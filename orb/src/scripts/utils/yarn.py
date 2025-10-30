#!/usr/bin/env python3
"""
yarn

Common code useful for yarn.

Example Usage:
    from utils import build, install
    from utils.yarn import build, install
"""
import os
import sys
import typing
import shutil

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import subprocess_long as _long_run


def yarn(*args) -> bool:
    """
    Shell out to the yarn CLI.

    It is expected that the commands are sent in a single string as if you were typing it on the command line

    Example: yarn.yarn("build", "--argument1", "something")

    Returns: True/False
    """

    if not check_yarn_installed():
        return False

    #
    # Test if args[0] is a list. If it is, then use that to build the command. Else, make the args tuple into a list.
    #
    if type(args[0]) == list:
        cmd = ["yarn"] + args[0]
    else:
        cmd = ["yarn"] + list(args)
    
    loggy.info(f"yarn.yarn(): stdout: {' '.join(cmd)}")
    output = _long_run(' '.join(cmd), check=False)
    loggy.info(f"yarn.yarn(): stdout: {output.stdout}")
    loggy.info(f"yarn.yarn(): stderr: {output.stderr}")
    loggy.info(f"yarn.yarn(): return: {str(output.returncode)}")

    if output.returncode != 0:
        loggy.info("yarn.yarn(): Error.")
        return False

    return True

def build() -> bool:
    return yarn("build")

def install() -> bool:
    return yarn("install")

def check_yarn_installed() -> bool:
    loggy.info("yarn.check_yarn_installed(): BEGIN")
    if not is_command_on_path("yarn"):
        loggy.info("yarn.check_yarn_installed(): Yarn not installed.")
        return False

    return True

def is_command_on_path(command):
    """
    Check if a command is available on the system's PATH.

    :param command: The command to check (e.g., 'python', 'ls').
    :return: True if the command is found, False otherwise.
    """
    return shutil.which(command) is not None