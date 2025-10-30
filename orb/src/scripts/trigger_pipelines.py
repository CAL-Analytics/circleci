#!/usr/bin/env python3
"""
trigger_pipelines

Call out to circleci and trigger one or more pipelines.

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
import common
from git import remote_origin_url

loggy.info("trigger_pipelines(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
common.add_bash_exports_to_env()

_PIPELINE_TRIGGER_TOKEN = os.environ.get('PIPELINE_TRIGGER_TOKEN')
if not _PIPELINE_TRIGGER_TOKEN:
    loggy.info("trigger_pipelines(): PIPELINE_TRIGGER_TOKEN ENV var required. Please ensure the proper context has been set.")
    sys.exit(1)

_TRIGGER_PIPELINES = os.environ.get('TRIGGER_PIPELINES')
_DONT_TRIGGER_PIPELINES = os.environ.get('DONT_TRIGGER_PIPELINES')

#
# If this is blank, we set repo_type to circleci, otherwise, bitbucket
#
_REPO_URL = common.get_environ('CIRCLE_REPOSITORY_URL')
_REPO_TYPE = 'circleci'
if 'github.com' in _REPO_URL:
    _REPO_TYPE = 'gh'
elif 'bitbucket' in _REPO_URL:
    _REPO_TYPE = 'bitbucket'

_REPO_SLUG = os.environ.get('REPO_SLUG')
if not _REPO_SLUG:
    if 'bitbucket' in _REPO_TYPE or 'gh' in _REPO_TYPE:
        _REPO_SLUG = os.environ.get('CIRCLE_PROJECT_REPONAME', None)
    else:
        _REPO_SLUG = os.environ.get('CIRCLE_PROJECT_ID', None)

_ENV_BRANCH_NAME = os.environ.get('ENV_BRANCH_NAME')
if not _ENV_BRANCH_NAME:
    _ENV_BRANCH_NAME = os.environ.get('CIRCLE_BRANCH', None)

if 'bitbucket' in _REPO_TYPE or 'gh' in _REPO_TYPE:
    _CIRCLE_PROJECT_USERNAME = os.environ.get('CIRCLE_PROJECT_USERNAME')
else:
    _CIRCLE_PROJECT_USERNAME = os.environ.get('CIRCLE_ORGANIZATION_ID')

loggy.info(f"trigger_pipelines(): Variables Set: trigger_pipelines {_TRIGGER_PIPELINES} dont_trigger_pipelines {_DONT_TRIGGER_PIPELINES} repo_slug {_REPO_SLUG} env_branch_name {_ENV_BRANCH_NAME} circle_project_username {_CIRCLE_PROJECT_USERNAME}")

#
# Here, we sneakily check if someone has set _TRIGGER_PARAMETER and if so, allow it to override
# TRIGGER_PARAMETER. This allows us to use ENVs that are part of the same Job in CircleCI as we
# can't actually set a parameter to an ENV or dynamically use values we generate after synth.
#
_TRIGGER_PARAMETERS = os.environ.get('_TRIGGER_PARAMETERS', os.environ.get('TRIGGER_PARAMETERS', None))

import requests

for _pipeline in _TRIGGER_PIPELINES.split(','):
    #
    # We have at least 1 parameter, which is the pipeline name to trigger
    #
    _parameters = {f"{_pipeline}": True}

    #
    # If we have any DONT_TRIGGER_PIPELINES, add them to each of the pipelines we trigger.
    #
    if _DONT_TRIGGER_PIPELINES:
        for _dont_trigger_pipeline in _DONT_TRIGGER_PIPELINES.split(','):
            _parameters[_dont_trigger_pipeline] = False

    #
    # Determine if we have any other parameters to add
    #
    if _TRIGGER_PARAMETERS:
        loggy.info(f"trigger_pipelines(): _TRIGGER_PARAMETERS set to {_TRIGGER_PARAMETERS}")
        for _param in _TRIGGER_PARAMETERS.split(';'):
            tp, tv = _param.split('=')[:2]
            _parameters[tp] = tv

    #
    # Set our json_params up 
    #
    json_params={"branch": _ENV_BRANCH_NAME, "parameters": _parameters}
    loggy.info(f"trigger_pipelines(): json_params {json_params}")

    #
    # Determine the repo type being used by the url
    # For whatever reason, CIRCLECI_REPO_URL is blank when i pull it in. 
    #
    # repo_url = remote_origin_url()
    # supported_repos = {"bitbucket", "github"}
    # if not any(_repo in repo_url for _repo in supported_repos):
    #     loggy.info(f"trigger_pipelines(): Repo {repo_url} not yet supported. Only ({supported_repos}) repos are supported.")
    #     sys.exit(1)
    # repo_type = 'circleci' if 'github' in repo_url else 'bitbucket'

    #
    # Shoot a request to the circleCi API with to trigger the pipeline with our parameters
    #
    loggy.info(f"trigger_pipelines(): https://circleci.com/api/v2/project/{_REPO_TYPE}/{_CIRCLE_PROJECT_USERNAME}/{_REPO_SLUG}/pipeline")
    x = requests.post(
        f"https://circleci.com/api/v2/project/{_REPO_TYPE}/{_CIRCLE_PROJECT_USERNAME}/{_REPO_SLUG}/pipeline",
        headers={"content-type": "application/json", "Circle-Token": _PIPELINE_TRIGGER_TOKEN},
        json=json_params)

    if x.status_code != 201:
        loggy.info(f"trigger_pipelines(): Triggering pipeline/workflow {_pipeline} failed.")
        loggy.info(x.text)
        sys.exit(1)

    loggy.info(x.text)

sys.exit(0)
