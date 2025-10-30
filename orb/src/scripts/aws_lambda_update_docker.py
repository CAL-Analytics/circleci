#!/usr/bin/env python3
"""
aws_lambda_update_docker

Update lambda functions docker container

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
from aws import ssm_get_parameter, ecr_generate_fqcn, lambda_update_docker, ecr_tag

loggy.info("aws_lambda_update_docker(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_FUNCTION_ARN = os.environ.get('FUNCTION_ARN')
_APP_NAME = os.environ.get('APP_NAME')
_TAG = os.environ.get('TAG')

if not _FUNCTION_ARN or not _APP_NAME or not _TAG:
    loggy.info("aws_lambda_update_docker(): Must set parameters for function_arn, app_name and tag.")
    sys.exit(1)

if _FUNCTION_ARN.startswith('/'):
    loggy.info(f"aws_lambda_update_docker(): Setting FUNCTION_ARN from SSM Param {_FUNCTION_ARN}")
    _FUNCTION_ARN = ssm_get_parameter(name=_FUNCTION_ARN)                                

#
# Generate the fully qualified container name
#
_IMAGE_URI, _t = ecr_generate_fqcn(container=_APP_NAME)

#
# Deploy the new docker to lambda by updating the lambda function
#
if not lambda_update_docker(function_name=_FUNCTION_ARN, image_uri=f"{_IMAGE_URI}:{_TAG}"):
    loggy.info("aws_lambda_update_docker(): Failed to update lambda.")
    sys.exit(1)

#
# Tag the container as being released, we just chop off the _rc postfix for the final tag.
#
if not ecr_tag(container=f"{_IMAGE_URI}:{_TAG}", tag=_TAG.split('_rc')[0]):
    loggy.info("aws_lambda_update_docker(): Failed to tag container with cdk tag (no _rc).")
    sys.exit(1)


sys.exit(0)

