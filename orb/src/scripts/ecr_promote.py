#!/usr/bin/env python3
"""
ecr_promote

Promotes a tagged ECR container to another environment. Also promotes the git repo.

"""
import os
import sys
import re

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
from release import git_promote
from aws import ecr_tag

loggy.info("ecr_promote(): BEGIN")

"""
      - cicd/ecr-promote:
          requires:
            - hold-promote
          name: promote
          context: 
            - global
            - unfurly-dev
          app_name: unfurly/redirector
          env_tag: dev_blue_rc
          next_env_tag: prod_blue_rc
          env_branch_name: develop
          next_env_branch_name: prod
          trigger_pipelines: run_workflow_blue_deploy_prod,run_workflow_green_deploy_prod
          slack_thread_id: deploy_blue_dev
"""

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_APP_NAME = os.environ.get('APP_NAME')
_ENV_TAG = os.environ.get('ENV_TAG')
_NEXT_ENV_TAG = os.environ.get('NEXT_ENV_TAG')

if not _APP_NAME or not _ENV_TAG or not _NEXT_ENV_TAG:
    loggy.info("ecr_promote(): ERROR: Must set APP_NAME, ENV_TAG and NEXT_ENV_TAG")

# Split the string on , or : or ;
_TAG_LIST = re.split(r'[,:;]', _NEXT_ENV_TAG)

for _tag in _TAG_LIST:
    if not ecr_tag(container=f"{_APP_NAME}:{_ENV_TAG}", tag=_tag):
        sys.exit(1)

sys.exit(0)