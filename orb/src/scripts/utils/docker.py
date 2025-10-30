#!/usr/bin/env python3
"""
docker

Common code useful for docker.

Example Usage:
    from utils import docker
    from utils.docker import docker
"""
import os
import sys
import typing

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import subprocess_long as _long_run


def docker(*args) -> bool:
    """
    Shell out to the Docker CLI.

    It is expected that the commands are sent in a single string as if you were typing it on the command line

    Example: docker.docker("build", "-t", "my_container:my_tag", ".")

    Returns: True/False
    """

    #
    # Test if args[0] is a list. If it is, then use that to build the command. Else, make the args tuple into a list.
    #
    if type(args[0]) == list:
        cmd = ["docker"] + args[0]
    else:
        cmd = ["docker"] + list(args)
    
    loggy.info(f"docker.docker(): stdout: {' '.join(cmd)}")
    output = _long_run(' '.join(cmd), check=False)
    loggy.info(f"docker.docker(): stdout: {output.stdout}")
    loggy.info(f"docker.docker(): stderr: {output.stderr}")
    loggy.info(f"docker.docker(): return: {str(output.returncode)}")

    if output.returncode != 0:
        loggy.info("docker.docker(): Error.")
        return False

    return True


def check_exists_locally(container, tag) -> bool:
    """
    check_exists_locally()

    Check if a docker image has been pulled down locally.

    container: String containing existing local container with tag "container:tag"
    tag: String containing new tag to add to the local container

    Returns: True/False
    """
    loggy.info(f"docker.check_exists_locally(): Does {container} with {tag} exist locally?")

    if not container or not tag:
        loggy.info(f"docker.check_exists_locally(): Container and tag are required.")
        return False

    cmd = ["docker"] + ["images", f"{container}:{tag}"]
    loggy.info(f"docker.check_exists_locally(): stdout: {' '.join(cmd)}")
    output = _long_run(' '.join(cmd), check=False)
    loggy.info(f"docker.check_exists_locally(): stdout: {output.stdout}")
    loggy.info(f"docker.check_exists_locally(): stderr: {output.stderr}")
    loggy.info(f"docker.check_exists_locally(): return: {str(output.returncode)}")

    if f"{container}" not in output.stdout:
        loggy.info("docker.check_exists_locally(): Container not found locally.")
        return False

    return True


def tag(container, tag) -> bool:
    """
    tag()

    Tag a locally built container.
    Example: tag(container="123456789.dkr.ecr.us-east-1.amazonaws.com/mirrored/timothy:1234", tag="latest")

    container: String containing existing local container with tag "container:tag"
    tag: String containing new tag to add to the local container

    Returns: True/False
    """
    loggy.info(f"docker.tag(): Tagging {container} with {tag}")
    if ':' not in container:
        raise Exception("docker.tag(): container must include tag")

    _c = container.split(':')[0]
    return docker("tag", container, f"{_c}:{tag}")


def login(username, password, repo) -> bool:
    """
    login()

    Log in to an external repo (i.e. ECR)

    username: String
    password: String
    repo: String
    """
    return docker("login", "--username", username, "--password", password, repo)


def logout(repo=None) -> bool:
    """
    logout()

    Log out of an external repo

    ecr: String. If None, log out everywhere
    """
    return docker("logout", repo)
