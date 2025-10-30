#!/usr/bin/env python3
"""
create_robots_txt.py

Create a robots txt file

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ
from release import create_robots_txt

loggy.info("create_robots_txt(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_BODY = get_environ('BODY')
_ROBOTS_PATH = get_environ('ROBOTS_PATH')

if not _BODY or not _ROBOTS_PATH:
    loggy.info("create_robots_txt(): Must set parameters for BODY and ROBOTS_PATH.")
    sys.exit(1)

if not create_robots_txt(body=_BODY, robots_path=_ROBOTS_PATH):
    loggy.info("create_robots_txt(): Failed to create robots.txt file.")
    sys.exit(1)

sys.exit(0)

