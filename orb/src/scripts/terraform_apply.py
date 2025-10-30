#!/usr/bin/env python3
"""
terraform_apply

Run a terraform apply

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
from terraform import apply
from aws import init_session

loggy.info("terraform_apply(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

#
# Log into aws, set the creds in the ~/.aws/credentials
#
init_session()

_TF_ENV = os.environ.get('TF_ENV')

# if not cdk.pre_tag_container(properties_env=_CDK_ENV):
#     sys.exit(1)

if not apply(properties_env=_TF_ENV):
    sys.exit(1)
