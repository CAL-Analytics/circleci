#!/usr/bin/env python3
"""
ecs_deploy

Deploys a new task definition to an existing ECS Cluster/Service

"""
import os
import sys
import re
import multiprocessing

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
_SERVICE_ARNS = os.environ.get('SERVICE_ARNS')
_ENV_NAME = os.environ.get('ENV_NAME')
_AWS_DEFAULT_REGION = os.environ.get('AWS_DEFAULT_REGION')

if not _APP_NAME or not _CLUSTER_ARN or not _SERVICE_ARNS or not _ENV_NAME or not _AWS_DEFAULT_REGION:
    loggy.info("ecs_deploy_many(): ERROR: Must set APP_NAME, CLUSTER_ARN, SERVICE_ARNS, ENV_NAME and AWS_DEFAULT_REGION")

# Split the SERVICE_ARNS into a list, run ecs_deploy_v2 for each service ARN in parallel using multiprocessing
service_arns = _SERVICE_ARNS.split(',')
def deploy_service(service_arn):
    return ecs_deploy_v2(clusterArn=_CLUSTER_ARN, serviceArn=service_arn, tag=f"{_ENV_NAME}_rc")

with multiprocessing.Pool(processes=len(service_arns)) as pool:
    results = pool.map(deploy_service, service_arns)

# Check if any of the deployments failed
if any(not result for result in results):
    loggy.info("ecs_deploy_many(): ERROR: One or more deployments failed")
    sys.exit(1)

# They should be using the same image, so only need to do this once
if not ecr_tag_to_build(container=f"{_APP_NAME}:{_ENV_NAME}_rc", tag_list=[f"{_ENV_NAME}-{_AWS_DEFAULT_REGION}"]):
    loggy.info("ecs_deploy_many(): ERROR: Failed to tag and push image for services.")
    sys.exit(1)

sys.exit(0)