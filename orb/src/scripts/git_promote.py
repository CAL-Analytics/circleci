#!/usr/bin/env python3
"""
git_promote

Promote a branch of code to another branch.

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
from release import get_version, git_promote

loggy.info("git_promote(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_ENV_BRANCH_NAME = os.environ.get('ENV_BRANCH_NAME')
_NEXT_ENV_BRANCH_NAME = os.environ.get('NEXT_ENV_BRANCH_NAME')

if not _ENV_BRANCH_NAME or not _NEXT_ENV_BRANCH_NAME:
    loggy.info("git_promote(): ERROR: Must set both ENV_BRANCH_NAME and NEXT_ENV_BRANCH_NAME")

version = get_version()
loggy.info(f"git_promote(): Realase version created as {version}")

if not git_promote(source=_ENV_BRANCH_NAME, dest=_NEXT_ENV_BRANCH_NAME, version=version):
    sys.exit(1)

sys.exit(0)