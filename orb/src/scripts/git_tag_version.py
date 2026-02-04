#!/usr/bin/env python3
"""
git_tag_version

Tag a version of the code using the pyproject.toml file for poetry or package.json for node.

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env
# from release import get_version
from subprocess_tee import run as _run
import toml

loggy.info("git_tag_version(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_TOOL = os.environ.get('TOOL')
_PREFIX = os.environ.get('PREFIX')

if not _TOOL:
    loggy.info("git_tag_version(): ERROR: Must set TOOL (poetry for now, node coming soon)")
    sys.exit(1)

if _TOOL == 'poetry':
    try:
        pyproject = toml.load('pyproject.toml')
    except FileNotFoundError as e:
        loggy.info("git_tag_version(): ERROR: pyproject.toml not found")
        sys.exit(1)

    try:
        _VERSION = pyproject['tool']['poetry']['version']
    except KeyError as e:
        try:
            _VERSION = pyproject['project']['version']
        except KeyError as e:
            try:
                _VERSION = pyproject['package']['version']
            except KeyError as e:
                loggy.info("git_tag_version(): ERROR: Must set version in pyproject.toml")
                sys.exit(1)

    if not _VERSION:
        loggy.info("git_tag_version(): ERROR: Must set version in pyproject.toml")
        sys.exit(1)

    if _PREFIX:
        _VERSION = f"{_PREFIX}{_VERSION}"
    loggy.info(f"git_tag_version(): Tagging version as {_VERSION}")
    _run(f"git tag -a '{_VERSION}' -m 'CircleCI Tagging Version {_VERSION}' -f", check=True, shell=True)
    _run(f"git push origin '{_VERSION}' -f", check=True, shell=True)

else:
    loggy.info("git_tag_version(): ERROR: Must set TOOL (poetry for now, node coming soon)")
    sys.exit(1)

sys.exit(0)