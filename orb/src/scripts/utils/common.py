#!/usr/bin/env python3
"""
common

Common functions

Example Usage:
    from utils import common
"""
import os
import sys
import typing
import subprocess
from subprocess_tee import run
from shlex import join  # type: ignore
import requests

if typing.TYPE_CHECKING:
    CompletedProcess = subprocess.CompletedProcess[typing.Any]  # pylint: disable=E1136
else:
    CompletedProcess = subprocess.CompletedProcess

sys.path.insert(0, '/home/circleci/bin')

import loggy


class ChDir(object):
    def __init__(self, path):
        self.old_dir = os.getcwd()
        self.new_dir = path if len(path) > 0 else os.getcwd()

    def __enter__(self):
        os.chdir(self.new_dir)

    def __exit__(self, *args):
        os.chdir(self.old_dir)

def cancel_workflow() -> bool:
    _CIRCLE_WORKFLOW_ID = get_environ('CIRCLE_WORKFLOW_ID')
    _PIPELINE_TRIGGER_TOKEN = get_environ('PIPELINE_TRIGGER_TOKEN')
    if not _CIRCLE_WORKFLOW_ID or not _PIPELINE_TRIGGER_TOKEN:
        loggy.info("common.cancel_workflow(): Pipeline error. One of CIRCLE_WORKFLOW_ID or PIPELINE_TRIGGER_TOKEN not set on environment.")
        loggy.info("Dumping available ENV vars for debugging:")
        for key, value in os.environ.items():
            loggy.info(f"{key}={value}")
        return False

    loggy.info(f"common.cancel_workflow(): Cancelling workflow: https://circleci.com/api/v2/workflow/{_CIRCLE_WORKFLOW_ID}/cancel")
    x = requests.post(f"https://circleci.com/api/v2/workflow/{_CIRCLE_WORKFLOW_ID}/cancel", headers={"Circle-Token": _PIPELINE_TRIGGER_TOKEN})
    if x.status_code != 202:
        loggy.info(f"common.cancel_workflow():  ERROR canceling workflow. {x.text}")
        return False

    return True

def get_environ(variable: str, default: typing.Optional[str] = None) -> str:
    """
    get_environ()

    This handles getting environnent variables better than the standard os.environ.get()
    There's a case where the ENV var could exist but it is empty, thus it should return the default val.

    Returns: String
    """
    _VAL = os.environ.get(variable, default)
    if not _VAL:
        return default
    return _VAL

def resolve_pipeline_variable(param):
    """
    resolve_pipeline_variable()

    Pipeline variables could get passed in as a literal string.
    Quickly check, resolve and pass back the true environment variable content.
    The `literal string` could be a variable surrounded by characters.

    Examples:
        * $ENV_NAME
        * ${ENV_NAME}
        * my_${ENV_NAME}
        * ${ENV_NAME}_rc
        * hello${ENV_NAME}goodbye

    param: String containing potential env variable

    Returns: String containing resolved env variable or original param if it can't resolve
    """
    _param = None

    if "${" in param and "}" in param:
        if param.startswith("${") and param.endswith("}"):
            _param = removeprefix(param, "${")
            _param = removesuffix(_param, "}")
            _param = os.environ.get(_param, None)
        else:
            m = re.search('\\$\\{(.+?)\\}', param)
            if m:
                found = m.group(1)
                _param = os.environ.get(found, None)
                _param = _param if _param is None else param.replace("${" + found + "}", _param)
    elif param.startswith("$"):
        _param = removeprefix(param, "$")
        _param = os.environ.get(_param, None)

    return _param if _param is not None else param

def add_bash_exports_to_env(file: typing.Optional[str] = None) -> bool:
    """
    add_bash_exports_to_env()

    Given a file with exports in it (i.e. circleCI BASH_ENV file), read in each export and add them to current os.environ

    file: Path to file with exports inside

    Returns: True/False
    """
    loggy.info("add_bash_exports_to_env(): BEGIN")

    if not file:
        file = os.environ.get('BASH_ENV')

    if os.path.exists(file):
        if os.stat(file).st_size != 0:
            with open(file, 'r') as _BASH_ENV:
                for _line in _BASH_ENV.readlines():
                    if _line.startswith('export'):
                        loggy.info(f"add_bash_exports_to_env(): Adding ({_line}) to os.environ")
                        _var, _val = _line.strip().split('export ', 1)[1].split('=', 1)[:2]
                        os.environ[_var] = _val.strip('"')

    return True

def push_export_to_env(export_name: str, export_value: str, file: typing.Optional[str] = None) -> bool:
    """
    push_export_to_env()

    Push an export to an environment file. i.e. cirlcCI BASH_ENV file.

    export_name: String containing desired variable name i.e. "_TRIGGER_PARAMETERS"
    export_value: String containing desired variable value i.e. "amis=ami-123456"
    file: (Optional) Path to file with exports inside. Will default to BASH_ENV for circleCI

    Returns: True/False
    """
    loggy.info("push_export_to_env(): BEGIN")

    if not file:
        file = os.environ.get('BASH_ENV')
    with open(os.environ.get('BASH_ENV'), "a") as _SAVE_BASH_ENV:
        _SAVE_BASH_ENV.write(f"export {export_name}=\"{export_value}\"\n")
    return True


def subprocess_run(args: typing.Union[str, typing.List[str]], **kwargs: typing.Any):
    """
    subprocess_run():

    Replace the default subprocess_tee.run with check=True as default

    * Usage: common.subprocess_run("make install")
    """

    if isinstance(args, str):
        cmd = args
    else:
        # run was called with a list instead of a single item but asyncio
        # create_subprocess_shell requires command as a single string, so
        # we need to convert it to string
        cmd = join(args)

    try:
        my_kwargs = kwargs.copy()
        my_kwargs['check'] = kwargs.get("check", True)
        my_kwargs['shell'] = kwargs.get("shell", True)
        _process_output = run(cmd, **my_kwargs)
    except subprocess.CalledProcessError as e:
        loggy.error(f"common.subprocess_run(): Error: {str(e)}")
        if _process_output and _process_output.stderr:
            loggy.error(f"common.subprocess_run(): Process STDERR: {_process_output.stderr}")

        raise

    return _process_output
    

def subprocess_long(args: typing.Union[str, typing.List[str]], timeout=None, delay=None, check=None, shell=None, env=None):
    """
    subprocess_long():

    imports subprocess_tee

    Run long-running commands that are wrapped into a continuous loggy.info statement to keep
    pipelines from exiting on zero output back to the GoCD server.

    * Usage: common.subprocess_long(cmd="make install", timeout=15, delay=5, check=True)

    timeout defaults to 30 minutes
    delay defaults to 10 seconds
    check defaults to False, use returned output.returncode to check for failure.
        (Set to True if you want this function to error on command failure instead)
    shell defaults to False
    env defaults to None
    """
    timeout = 30 if timeout is None else timeout
    delay = 10 if delay is None else delay
    check = False if check is None else check
    shell = False if shell is None else shell

    if isinstance(args, str):
        cmd = args
    else:
        # run was called with a list instead of a single item but asyncio
        # create_subprocess_shell requires command as a single string, so
        # we need to convert it to string
        cmd = join(args)

    longRunningProcessStart = 'counter=0; while [ $counter -lt ' + \
        str(timeout*60) + \
        ' ]; do counter=$((counter+' + \
        str(delay) + \
        ')); sleep ' + \
        str(delay) + \
        '; echo "common.subprocess_long(): LONG RUNNING PROCESS ENABLED - Running for $counter of ' + \
        str(timeout*60) + \
        ' seconds."; done & export _LONG_RUNNING_PROCESS=$!; '

    longRunningProcessStop = '; retcode=$?; kill $_LONG_RUNNING_PROCESS; exit $retcode'

    _process_output = run(longRunningProcessStart + cmd + longRunningProcessStop, env=env, shell=shell, check=check)

    # loggy.info(_process_output.stdout)
    # loggy.info(_process_output.stderr)
    # loggy.info(_process_output.returncode)
    return _process_output
