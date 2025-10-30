#!/usr/bin/env python3
"""
yarn_build

Run a yarn build

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, push_export_to_env, ChDir, get_environ
from yarn import build, install
from release import get_version, package
from aws import s3_cp

loggy.info("yarn_build(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_APP_NAME = get_environ('APP_NAME', None)
_BUILD_PATH = get_environ('BUILD_PATH', ".")
_VERSION_FILE = get_environ('VERSION_FILE', "version")
_DIST_PATH = get_environ('DIST_PATH', "dist")
_ARTIFACTS_BUCKET = get_environ('ARTIFACTS_BUCKET', None)

if not _ARTIFACTS_BUCKET:
    loggy.info(f"yarn_build(): Could not load ARTIFACTS_BUCKET env. Is Global context set?")
    sys.exit(1)

version = get_version()
loggy.info(f"yarn_build(): Realase version created as {version}")

with ChDir(_BUILD_PATH):
    if not install():
        loggy.info("yarn_build(): Failed to install yarn packages.")
        sys.exit(1)
    if not build():
        loggy.info("yarn_build(): Failed to build dist.")
        sys.exit(1)
    if os.path.exists(f"{_DIST_PATH}/{_VERSION_FILE}"):
        loggy.info(f"yarn_build(): Version file {_DIST_PATH}/{_VERSION_FILE} exists. Will not overwrite. Failing build.")
        sys.exit(1)

    try:
        # Write the version to a file in a json blob so it's read from the web properly.
        with open(f"{_DIST_PATH}/{_VERSION_FILE}", "w") as version_file:
            version_file.write("{ \"version\": \"" + version + "\" }")
    except Exception as e:
        loggy.info(f"yarn_build(): Failed to write version file to {_DIST_PATH}/{_VERSION_FILE}. {str(e)}")
        sys.exit(1)

    _package = package(folder=_DIST_PATH, version=version)
    if not _package:
        loggy.info(f"yarn_build(): Failed to package file.")
        sys.exit(1)

    #
    # Push the new artifact file to the build artifacts S3 bucket
    #
    loggy.info(f"yarn_build(): Pushing artifact {_package} to artifact bucket {_ARTIFACTS_BUCKET} in S3.")
    if not s3_cp(s3_bucket=f"s3://{_ARTIFACTS_BUCKET}", 
                s3_path=f"{_APP_NAME}/", 
                files=_package):
        sys.exit(1)

    #
    # Push our artifact file into the build args for future commands/jobs in this
    # pipeline to read in. This is so we can trigger the deploy pipelines with 
    # the version/archive file.
    #
    if not push_export_to_env(export_name="_TRIGGER_PARAMETERS", export_value=f"ARTIFACTS_FILE={_APP_NAME}/{_package}"):
        logger.info("Failed to push ARTIFACT_FILE into pipeline BASH_ENV as a trigger parameter")
        sys.exit(1)

sys.exit(0)