#!/usr/bin/env python3
"""
cdk_diff

Run a cdk diff

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
from cdk import diff, diff_pretty
from aws import init_session

loggy.info("cdk_diff(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

#
# Log into aws, set the creds in the ~/.aws/credentials
#
init_session()

_CDK_ENV = os.environ.get('CDK_ENV')
_CDK_LANG = os.environ.get('CDK_LANG')

if not diff(properties_env=_CDK_ENV, lang=_CDK_LANG):
    sys.exit(1)

if not diff_pretty(verbose=True):
    sys.exit(1)