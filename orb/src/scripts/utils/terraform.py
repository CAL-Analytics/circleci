#!/usr/bin/env python3
"""
terraform

Common code useful for a Terraform plan/apply.

Example Usage:
    from utils import terraform
    from utils.terraform import plan, apply
"""

import subprocess
import os
import sys
from pathlib import Path
import re
import typing
import glob
import shutil

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import subprocess_long as _long_run, ChDir as _chdir

def plan(properties_env: str, lang: typing.Optional[str] = None, path: typing.Optional[str] = None, poetry_path: typing.Optional[str] = None, poetry_install_cmd: typing.Optional[str] = None) -> bool:
    """
    plan()

    For terraform, runs `plan` using the `tfwrapper` helper script. The function signature is
    preserved for backwards compatibility but the implementation executes terraform via
    `tfwrapper plan` with the provided environment.

    Returns: True/False
    """

    _TARGET_DIR = get_terraform_path(path)
    # _PROPS_FILE = f"properties.{properties_env}.json"
    _TF_PLAN_FILE = f"{os.getcwd()}/tf.plan.txt"

    loggy.info(f"terraform.plan(): Running with target: {_TARGET_DIR}")

    # Ensure terraform is installed (attempt installation if possible)
    if not verify_terraform_installed():
        loggy.info("terraform.plan(): Terraform not available and could not be installed.")
        return False

    aws_session_env = os.environ.copy()
    aws_session_env["ENV"] = properties_env

    # locate the tfwrapper script relative to this file
    # tfwrapper_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bin', 'tfwrapper'))
    tfwrapper_path = shutil.which('tfwrap')
    if not tfwrapper_path:
      loggy.info("terraform.plan(): tfwrap not available and could not be installed.")
      return False

    with _chdir(_TARGET_DIR):
      loggy.info("terraform.plan(): Running tfwrapper plan")
      _process_output = _long_run(
          ['python3', tfwrapper_path, 'plan', '-e', properties_env], env=aws_session_env, check=False)

      loggy.info("----------------------------------")
      loggy.info(f"terraform.plan(): tfwrapper returned {str(_process_output.returncode)}")

    with open(_TF_PLAN_FILE, 'w') as file:
        if _process_output.stderr:
            file.write(_process_output.stderr)

        if _process_output.stdout:
            file.write(_process_output.stdout)

    return _process_output.returncode == 0


def apply(properties_env: str, lang: typing.Optional[str] = None, path: typing.Optional[str] = None, poetry_path: typing.Optional[str] = None, poetry_install_cmd: typing.Optional[str] = None) -> bool:
    """
    apply()

    For terraform, runs `apply` using the `tfwrapper` helper script. The signature is
    preserved for backwards compatibility but the implementation executes terraform via
    `tfwrapper apply` with the provided environment.

    Returns: True/False
    """

    _TARGET_DIR = get_terraform_path(path)
    # _PROPS_FILE = f"properties.{properties_env}.json"
    _TF_APPLY_FILE = f"{os.getcwd()}/tf.apply.txt"

    loggy.info(f"terraform.apply(): Running with target: {_TARGET_DIR}")

    # Ensure terraform is installed
    if not verify_terraform_installed():
        loggy.info("terraform.apply(): Terraform not available and could not be installed.")
        return False

    aws_session_env = os.environ.copy()
    aws_session_env["ENV"] = properties_env

    # tfwrapper_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'bin', 'tfwrapper'))
    tfwrapper_path = shutil.which('tfwrap')
    if not tfwrapper_path:
      loggy.info("terraform.apply(): tfwrap not available and could not be installed.")
      return False

    with _chdir(_TARGET_DIR):
      loggy.info("terraform.apply(): Running tfwrapper apply")
      _process_output = _long_run(
          ['python3', tfwrapper_path, 'apply', '-e', properties_env, '--force'], env=aws_session_env, check=False)

      loggy.info("----------------------------------")
      loggy.info(f"terraform.apply(): tfwrapper returned {str(_process_output.returncode)}")

    with open(_TF_APPLY_FILE, 'w') as file:
        if _process_output.stderr:
            file.write(_process_output.stderr)

        if _process_output.stdout:
            file.write(_process_output.stdout)

    # Return True if the plan/process exited successfully
    return _process_output.returncode == 0


def verify_terraform_installed() -> bool:
    """
    Previously checked for npm. Now ensures `terraform` binary exists. If missing
    we attempt to parse `versions.tf` to extract a required terraform version and try
    to install it via `tfenv` (if available), otherwise fall back to package managers
    when possible.
    """
    loggy.info("terraform.verify_terraform_installed(): BEGIN")

    terraform_path = shutil.which('terraform')
    if terraform_path:
      loggy.info(f"terraform.verify_terraform_installed(): Found terraform at {terraform_path}")
      return True

    # Try to determine required version from versions.tf
    _required = None
    try:
        _required = get_terraform_required_version()
    except Exception:
        _required = None

    # Try tfenv if present
    if shutil.which('tfenv'):
      try:
        if _required:
          # tfenv expects a specific version (strip operators if present)
          # take first numeric-looking section from the constraint
          m = re.search(r"([0-9]+\.[0-9]+(?:\.[0-9]+)?)", _required)
          ver = m.group(1) if m else None
          if ver:
            subprocess.run(['tfenv', 'install', ver], check=True)
            subprocess.run(['tfenv', 'use', ver], check=True)
        else:
          subprocess.run(['tfenv', 'install', 'latest'], check=True)
        # verify
        terraform_path = shutil.which('terraform')
        return bool(terraform_path)
      except Exception:
        loggy.info("terraform.verify_terraform_installed(): tfenv failed to install terraform")

    # Try common package managers (best-effort)
    try:
      if shutil.which('apt'):
        subprocess.run(['sudo', 'apt', 'update'], check=True)
        subprocess.run(['sudo', 'apt', 'install', '-y', 'terraform'], check=True)
      elif shutil.which('brew'):
        subprocess.run(['brew', 'install', 'terraform'], check=True)
      elif shutil.which('yum'):
        subprocess.run(['sudo', 'yum', 'install', '-y', 'terraform'], check=True)
    except Exception:
      loggy.info("terraform.verify_terraform_installed(): package manager installation attempt failed")

    terraform_path = shutil.which('terraform')
    return bool(terraform_path)

def get_terraform_installed_version() -> str:
    """
    get_terraform_installed_version()

    Returns: String representing the installed terraform version, or None
    """

    loggy.info("terraform.get_terraform_installed_version(): BEGIN")

    terraform_path = shutil.which('terraform')
    if terraform_path:
      try:
        process_output = subprocess.run(
            ['terraform', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        out = process_output.stdout.decode() or process_output.stderr.decode()
        # Terraform prints like: Terraform v1.4.0
        m = re.search(r'Terraform v?([0-9]+\.[0-9]+(?:\.[0-9]+)?)', out)
        if m:
          return m.group(1)
      except Exception:
        return None
    return None

def get_terraform_required_version() -> str:
    """
    get_terraform_required_version()

    Parse a `versions.tf` file if present and return the `required_version` constraint string.
    If no file found, fall back to the installed terraform version.
    """
    loggy.info("terraform.get_terraform_required_version(): BEGIN")
    versions_files = glob.glob('**/versions.tf', recursive=True)
    _TF_REQUIRED = None
    if versions_files:
        try:
            content = Path(versions_files[0]).read_text()
            m = re.search(r'required_version\s*=\s*"([^"]+)"', content)
            if m:
                _TF_REQUIRED = m.group(1).strip()
        except Exception:
            _TF_REQUIRED = None
    if not _TF_REQUIRED:
        _TF_REQUIRED = get_terraform_installed_version()

    loggy.info("terraform.get_terraform_required_version(): END")
    return _TF_REQUIRED


def set_terraform_installed_version() -> str:
    """
    set_terraform_installed_version()

    If the required terraform version differs from the installed one, attempt to install
    the required version via `tfenv` or package managers. Returns the required version
    (or 'latest' if undetermined).
    """

    loggy.info("terraform.set_terraform_installed_version(): BEGIN")

    _TF_REQUIRED_VERSION = get_terraform_required_version()
    if not _TF_REQUIRED_VERSION:
      _TF_REQUIRED_VERSION = 'latest'

    _TF_INSTALLED_VERSION = get_terraform_installed_version()

    if _TF_REQUIRED_VERSION:
      loggy.info(
          "terraform.set_terraform_installed_version(): _TF_REQUIRED_VERSION: " + str(_TF_REQUIRED_VERSION))
    if _TF_INSTALLED_VERSION:
      loggy.info("terraform.set_terraform_installed_version(): _TF_INSTALLED_VERSION: " + str(_TF_INSTALLED_VERSION))

    if _TF_REQUIRED_VERSION != _TF_INSTALLED_VERSION:
        # Try tfenv first
        if shutil.which('tfenv'):
          try:
            m = re.search(r"([0-9]+\.[0-9]+(?:\.[0-9]+)?)", _TF_REQUIRED_VERSION)
            ver = m.group(1) if m else None
            if ver:
              subprocess.run(['tfenv', 'install', ver], check=True)
              subprocess.run(['tfenv', 'use', ver], check=True)
          except Exception:
            loggy.info('terraform.set_terraform_installed_version(): tfenv install/use failed')
        else:
          # Best-effort package manager attempt
          try:
            if shutil.which('apt'):
              subprocess.run(['sudo', 'apt', 'update'], check=True)
              subprocess.run(['sudo', 'apt', 'install', '-y', 'terraform'], check=True)
            elif shutil.which('brew'):
              subprocess.run(['brew', 'install', 'terraform'], check=True)
            elif shutil.which('yum'):
              subprocess.run(['sudo', 'yum', 'install', '-y', 'terraform'], check=True)
          except Exception:
            loggy.info('terraform.set_terraform_installed_version(): package manager install attempt failed')

    loggy.info("terraform.set_terraform_installed_version(): END")
    return _TF_REQUIRED_VERSION



def get_terraform_path(path: typing.Optional[str]) -> str:
    if path is not None:
        return path

    terraform_path_env = os.getenv("TERRAFORM_PATH", None)

    if terraform_path_env is not None:
        return terraform_path_env

    # Assumes the terraform path is the directory containing the properties.ENV.json file
    return os.path.dirname(
        glob.glob('**/properties.*.json', recursive=True)[0])
