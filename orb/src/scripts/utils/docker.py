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

import subprocess


def docker(*args, env=None, ssh=None) -> bool:
    """
    Shell out to the Docker CLI.

    It is expected that the commands are sent in a single string as if you were typing it on the command line

    Example: docker.docker("build", "-t", "my_container:my_tag", ".")
             docker.docker("build", "-t", "my_container:my_tag", ".", ssh=True)

    Args:
        ssh: If True, sets up ssh-agent and adds --ssh default to build commands

    Returns: True/False
    """

    #
    # Test if args[0] is a list. If it is, then use that to build the command. Else, make the args tuple into a list.
    #
    if type(args[0]) == list:
        cmd = ["docker"] + args[0]
    else:
        cmd = ["docker"] + list(args)

    # Handle SSH support for build commands
    if ssh and "build" in cmd:
        # Set up ssh-agent if not already running
        try:
            # Check if ssh-agent is already running
            result = subprocess.run(["pgrep", "ssh-agent"], capture_output=True, text=True)
            if result.returncode != 0:
                loggy.info("docker.docker(): Setting up ssh-agent")
                # Start ssh-agent
                agent_output = subprocess.run(["ssh-agent", "-s"], capture_output=True, text=True, check=True)
                # Export the environment variables
                for line in agent_output.stdout.split('\n'):
                    if 'SSH_AGENT_PID' in line or 'SSH_AUTH_SOCK' in line:
                        key, value = line.split('=', 1)
                        value = value.rstrip(';')
                        os.environ[key] = value

            # Add SSH key if available
            ssh_key_path = os.environ.get('SSH_KEY_PATH', os.path.expanduser('~/.ssh/id_rsa'))
            if os.path.exists(ssh_key_path):
                loggy.info(f"docker.docker(): Adding SSH key from {ssh_key_path}")
                subprocess.run(["ssh-add", ssh_key_path], check=True)
            else:
                loggy.info("docker.docker(): No SSH key found, attempting to add default key")
                subprocess.run(["ssh-add"], check=False)  # Try to add default key

        except subprocess.CalledProcessError as e:
            loggy.warning(f"docker.docker(): Failed to setup SSH agent/keys: {e}")
            return False

        # Add --ssh default to the docker build command
        cmd.append("--ssh")
        cmd.append("default")
    

    #
    # Show me the ssh-add output
    #
    ssh_add_output = subprocess.run(["ssh-add", "-L"], capture_output=True, text=True)
    loggy.info(f"docker.docker(): ssh-add output: {ssh_add_output.stdout}")
    loggy.info(f"docker.docker(): ssh-add stderr: {ssh_add_output.stderr}")
    loggy.info(f"docker.docker(): ssh-add return: {str(ssh_add_output.returncode)}")

    loggy.info(f"docker.docker(): stdout: {' '.join(cmd)}")
    if env and isinstance(env, dict):
        # grab current env vars and add them together with the env passed in
        _env = os.environ.copy()
        _env.update(env)
        output = _long_run(' '.join(cmd), check=False, env=_env)
    else:
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
