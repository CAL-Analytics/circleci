#!/usr/bin/env python3
"""
release.py

Common code useful for release pipelines.

Example Usage:
    from utils import release
    from utils.release import get_new_build_release as _version
"""

import datetime
import os
import sys
import json
from subprocess_tee import run as _run
from aws import cloudfront_get_kvs_key, cloudfront_update_kvs_key
from enum import Enum
from dns import resolver
import typing
import requests

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import get_environ, resolve_pipeline_variable, ChDir
from aws import route53_update_txt_record

last_weight = {}
last_green_version = {}
last_blue_version = {}
last_retrieved = {}

FULL_ROUTING = { "blue": 0, "green": 100}

class Release(Enum):
    DEV = "develop"
    DEVELOP = "develop"
    QA = "qa"
    STAGE = "staging"
    STAGING = "staging"
    DEMO = "demo"
    PROD = "master"
    HOTFIX = "hotfix"


def get_semver():
    """
    get_semver()

    Generates a new build version string using Semantic Versioning using environment variables.

    Uses the following Environment variables to generate the version string:

    * VERSION_MAJOR
    * VERSION_MINOR
    * GO_PIPELINE_COUNTER

    Returns: None if environment variables are not set

    NOTE: Looks for GO_PIPELINE_COUNTER, then BITBUCKET_BUILD_NUMBER, then CIRCLE_BUILD_NUM in that order.
    """
    counter = os.environ.get('GO_PIPELINE_COUNTER', os.environ.get('BITBUCKET_BUILD_NUMBER', os.environ.get('CIRCLE_BUILD_NUM', None)))
    if os.environ.get('VERSION_MAJOR') and os.environ.get('VERSION_MINOR') and counter:
        return f"{os.environ.get('VERSION_MAJOR')}.{os.environ.get('VERSION_MINOR')}.{counter}"

    return None


def get_version():
    """
    get_version()

    Generates a new build version string using `get_new_build_release()`

    NOTE: This is the `default` version format for ALL of our backend versioning.

    """
    return get_new_build_release()

def get_pipeline_number() -> int:
    pipeline_number = 0
    _CIRCLE_WORKFLOW_ID = get_environ('CIRCLE_WORKFLOW_ID')
    _PIPELINE_TRIGGER_TOKEN = get_environ('PIPELINE_TRIGGER_TOKEN')
    if not _CIRCLE_WORKFLOW_ID or not _PIPELINE_TRIGGER_TOKEN:
        loggy.info("release.get_pipeline_number(): Pipeline error. One of CIRCLE_WORKFLOW_ID or PIPELINE_TRIGGER_TOKEN not set on environment.")
        loggy.info("Dumping available ENV vars for debugging:")
        for key, value in os.environ.items():
            loggy.info(f"{key}={value}")
        return pipeline_number

    try:
        loggy.info(f"release.get_pipeline_number(): Getting pipeline_number for workflow: https://circleci.com/api/v2/workflow/{_CIRCLE_WORKFLOW_ID}")
        x = requests.get(f"https://circleci.com/api/v2/workflow/{_CIRCLE_WORKFLOW_ID}", headers={"Circle-Token": _PIPELINE_TRIGGER_TOKEN})
        if x.status_code < 200 or x.status_code > 299:
            loggy.info(f"release.get_pipeline_number():  ERROR getting pipeline_number. {x.text}")
            return pipeline_number

        pipeline_number = x.json()['pipeline_number']
    except Exception as e:
        loggy.info(f"release.get_pipeline_number(): Failed to get pipeline_number. {str(e)}")

    return pipeline_number


def get_new_build_release():
    """
    get_new_build_release()

    Updated 2023-06-13 TAW
    Generates a new build version string in the format: YY.MM.DD.GO_PIPELINE_COUNTER.GO_REVISION_*

    Will search env variables for GO_REVISION_* and use the first one it finds, in case there's multiple repos

    returns: String

    NOTE: Looks for BITBUCKET_COMMIT, then CIRCLE_SHA1, then GO_REVISION_* in that order
    NOTE: Looks for GO_PIPELINE_COUNTER, then BITBUCKET_BUILD_NUMBER, then CIRCLE_BUILD_NUM in that order.
    """
    now = datetime.datetime.now().strftime("%y.%m.%d")

    # Roll through the environ variables and set the commit_hash to the first one it finds, default to string 0
    commit_hash = '0' 
    if os.environ.get('BITBUCKET_COMMIT', None):
        commit_hash = os.environ.get('BITBUCKET_COMMIT')[0:7]
    elif os.environ.get('CIRCLE_SHA1', None):
        commit_hash = os.environ.get('CIRCLE_SHA1')[0:7]
    else:
        for name, value in os.environ.items():
            if "GO_REVISION_" in name:
                commit_hash = os.environ.get(name, '0')
                if len(commit_hash) > 7:
                    commit_hash = commit_hash[0:7]
                break
        
    # version = f"{now}{os.environ.get('GO_PIPELINE_COUNTER', os.environ.get('BITBUCKET_BUILD_NUMBER', os.environ.get('CIRCLE_BUILD_NUM', '0')))}.{commit_hash}"
    #
    # NOTE: In circleci, the CIRCLE_BUILD_NUM increments per JOB, so we can't use this on a workflow/pipeline
    # level to pass around version. The real pipeline version is NOT given in an environment variable. 
    #
    version = f"{now}.{get_pipeline_number()}.{commit_hash}"

    loggy.info(f"release.get_new_build_release(): Generated build: {version}")
    return version


def _check_for_multiple_materials():
    """
    _check_for_multiple_materials()

    Checks for and exits if multiple materials in a GoCD pipeline are found.
    We currently do not support this in our release functions.

    returns: False
    """
    counter = sum(x.startswith('GO_REVISION_') for x in os.environ.keys())

    if counter > 1:
        loggy.error("release.get_commit_short_hash(): Error: (" + counter + ") Materials found in Env. We only support 1 Material right now.")
        sys.exit(1)

    return False


def get_commit_short_hash():
    """
    get_commit_short_hash()

    Grabs the git commit hash from ENV vars in a GoCD pipeline and returns the first 8 chars.

    returns: String

    NOTE: Looks for BITBUCKET_COMMIT, then CIRCLE_SHA1, then GO_REVISION_* in that order
    """
    if os.environ.get('BITBUCKET_COMMIT', None):
        return os.environ.get('BITBUCKET_COMMIT', None)[0:7]
    elif os.environ.get('CIRCLE_SHA1', None):
        return os.environ.get('CIRCLE_SHA1')[0:7]

    _check_for_multiple_materials()
    return next(val for key, val in os.environ.items() if key.startswith('GO_REVISION_'))[0:7]


def get_source_branch():
    """
    get_source_branch()

    Grabs the git branch from ENV vars in a GoCD pipeline

    returns: String

    NOTE: Looks for BITBUCKET_BRANCH, then CIRCLE_BRANCH, then GO_MATERIAL_BRANCH in that order
    """
    if os.environ.get('BITBUCKET_BRANCH', None):
        return os.environ.get('BITBUCKET_BRANCH', None)
    elif os.environ.get('CIRCLE_BRANCH', None):
        return os.environ.get('CIRCLE_BRANCH', None)
 
    _check_for_multiple_materials()
    try:
        return next(val for key, val in os.environ.items() if key.startswith('GO_MATERIAL_BRANCH'))
    except StopIteration as e:
        loggy.error(f"release.get_source_branch(): No branches found. GO_MATERIAIL_BRANCH_x env vars not found. Is this a GoCD pipeline? {str(e)}")
        return None


def get_last_tag():
    """
    get_last_tag()

    Grabs the latest tag in a git repo.

    returns: String or None
    """
    _run("git fetch --all --tags", check=False, shell=True)
    latest_tag = _run("git for-each-ref refs/tags --sort=-taggerdate --count=1 --format=\"%(refname)\"", check=False, shell=True)

    resolved = latest_tag.stdout.strip().split('/')[-1] if latest_tag else None

    loggy.info(f"release.get_last_tag(): Returning latest tag as: {resolved}")
    return resolved


# def git_promote(version=None, source=None, dest=None, tag=None) -> bool:
#     """
#     git_promote()

#     Git promote a release from one branch to another.

#     version: Defaults to `get_new_build_release()`, which generates a version
#     string in the following format: YYYY.MM.BUILD_NUMBER

#     source: Defaults to `develop`

#     dest: Defaults to `qa`

#     tag: Default is None. If set, we will tag the release version.
#     """
#     source_branch = 'develop' if source is None else resolve_pipeline_variable(source)
#     dest_branch = 'qa' if dest is None else resolve_pipeline_variable(dest)
#     version = get_new_build_release() if version is None else resolve_pipeline_variable(version)
#     promote_branch = f"promote/{version}"

#     _run("git status", check=False, shell=True)
#     _run("git config -l", check=False, shell=True)
#     _skip_merge = False

#     try:
#         _run(f"git checkout {dest_branch}", check=True, shell=True)
#         _run(f"git pull origin {dest_branch}", check=True, shell=True)
#     except Exception as e:
#         # dest branch doesn't exist. creating it
#         loggy.error("release.git_promote(): Exception: " + str(e))
#         _run(f"git checkout -b {dest_branch}", check=True, shell=True)
#         _run(f"git push origin {dest_branch}", check=True, shell=True)

#         _skip_merge = True
#         pass

#     if not _skip_merge:
#         _run(f"git checkout {source_branch}", check=True, shell=True)
#         _run(f"git pull origin {source_branch}", check=True, shell=True)

#         try:
#             loggy.info(f"release.git_promote(): Creating temp release branch {promote_branch}")
#             _run(f"git checkout -b {promote_branch}", check=True, shell=True)
#         except Exception as e:
#             # branch probably already exists...
#             loggy.error("release.git_promote(): Exception: " + str(e))
#             _run(f"git branch -D {promote_branch}", check=True, shell=True)
#             _run(f"git checkout -b {promote_branch}", check=True, shell=True)
#             pass

#         _run(f"git merge --strategy=ours --no-edit {dest_branch}", check=True, shell=True)
#         _run(f"git checkout {dest_branch}", check=True, shell=True)
#         _run(f"git merge --squash {promote_branch}", check=True, shell=True)

#         try:
#             output = _run(f"git commit -m \"CiCD merge {source_branch} to {dest_branch} for promotion {version}\"", check=False, shell=True)

#             if output.returncode != 0:
#                 if 'nothing to commit' in output.stderr or 'nothing to commit' in output.stdout:
#                     loggy.info("release.git_commit(): Nothing to commit. Skipping push and proceeding as success.")
#                 else:
#                     loggy.error("release.git_commit(): Git commit failure. Exiting. now")
#                     loggy.error(f"release.git_promote(): {output.stdout}")
#                     loggy.error(f"release.git_promote(): {output.stderr}")
#                     loggy.error(f"release.git_promote(): {str(output.returncode)}")
#                     raise Exception(output.stderr)
#             else:
#                 _run(f"git push origin {dest_branch}", check=True, shell=True)
#         except Exception as e:
#             loggy.error(f"release.git_promot(): {str(e)}")
#             return False

#     if 'master' in dest_branch:
#         version = get_new_build_release() if tag is None else tag
#         _run(f"git tag -f -a {version} -m \"Rev to version {version}\"", check=True, shell=True)
#         _run(f"git push origin {version}", check=True, shell=True)

#     return True


def git_promote(version=None, source=None, dest=None, tag=None, keep_changes=False) -> bool:
    """
    git_promote()

    Git promote a release from one branch to another.

    version: Defaults to `get_new_build_release()`, which generates a version
    string in the following format: YYYY.MM.BUILD_NUMBER

    source: Defaults to `develop`

    dest: Defaults to `qa`

    tag: Default is None. If set, we will tag the release version.

    keep_changes: if True, we'll just use the existing /home/circleci/project path, defaults to False

    NOTE: Checks if we are running on Bitbucket, then CircleCI, then GoCD
    """
    source_branch = 'develop' if source is None else resolve_pipeline_variable(source)
    dest_branch = 'qa' if dest is None else resolve_pipeline_variable(dest)
    version = get_new_build_release() if version is None else resolve_pipeline_variable(version)
    promote_branch = f"promote/{version}"

    #
    # We want to check out a fresh repo here, in case any files were created/modified in here by accident. 
    # 
    # _REPO_PATH = os.environ.get('PWD', None)
    _REPO_PATH = "/home/circleci/project" 
    
    if not keep_changes:
        _REPO_PATH = f"/home/circleci/{os.environ.get('CIRCLE_REPOSITORY_URL').split('/')[-1].split('.git')[0]}"

        with ChDir("/home/circleci"):
            _run(f"git clone {os.environ.get('CIRCLE_REPOSITORY_URL')}", check=True, shell=True)

    with ChDir(_REPO_PATH):
        _run(f"git checkout {source}", check=True, shell=True)

    #
    # Ensure we are in the right path before running commands
    #
    with ChDir(_REPO_PATH):
        _run("git status", check=False, shell=True)
        _run("git config -l", check=False, shell=True)
        _skip_merge = False

        try:
            _run(f"git checkout {dest_branch}", check=True, shell=True)
            _run(f"git pull origin {dest_branch}", check=True, shell=True)
        except Exception as e:
            # dest branch doesn't exist. creating it
            loggy.error("release.git_promote(): Exception: " + str(e))
            _run(f"git checkout -b {dest_branch}", check=True, shell=True)
            _run(f"git push origin {dest_branch}", check=True, shell=True)

            _skip_merge = True
            pass

        if not _skip_merge:
            _run(f"git checkout {source_branch}", check=True, shell=True)
            _run(f"git pull origin {source_branch}", check=True, shell=True)

            try:
                loggy.info(f"release.git_promote(): Creating temp release branch {promote_branch}")
                _run(f"git checkout -b {promote_branch}", check=True, shell=True)
            except Exception as e:
                # branch probably already exists...
                loggy.error("release.git_promote(): Exception: " + str(e))
                _run(f"git branch -D {promote_branch}", check=True, shell=True)
                _run(f"git checkout -b {promote_branch}", check=True, shell=True)
                pass

            _run(f"git merge --strategy=ours --no-edit {dest_branch}", check=True, shell=True)
            _run(f"git checkout {dest_branch}", check=True, shell=True)
            _run(f"git merge --squash {promote_branch}", check=True, shell=True)

            try:
                output = _run(f"git commit -m \"CiCD merge {source_branch} to {dest_branch} for promotion {version}\"", check=False, shell=True)

                if output.returncode != 0:
                    if 'nothing to commit' in output.stderr or 'nothing to commit' in output.stdout:
                        loggy.info("release.git_commit(): Nothing to commit. Skipping push and proceeding as success.")
                    else:
                        loggy.error("release.git_commit(): Git commit failure. Exiting. now")
                        loggy.error(f"release.git_promote(): {output.stdout}")
                        loggy.error(f"release.git_promote(): {output.stderr}")
                        loggy.error(f"release.git_promote(): {str(output.returncode)}")
                        raise Exception(output.stderr)
                else:
                    _run(f"git push origin {dest_branch}", check=True, shell=True)
            except Exception as e:
                loggy.error(f"release.git_promot(): {str(e)}")
                return False

        if 'master' in dest_branch:
            version = get_new_build_release() if tag is None else tag
            _run(f"git tag -f -a {version} -m \"Rev to version {version}\"", check=True, shell=True)
            _run(f"git push origin {version}", check=True, shell=True)

    return True


def get_routing_info(record_name):
    """
    get_routing_info()
    
    Fetch the routing info from a dns TXT record.

    record_name str pointing to a valid dns record

    returns a json object with weight and color versions. If error, returns empty
    """
    global last_weight, last_green_version, last_blue_version, last_retrieved

    loggy.info("release.get_routing_info: BEGIN")

    info = {}

    now = datetime.datetime.now()
    # Cache the value for 60 seconds to reduce DNS lookups
    if record_name in last_retrieved and (now - last_retrieved[record_name]).total_seconds() < 30:
        info['weight'] = last_weight[record_name]
        info['green'] = last_green_version[record_name]
        info['blue'] = last_blue_version[record_name]
        return info

    try:
        # Fetch the TXT record for the domain
        txt_records = resolver.resolve(record_name, "TXT")

        info['weight'] = int(txt_records[0].strings[0])
        info['green'] = "unknown"
        info['blue'] = "unknown"

        last_weight[record_name] = info['weight']
        last_green_version[record_name] = info['green']
        last_blue_version[record_name] = info['blue']
        last_retrieved[record_name] = now
        loggy.info(f"release.get_routing_weight: Return weight: {info['weight']}")

    except ValueError as e:
        _record = json.loads(txt_records[0].strings[0].decode('utf-8').replace("'", '"'))
        info['weight'] = _record['weight']
        #
        # TODO: Remove this if code and only use the else block. it's only needed for fallback to v2
        #
        if 'version' in _record:
            info['green'] = _record['version']
            info['blue'] = _record['version']
        else:
            info['green'] = _record['green']
            info['blue'] = _record['blue']

        last_weight[record_name] = info['weight']
        last_green_version[record_name] = info['green']
        last_blue_version[record_name] = info['blue']
        last_retrieved[record_name] = now
        loggy.info(f"release.get_routing_weight: Return weight: {info['weight']}")

    except Exception as e:
        print(f"release.get_routing_weight(): Error resolving DNS for {record_name}: {e}") 
    
    return info  # Default to {} if DNS fails

# def get_routing_weight(record_name):
#     """
#     get_routing_weight()
    
#     Fetch the routing weight from a dns TXT record.

#     record_name str pointing to a valid dns record

#     returns weight 0-100. If error, returns -1
#     """
#     global last_weight, last_version, last_retrieved

#     loggy.info("release.get_routing_weight: BEGIN")

#     now = datetime.datetime.now()
#     # Cache the value for 60 seconds to reduce DNS lookups
#     if record_name in last_retrieved and (now - last_retrieved[record_name]).total_seconds() < 30:
#         return last_weight[record_name]

#     try:
#         txt_records = resolver.resolve(record_name, "TXT")
#         _record = json.loads(txt_records[0].strings[0].decode('utf-8').replace("'", '"'))

#         weight = _record['weight']
#         version = _record['version']

#         last_weight[record_name] = weight
#         last_version[record_name] = version
#         last_retrieved[record_name] = now
#         loggy.info(f"release.get_routing_weight: Return weight: {weight}")

#         return weight
#     except Exception as e:
#         loggy.error(f"release.get_routing_weight(): Error resolving DNS for {record_name}: {e}")
#         return -1  # Default to -1 if DNS fails

def get_inactive_color(record_name: str | None = None, kvs_arn: str | None = None, kvs_key: str | None = None, force_routing: typing.Optional[bool] = None) -> str:
    loggy.info("release.get_inactive_color: BEGIN")

    info = {}
    if kvs_arn and kvs_key:
        info = cloudfront_get_kvs_key(kvs_arn=kvs_arn, kvs_key=kvs_key)
        if info.startswith('{'):
            info = json.loads(info.replace("'", '"'))
    else:
        info = get_routing_info(record_name)

    weight = info['weight']
    if weight < 0:
        loggy.info(f"release.get_inactive_color: Unknown weight {weight}. Returning None")
        return None

    active_color = None
    inactive_color = None

    #
    # If we are weighted more to the blue side, we will deploy to green
    #
    if weight < 50:
        active_color = "blue"
        inactive_color = "green"
    if weight >= 50:
        active_color = "green"
        inactive_color = "blue"

    #
    # If force_routing is set, we make sure routing is 100% weighted to the most weighted live color
    #
    if force_routing and weight != 0 and weight != 100:
        loggy.info(f"release.get_inactive_color: Forcing active color to {active_color}")
        info[active_color] = get_version()
        info['weight'] = FULL_ROUTING[active_color]
        if kvs_arn and kvs_key:
            if not set_active_color(kvs_arn=kvs_arn, kvs_key=kvs_key, info=info):
                loggy.info(f"release.get_inactive_color: Failed Forcing active color to {active_color}")
                return None
        else:
            if not set_active_color(record_name=record_name, info=info):
                loggy.info(f"release.get_inactive_color: Failed Forcing active color to {active_color}")
                return None

    return inactive_color

def set_active_color(info: dict, record_name: str | None = None, kvs_arn: str | None = None, kvs_key: str | None = None) -> bool:
    """
    set_active_color()

    Set the active color in routing TXT record

    record_name str Record name to modify
    kvs_arn str Key Value Store ARN to modify
    kvs_key str Key to modify
    info dict Dictionary of weighting info to write to route53 or kvs
    """
    loggy.info(f"release.set_active_color: BEGIN - Setting active color.")
    if record_name:
        domain_name = '.'.join(record_name.split('.')[1:])
        record_name = record_name.split('.')[0]
        return route53_update_txt_record(record_name=record_name, domain_name=domain_name, txt=str(info))
    elif kvs_arn and kvs_key:
        return cloudfront_update_kvs_key(kvs_arn=kvs_arn, kvs_key=kvs_key, value=str(info))
    else:
        loggy.info(f"release.set_active_color: No record_name or kvs_arn and kvs_key provided. Skipping.")
        return False

def package(folder: str, app_name: typing.Optional[str] = None, version: typing.Optional[str] = None) -> str:
    loggy.info(f"release.package(): BEGIN")

    if not version:
        version = get_version()

    if not os.path.exists(f"{folder}"):
        loggy.info(f"release.package() folder {folder} does not exist.")
        return None
    
    artifact_name = f"{version}.tar.gz"
    if app_name:
        artifact_name = f"{app_name}-{artifact_name}"

    try:
        _run(f"tar -zcvf {artifact_name} {folder}", check=True, shell=True)
    except Exception as e:
        loggy.info(f"release.package() Failed to create package {artifact_name} for {folder}. {str(e)}")
        return None
    
    return artifact_name

def create_robots_txt(body: str, robots_path: str) -> bool:
    loggy.info(f"release.create_robots_txt(): BEGIN")

    if not os.path.exists(robots_path):
        loggy.info(f"release.create_robots_txt() folder {robots_path} does not exist.")
        return False

    try:
        with open(f"{robots_path}/robots.txt", "w") as robots_file:
            robots_file.write(body)
    except Exception as e:
        loggy.info(f"release.create_robots_txt(): Failed to write {robots_path}/robots.txt file. {str(e)}")
        return False
    
    return True