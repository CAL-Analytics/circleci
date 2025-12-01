#!/usr/bin/env python3
"""
ecs_deploy

Deploys a new task definition to an existing ECS Cluster/Service

"""
import os
import sys
import re

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
from aws import ecs_deploy_v2, ecr_tag_to_build

loggy.info("ecs_deploy(): BEGIN")

"""
      - cicd/ecs-deploy:
          requires:
            - hold-deploy
          name: deploy
          context: 
            - global
            - unfurly-dev
          app_name: unfurly/redirector
          env_name: dev
"""

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_APP_NAME = os.environ.get('APP_NAME')
_CLUSTER_ARN = os.environ.get('CLUSTER_ARN')
_SERVICE_ARN = os.environ.get('SERVICE_ARN')
_ENV_NAME = os.environ.get('ENV_NAME')
_AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION')

if not _APP_NAME or not _CLUSTER_ARN or not _SERVICE_ARN or not _ENV_NAME or not _AWS_DEFAULT_REGION:
    loggy.info("ecs_deploy(): ERROR: Must set APP_NAME, CLUSTER_ARN, SERVICE_ARN, ENV_NAME and AWS_DEFAULT_REGION")

if not ecs_deploy_v2(clusterArn=_CLUSTER_ARN, serviceArn=_SERVICE_ARN, tag=f"{_ENV_NAME}_rc"):
    sys.exit(1)
if not ecr_tag_to_build(container=f"{_APP_NAME}:{_ENV_NAME}_rc", tag_list=[f"{_ENV_NAME}-{_AWS_DEFAULT_REGION}"]):
    exit(1)

sys.exit(0)