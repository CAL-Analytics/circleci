#!/usr/bin/env python3
"""
cdk_diff

Run a cdk diff

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
import common
import cdk
import aws
import release
import docker

loggy.info("docker_build(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
common.add_bash_exports_to_env()

_BUILD_VERSION = release.get_version()


# 
# Let's mock up our ENV_NAME so that it aligns with our CDK application model
#

# We can convert our git tag to an ENV_NAME by removing the 'deploy/' prefix and replacing '.' with '-'
_ENV_NAME = os.environ.get('ENV_NAME')
if _ENV_NAME:
    _ENV_NAME = _ENV_NAME.replace('deploy/', '').replace('.', '-')

_APP_NAME = os.environ.get('APP_NAME')
_DOCKERFILE_PATH = common.get_environ('DOCKERFILE_PATH', ".")
loggy.info(f"docker_build(): Setting _DOCKERFILE_PATH to {_DOCKERFILE_PATH}")

_DOCKERFILE_NAME = common.get_environ('DOCKERFILE_NAME', "Dockerfile")

#
# Grab our running platform
#
_RUNNING_PLATFORM = 'linux/amd64' if 'x86_64' in common.subprocess_run("uname -a").stdout else 'linux/arm64'
loggy.info(f"docker_build(): Setting _RUNNING_PLATFORM to {_RUNNING_PLATFORM}")

#
# Set our docker platform to the runnning platform, IF and only if, the docker platform value wasn't forced
#
_DOCKER_PLATFORM = common.get_environ('DOCKER_PLATFORM', _RUNNING_PLATFORM)
loggy.info(f"docker_build(): Setting _DOCKER_PLATFORM to {_DOCKER_PLATFORM}")

#
# Set any docker build args passed into us. This is a comma separated list of build args like "SOMETHING=HELLO,OTHERTHING=NO"
#
_DOCKER_BUILD_ARGS = common.get_environ('DOCKER_BUILD_ARGS', None)

#
# Set any docker build extra options passed into us. This is a string of extra options to pass to the docker build command.
#
_DOCKER_BUILD_EXTRA_OPTIONS = common.get_environ('DOCKER_BUILD_EXTRA_OPTIONS', None)

#
# Check if SSH should be enabled for docker build
#
_DOCKER_BUILD_SSH = common.get_environ('DOCKER_BUILD_SSH', None)

#
# Test if we passed in BUILD_VERSION as one of the args. If we didn't, then ensure it's set here.
#
if not _DOCKER_BUILD_ARGS:
    _DOCKER_BUILD_ARGS = f"BUILD_VERSION={_BUILD_VERSION}"
elif "BUILD_VERSION" not in _DOCKER_BUILD_ARGS:
    _DOCKER_BUILD_ARGS = f"{_DOCKER_BUILD_ARGS},BUILD_VERSION={_BUILD_VERSION}"
else:
    #
    # If we get here, the BUILD_VERSION was passed into this pipeline, so we override what we would have
    # created. This only happens on plumvp builds at the moment.
    #
    for _ARG in _DOCKER_BUILD_ARGS.split(','):
        if 'BUILD_VERSION' in _ARG:
            _BUILD_VERSION = _ARG.split('=')[1]

#
# Now we build out our docker build command, adding any build args we might have passed
#
_DOCKER_BUILD_COMMAND = ["build", "--platform", _DOCKER_PLATFORM]
for _BUILD_ARG in _DOCKER_BUILD_ARGS.split(','):
    _DOCKER_BUILD_COMMAND.append("--build-arg")
    _DOCKER_BUILD_COMMAND.append(_BUILD_ARG)

#
# Now, add any extra options we might have passed
#
if _DOCKER_BUILD_EXTRA_OPTIONS:
    for _EXTRA_OPTION in _DOCKER_BUILD_EXTRA_OPTIONS.split(','):
        _DOCKER_BUILD_COMMAND.extend(_EXTRA_OPTION.split(' '))

#
# Now we finish building out our docker build command with the final bits...
#
loggy.info("docker_build(): Getting ECR_FQDN")
_ECR_FQDN = aws.ecr_generate_build_fqcn(_APP_NAME)[0]

_DOCKER_BUILD_COMMAND.append("-t")
_DOCKER_BUILD_COMMAND.append(f"{_ECR_FQDN}:{_BUILD_VERSION}")

#
# Add the dockerfile name if it's unique
#
_DOCKER_BUILD_COMMAND.append("-f")
_DOCKER_BUILD_COMMAND.append(_DOCKERFILE_NAME)

#
# Finally, we tell docker to look at the root of this folder. We will be in a common.ChDir
# to run it, so this will always be good.
#
_DOCKER_BUILD_COMMAND.append(".")

#
# Set any environment variables to append to the environment before running the docker build command
#
_DOCKER_BUILD_ENV_APPEND = common.get_environ('DOCKER_BUILD_ENV_APPEND', None)
if _DOCKER_BUILD_ENV_APPEND:
    # make a dictionary of the environment variables to match os.environ format
    _NEW_DOCKER_BUILD_ENV_APPEND = os.environ.copy()
    for _ENV_VAR in _DOCKER_BUILD_ENV_APPEND.split(','):
        _NEW_DOCKER_BUILD_ENV_APPEND.update({_ENV_VAR.split('=')[0]: _ENV_VAR.split('=')[1]})
    _DOCKER_BUILD_ENV_APPEND = _NEW_DOCKER_BUILD_ENV_APPEND


# loggy.info("pipeline: *** SonarQube Code Scanning ***")
# sonarqube.scan()

# Don't build, just retag the image if the commit hash has already been built for this image
_COMMIT_HASH = release.get_commit_short_hash()
if aws.ecr_tag_exists(_ECR_FQDN, _COMMIT_HASH):
    loggy.info("docker_build(): Commit hash has already been built for this image. Tagging with the env.")
    aws.ecr_tag_to_build(container=f"{_ECR_FQDN}:{_COMMIT_HASH}", tag_list=[f"{_ENV_NAME}_rc", f"{_ENV_NAME}_blue_rc", f"{_ENV_NAME}_green_rc"])
    sys.exit(0)

#
# Moved the ecr login in case the Dockerfile we are building uses a FROM pulling an image from our ECR
#
aws.ecr_login_build()

with common.ChDir(_DOCKERFILE_PATH):
    loggy.info("docker_build(): Running docker.docker to build the docker container")
    if not docker.docker(_DOCKER_BUILD_COMMAND, env=_DOCKER_BUILD_ENV_APPEND, ssh=_DOCKER_BUILD_SSH):
        loggy.info("docker_build(): Docker failed. FAILING pipeline...")
        sys.exit(1)

loggy.info("docker_build(): Running aws.ecr_push")
if not aws.ecr_push(container=_ECR_FQDN, tag=_BUILD_VERSION, tag_list=[f"{_ENV_NAME}_rc", f"{_ENV_NAME}_blue_rc", f"{_ENV_NAME}_green_rc"]):
    loggy.info("docker_build(): ecr_push failed")
    sys.exit(1)

sys.exit(0)

