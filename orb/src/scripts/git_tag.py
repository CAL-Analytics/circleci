#!/usr/bin/env python3
"""
git_tag

Add a tag to the current git commit.

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
# from release import get_version
from subprocess_tee import run as _run
import toml

loggy.info("git_tag(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_TAG = os.environ.get('TAG')

if not _TAG:
    loggy.info("git_tag(): ERROR: Must set TAG")
    sys.exit(1)

# Add the tag to the current commit
_run(f"git tag -a '{_TAG}' -m 'CircleCI Promoting to {_TAG}' -f", check=True, shell=True)
_run(f"git push origin '{_TAG}'", check=True, shell=True)

sys.exit(0)