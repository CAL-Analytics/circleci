#!/usr/bin/env python3
"""
git.py

Common code useful for interacting with git.

Example Usage:
    from utils import git
    from utils.git import checkout
"""
import sys
import typing
import re
from subprocess_tee import run as _run

sys.path.insert(0, '/home/circleci/bin')

import loggy


def checkout(branch):
    """
    git.checkout()

    Check out a specific branch

    branch: String
    """
    loggy.info(f"git.checkout(): Checking out {branch}")
    _run(f"git checkout {branch}", shell=True, check=True)
    _run(f"git pull origin {branch}", shell=True, check=True)

def changes_by_path(path: str, from_commit: typing.Optional[str] = "HEAD^") -> bool:
    """
    git.changes_by_path()

    Check for changes given a regex style path

    path: String - Space separate list of files. Will be converted/used as a regex style for matching.
    from_commit: String - Choose commit to check against, defaults to previous commit (HEAD^)

    Examples: git.changes_by_path(path="^cdk/.* app/something/config.yml") <<<< multiple paths
              git.changes_by_path(path="^app/.*") <<<< single path
    """    
    loggy.info(f"git.changes_by_path(): Checking for changes from commit ({from_commit}) to checked out commit.")
    
    o = _run(f"git diff {from_commit} HEAD --name-only", capture_output=True)

    if o.returncode == 0:
        loggy.info(f"git.changes_by_path(): Commited files list: \n{o.stdout}")
        for line in o.stdout.split('\n'):
            for p in path.split(' '):
                match = re.search(p, line)
                if match:
                    loggy.info(f"git.changes_by_path(): Change in required path found. {line}")
                    return True

    loggy.info("git.changes_by_path(): No changes to files in required path found.")
    return False

def remote_origin_url() -> str:
    """
    git.remote_origin_url()

    Grab the git origin path. It's useful for things like triggering more pipelines to run.

    """
    o = _run(f"git config --get remote.origin.url", capture_output=True)

    _output = None
    if o.returncode == 0:
        loggy.info(f"git.remote_origin_url(): Remore origin url: {o.stdout}")
        _output = o.stdout.strip()
    else:
        loggy.info(f"git.remote_origin_url(): Failed to git remote.origin.url: {o.stderr}")

    return _output