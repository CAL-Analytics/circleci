#!/usr/bin/env python3
"""
cdk

Common code useful for a CDK diff/deploy.

Example Usage:
    from utils import cdk
    from utils.cdk import get_cdk_required_version
"""

import subprocess
import os
import sys
from pathlib import Path
import re
import typing
import glob
import json
import yaml
import shutil

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import subprocess_long as _long_run, ChDir as _chdir

def deploy(properties_env: str, lang: typing.Optional[str] = None, path: typing.Optional[str] = None, poetry_path: typing.Optional[str] = None, poetry_install_cmd: typing.Optional[str] = None) -> bool:
    """
    deploy()

    Runs `cdk deploy` using the properties_env to locate the `properties.env.json` file

    properties_env: String containing env name to locate the properties file
    lang: String representing the type of CDK code to deploy
    path: String (Optional) Will use the CDK_PATH env variable or search for the cdk.json file recursively if this path is not set.
    poetry_path: String (Options) Will use the POETRY_PATH env variable, or default to CDK_PATH if None
    poetry_install_cmd: String (Options) Will use the POETRY_INSTALL_CMD env variable, or default to "poetry install" if None

    Returns: True/False
    """

    _CDK_PATH = get_cdk_path(path)
    _PROPS_FILE = f"properties.{properties_env}.json"
    _CDK_DEPLOY_FILE = f"{os.getcwd()}/cdk.deploy.txt"

    _POETRY_PATH = poetry_path or os.environ.get('POETRY_PATH') or os.environ.get('CIRCLE_WORKING_DIRECTORY') or _CDK_PATH
    _POETRY_INSTALL_CMD = os.environ.get('POETRY_INSTALL_CMD', poetry_install_cmd)
    loggy.info(f"cdk.deploy(): Running with values: _POETRY_PATH {_POETRY_PATH} _POETRY_INSTALL_CMD {_POETRY_INSTALL_CMD}")

    with _chdir(_POETRY_PATH):
      if not install_cdk_requirements(cdk_lang=lang, poetry_install_cmd=_POETRY_INSTALL_CMD):
          loggy.info(
              "cdk.deploy(): Failed to install cdk requirements. Check logs.")
          return False

    with _chdir(_CDK_PATH):
        env_file = Path(_PROPS_FILE).read_text()
        # env_data = json.load(env_file)
        loggy.info(f"cdk.deploy(): {env_file}")

        loggy.info("Setting environment for cdk deploy")
        aws_session_env = os.environ.copy()

        loggy.info("Adding our properties ENV file to the environment")
        aws_session_env["ENV"] = properties_env

        loggy.info("Running CDK bootstrap")
        if not bootstrap_cdk_environment(cdk_lang=lang, aws_session_env=aws_session_env, poetry_install_cmd=_POETRY_INSTALL_CMD):
          loggy.info(
            "cdk.deploy(): Failed to bootstrap cdk environment. Check logs.")
          return False

        loggy.info("Running CDK deploy")
        _process_output = _long_run(
            ['poetry', 'run', 'cdk', 'deploy', '--require-approval', 'never', '--all'], env=aws_session_env, check=False)
        loggy.info("----------------------------------")
        loggy.info(
            f"cdk.deploy(): CDK returned {str(_process_output.returncode)}")

        with open(_CDK_DEPLOY_FILE, 'w') as file:
            if _process_output.stderr:
                file.write(_process_output.stderr)

            if _process_output.stdout:
                file.write(_process_output.stdout)

        if _process_output.returncode != 0:
            return False

    return True


def diff(properties_env: str, lang: typing.Optional[str] = None, path: typing.Optional[str] = None, poetry_path: typing.Optional[str] = None, poetry_install_cmd: typing.Optional[str] = None) -> bool:
    """
    diff()

    Runs `cdk diff` using the properties_env to locate the `properties.env.json` file

    properties_env: String containing env name to locate the properties file
    lang: String representing the type of CDK code to deploy (python, ts, typescript)
    path: String (Optional) Will use the CDK_PATH env variable or search for the cdk.json file recursively if this path is not set.
    poetry_path: String (Options) Will use the POETRY_PATH env variable, or default to CDK_PATH if None
    poetry_install_cmd: String (Options) Will use the POETRY_INSTALL_CMD env variable, or default to "poetry install" if None

    Returns: True/False
    """

    _CDK_PATH = get_cdk_path(path)
    _PROPS_FILE = f"properties.{properties_env}.json"
    _CDK_DIFF_FILE = f"{os.getcwd()}/cdk.diff.txt"

    _POETRY_PATH = poetry_path or os.environ.get('POETRY_PATH') or os.environ.get('CIRCLE_WORKING_DIRECTORY') or _CDK_PATH
    _POETRY_INSTALL_CMD = os.environ.get('POETRY_INSTALL_CMD', poetry_install_cmd)
    loggy.info(f"cdk.diff(): Running with values: _POETRY_PATH {_POETRY_PATH} _POETRY_INSTALL_CMD {_POETRY_INSTALL_CMD}")

    with _chdir(_POETRY_PATH):
      if not install_cdk_requirements(cdk_lang=lang, poetry_install_cmd=_POETRY_INSTALL_CMD):
          loggy.info(
              "cdk.diff(): Failed to install cdk requirements. Check logs.")
          return False

    _EXIT = True
    with _chdir(_CDK_PATH):
        env_file = Path(_PROPS_FILE).read_text()
        # env_data = json.load(env_file)
        loggy.info(f"cdk.diff(): {env_file}")

        loggy.info("Setting environment for cdk deploy")
        aws_session_env = os.environ.copy()

        loggy.info("Adding our properties ENV file to the environment")
        aws_session_env["ENV"] = properties_env

        loggy.info("Running CDK bootstrap")
        if not bootstrap_cdk_environment(cdk_lang=lang, aws_session_env=aws_session_env, poetry_install_cmd=_POETRY_INSTALL_CMD):
          loggy.info(
            "cdk.deploy(): Failed to bootstrap cdk environment. Check logs.")
          return False

        loggy.info("Running CDK diff")
        #
        # CDK finally added a CI option so logs are sent to stdout. 
        #
        _process_output = _long_run(
            ['poetry', 'run', 'cdk', 'diff', '--fail', '--ci', '--verbose'], env=aws_session_env, check=False)
        loggy.info("----------------------------------")
        loggy.info(
            f"cdk.diff(): CDK returned {str(_process_output.returncode)}")
        # loggy.info("----------------------------------")
        # loggy.info(f"cdk.diff(): CDK returned {str(_process_output.stderr)}")
        # loggy.info("----------------------------------")
        # loggy.info(f"cdk.diff(): CDK returned {str(_process_output.stdout)}")
        # loggy.info("----------------------------------")

        if _process_output.returncode != 0:
            loggy.info("cdk.diff(): Testing for CDK Diff or Error.")

            with open(_CDK_DIFF_FILE, 'w') as file:
                file.write(_process_output.stdout)

            if '[~]' in _process_output.stdout or '[+]' in _process_output.stdout or '[-]' in _process_output.stdout or '[=]' in _process_output.stdout:
                loggy.info("cdk.diff(): CDK Diff found!")
                _EXIT = True
            else:
                loggy.info("cdk.diff(): CDK ERROR!")
                for stack in glob.glob('cdk.out/*.json'):
                    loggy.info("----------------------------------")
                    loggy.info("STACK: " + stack)
                    _stack_yaml = yaml.dump(
                        json.loads(Path(stack).read_text()))
                    loggy.info(_stack_yaml)
                _EXIT = False

        else:
            # if 'DEPLOY_OVERRIDE' in os.environ.keys():
            #     print("cdkDiff.__main__(): No CDK diff! Overriding CDK_DIFF because DEPLOY_OVERRIDE")
            #     _EXIT = 0
            # else:
            with open(_CDK_DIFF_FILE, 'w') as file:
                file.write(
                    "NO CDK diff found. This could be an AMI SSM Param change. Deploy proceding.")

            loggy.info(
                "cdk.diff(): NO CDK diff found. This could be an AMI SSM Param change. Deploy proceding.")
            _EXIT = True

    return _EXIT


def diff_pretty(diff_file: str = 'cdk.diff.txt', output_file: str = 'cdk.diff.html', verbose: bool = False) -> bool:

    _CDK_DIFF_FILE = diff_file
    _CDK_HTML_OUTPUT_FILE = output_file
    _VERBOSE = verbose

    html_template = """
<!DOCTYPE html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>prettyplan</title>
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="stylesheet" type="text/css" href="https://cdn.jsdelivr.net/npm/diff2html/bundles/css/diff2html.min.css" />
    <style>
      body {
        font-family: Arial, Helvetica, sans-serif;
        text-rendering: optimizeLegibility;
        background: #ecf7fe;
        color: #000000c0;
        font-size: 15px;
        margin: 0;
      }
      @keyframes fade-in {
        0% {
          opacity: 0;
        }
        100% {
          opacity: 1;
        }
      }
      .stripe {
        width: 100%;
        height: 5px;
        background: #5c4ce4;
        animation-name: wipe-in;
        animation-duration: 1s;
      }
      @keyframes wipe-in {
        0% {
          width: 0%;
        }
        100% {
          width: 100%;
        }
      }
      #release-notification {
        background: #5c4ce4;
        color: white;
        font-weight: bold;
        text-align: center;
        overflow: hidden;
        padding: 10px 0 15px 0;
        height: 20px;
        animation-name: notification-pop-in;
        animation-duration: 2s;
      }
      #release-notification a {
        color: white;
      }
      #release-notification.dismissed {
        animation-name: notification-pop-out;
        animation-duration: 0.5s;
        height: 0;
        padding: 0;
      }
      @keyframes notification-pop-in {
        0% {
          height: 0;
          padding: 0;
        }
        50% {
          height: 0;
          padding: 0;
        }
      }
      @keyframes notification-pop-out {
        0% {
          height: 20px;
          padding: 10px 0 15px 0;
        }
        100% {
          height: 0;
          padding: 0;
        }
      }
      #modal-container {
        animation-name: fade-in;
        animation-duration: 0.2s;
      }
      .modal-pane {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #ffffffe6;
        z-index: 10;
      }
      .modal-content {
        position: fixed;
        width: 60%;
        height: 60%;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: #ffffff;
        box-shadow: 0 2px 6px 0 hsla(0, 0%, 0%, 0.2);
        z-index: 20;
      }
      .modal-close {
        position: absolute;
        right: 0;
        padding: 10px;
      }
      .modal-close button.text-button {
        color: #4526ac;
        text-decoration: none;
        font-weight: normal;
      }
      .release-notes {
        max-width: 80%;
        margin: 0 auto 0 auto;
        overflow-y: auto;
        max-height: 100%;
      }
      #branding {
        float: right;
        padding-top: 10px;
        padding-right: 10px;
        font-size: 10px;
        color: #4526ac;
        text-align: right;
      }
      #branding a {
        color: #4526ac;
      }
      .container {
        margin: 10px 10px 0 10px;
        animation-name: fade-in;
        animation-duration: 1s;
      }
      @media only screen and (min-width: 600px) {
        .container {
          max-width: 80%;
          margin-left: auto;
          margin-right: auto;
        }
      }
      h1,
      h2 {
        text-align: center;
        color: #4526ac;
      }
      #terraform-plan {
        width: 100%;
        min-height: 300px;
        border: none;
        box-shadow: 0 2px 6px 0 hsla(0, 0%, 0%, 0.2);
        padding: 10px;
        margin-bottom: 10px;
        resize: none;
        background: #ffffffe6;
      }
      button {
        font-size: 18px;
        background: #5c4ce4;
        color: #fff;
        box-shadow: 0 2px 6px 0 hsla(0, 0%, 0%, 0.2);
        border: none;
        border-radius: 2px;
        min-width: 170px;
        height: 40px;
      }
      button:hover {
        background: #6567ea;
        cursor: pointer;
      }
      button:active {
        background: #5037ca;
      }
      button.text-button {
        background: none;
        box-shadow: none;
        border-radius: 0;
        width: auto;
        height: auto;
        text-decoration: underline;
        font-size: inherit;
        font-weight: inherit;
        font-family: Arial, Helvetica, sans-serif;
        color: inherit;
        text-align: inherit;
        padding: 0;
      }
      #parsing-error-message {
        background-color: #ffffff;
        padding: 10px;
        color: #000000c0;
        margin: 4px;
        box-shadow: 0 2px 6px 0 hsla(0, 0%, 0%, 0.2);
        font-weight: bold;
        border-left: 2px solid red;
        animation-name: error;
        animation-duration: 1s;
      }
      @keyframes error {
        0% {
          background-color: red;
        }
        100% {
          background-color: white;
        }
      }
      .prettyplan ul {
        padding-left: 0;
        font-size: 13px;
      }
      .prettyplan li {
        list-style: none;
        background: #ffffffe6;
        padding: 10px;
        color: #000000c0;
        margin: 4px;
        box-shadow: 0 2px 6px 0 hsla(0, 0%, 0%, 0.2);
      }
      .prettyplan ul.warnings li {
        border-left: 3px solid #757575;
      }
      .prettyplan ul.actions li.update {
        border-left: 3px solid #ff8f00;
      }
      .prettyplan ul.actions li.create {
        border-left: 3px solid #2e7d32;
      }
      .prettyplan ul.actions li.addition {
        border-left: 3px solid #2e7d32;
      }
      .prettyplan ul.actions li.destroy {
        border-left: 3px solid #b71c1c;
      }
      .prettyplan ul.actions li.removal {
        border-left: 3px solid #b71c1c;
      }
      .prettyplan ul.actions li.recreate {
        border-left: 3px solid #1565c0;
      }
      .prettyplan ul.actions li.read {
        border-left: 3px solid #519bf0;
      }
      .badge {
        display: inline-block;
        text-transform: uppercase;
        margin-right: 10px;
        padding: 3px;
        font-size: 12px;
        font-weight: bold;
      }
      .warnings .badge {
        color: #757575;
      }
      li.update .badge {
        color: #ff8f00;
      }
      li.create .badge {
        color: #2e7d32;
      }
      li.addition .badge {
        color: #2e7d32;
      }
      li.destroy .badge {
        color: #b71c1c;
      }
      li.removal .badge {
        color: #b71c1c;
      }
      li.recreate .badge {
        color: #1565c0;
      }
      li.read .badge {
        color: #519bf0;
      }
      .id-segment:not(:last-child)::after {
        content: ' > ';
      }
      .id-segment.name,
      .id-segment.type {
        font-weight: bold;
      }
      .change-count {
        float: right;
      }
      .summary {
        cursor: pointer;
      }
      .no-diff-changes-breakdown {
        margin: 5px auto 0 auto;
        padding: 5px;
      }
      .no-diff-changes-breakdown table {
        width: 100%;
        word-break: break-all;
        font-size: 13px;
      }
      .no-diff-changes-breakdown table td {
        padding: 10px;
        width: 40%;
      }
      pre {
        white-space: pre-wrap;
        background: #f3f3f3;
      }
      .no-diff-changes-breakdown table td.property {
        width: 20%;
        text-align: right;
        font-weight: bold;
      }
      .no-diff-changes-breakdown table tr:nth-child(even) {
        background-color: #f5f5f5;
      }
      .forces-new-resource {
        color: #b71c1c;
      }
      .collapsed,
      .hidden {
        display: none;
      }
      .actions button {
        background: none;
        border: none;
        text-decoration: underline;
        color: black;
        box-shadow: none;
        font-weight: bold;
        font-size: 14px;
      }
      .d2h-icon {
        display: none;
      }
    </style>
  </head>
  <body>
    <div class="stripe"></div>
    <div class="container">
      <h1>prettyplan</h1>
      <div id="parsing-error-message" class="hidden">
        That doesn't look like a Terraform plan. Did you copy the entire output (without colouring) from the plan
        command?
      </div>
      <div id="prettyplan" class="prettyplan">
        <ul id="errors" class="errors"></ul>
        <ul id="warnings" class="warnings"></ul>
        <button class="expand-all" onclick="expandAll()">Expand all</button>
        <button class="collapse-all hidden" onclick="collapseAll()">Collapse all</button>
        <div id="stacks"></div>
        <ul id="actions" class="actions"></ul>
        <pre id="diff"></pre>
      </div>
    </div>
    <script>
      function accordion(element) {
        const changes = element.parentElement.getElementsByClassName('changes');
        for (var i = 0; i < changes.length; i++) {
          toggleClass(changes[i], 'collapsed');
        }
      }
      function toggleClass(element, className) {
        if (!element.className.match(className)) {
          element.className += ' ' + className;
        } else {
          element.className = element.className.replace(className, '');
        }
      }
      function addClass(element, className) {
        if (!element.className.match(className)) element.className += ' ' + className;
      }
      function removeClass(element, className) {
        element.className = element.className.replace(className, '');
      }
      function expandAll() {
        const sections = document.querySelectorAll('.changes.collapsed');
        for (var i = 0; i < sections.length; i++) {
          toggleClass(sections[i], 'collapsed');
        }
        toggleClass(document.querySelector('.expand-all'), 'hidden');
        toggleClass(document.querySelector('.collapse-all'), 'hidden');
      }
      function collapseAll() {
        const sections = document.querySelectorAll('.changes:not(.collapsed)');
        for (var i = 0; i < sections.length; i++) {
          toggleClass(sections[i], 'collapsed');
        }
        toggleClass(document.querySelector('.expand-all'), 'hidden');
        toggleClass(document.querySelector('.collapse-all'), 'hidden');
      }
      function removeChildren(element) {
        while (element.lastChild) {
          element.removeChild(element.lastChild);
        }
      }
      function createModalContainer() {
        const modalElement = document.createElement('div');
        modalElement.id = 'modal-container';
        document.body.appendChild(modalElement);
        return modalElement;
      }
      function closeModal() {
        const modalElement = document.getElementById('modal-container');
        document.body.removeChild(modalElement);
      }
    </script>
  </body>
</html>
"""

    if _VERBOSE:
        loggy.info("diff_pretty()): BEGIN")

    if not Path(_CDK_DIFF_FILE).exists():
        loggy.info(
            f"diff_pretty(): ERROR. INPUT FILE ({_CDK_DIFF_FILE}) does NOT exist.")
        return False

    if _VERBOSE:
        loggy.info(f"diff_pretty(): Reading input file: {_CDK_DIFF_FILE}")

    cdk_out = Path(_CDK_DIFF_FILE).read_text()

    if _VERBOSE:
        loggy.info(f"diff_pretty(): {cdk_out}")

    #
    # Here, we split the stack output into an array based on `Stack xyz` lines
    #
    stacks = [f"Stack {e}" for e in cdk_out.split('Stack ') if e]

    #
    # This is a Hack to get rid of any warnings at the top of the output before
    # we encounter our first `Stack xyz` line.
    #
    for idx, l in enumerate(stacks):
        match = False
        for hack_line in cdk_out.split('\n'):
            if l.split('\n')[0] in hack_line:
                match = True
                break

        if not match:
            del stacks[idx]
            continue

    #
    # Convert each `Stack xyz` line to our HTML format
    #
    for idx, l in enumerate(stacks):
        new_line = []
        diff_type = ""
        divs_open = 0
        ul_li_open = 0
        for ndx, n in enumerate(l.split('\n')):
            if _VERBOSE:
                loggy.info(
                    f"diff_pretty(): DEBUG: ({str(idx)})-({str(ndx)}) - {str(n)}")

            if ndx == 0:
                # new_line.append(f"<div class=\"stack\"><h2>{n}</h2><div class=\"raw-diff\"><button onclick=\"accordion(this)\">Expand this Stack</button><div class=\"changes\">")

                #
                # 2 open divs
                #
                divs_open += 2
                new_line.append(
                    f"<div class=\"stack\"><h2>{n}</h2><button onclick=\"accordion(this)\">Expand this Stack</button><div class=\"changes\">")
            else:
                if n.startswith('IAM Policy Changes'):
                    diff_type = "IAM"
                elif n.startswith('Resources'):
                    diff_type = "Resources"
                elif n.startswith('Outputs'):
                    diff_type = "Outputs"
                elif n.startswith('There were no differences'):
                    diff_type = "NoDiff"

                if 'Resources' in diff_type or 'Outputs' in diff_type:
                    if n.startswith('[+]'):
                        if ul_li_open > 0:
                            ul_li_open = 0
                            divs_open -= 1
                            new_line.append('<pre></div></li></ul>')

                        ul_li_open += 1
                        divs_open += 1
                        new_line.append(
                            f"<ul class=\"actions\"><li class=\"create\"><div class=\"summary\" onclick=\"accordion(this)\"><span class=\"badge\">Addition</span></div><div class\"changes\"><pre>{n}")
                    elif n.startswith('[-]'):
                        if ul_li_open > 0:
                            ul_li_open = 0
                            divs_open -= 1
                            new_line.append('</pre></div></li></ul>')

                        ul_li_open += 1
                        divs_open += 1
                        new_line.append(
                            f"<ul class=\"actions\"><li class=\"destroy\"><div class=\"summary\" onclick=\"accordion(this)\"><span class=\"badge\">Delete</span></div><div class\"changes\"><pre>{n}")
                    elif n.startswith('[~]'):
                        if ul_li_open > 0:
                            ul_li_open = 0
                            divs_open -= 1
                            new_line.append('</pre></div></li></ul>')

                        ul_li_open += 1
                        divs_open += 1
                        if 'replace' in n or ((len(l)-1) >= ndx+1 and 'replace' in l[ndx+1]):
                            new_line.append(
                                f"<ul class=\"actions\"><li class=\"destroy\"><div class=\"summary\" onclick=\"accordion(this)\"><span class=\"badge\">REPLACEMENT</span></div><div class\"changes\"><pre>{n}")
                        else:
                            new_line.append(
                                f"<ul class=\"actions\"><li class=\"update\"><div class=\"summary\" onclick=\"accordion(this)\"><span class=\"badge\">Update</span></div><div class\"changes\"><pre>{n}")

                    else:
                        new_line.append(f"{n}")

                elif 'IAM' in diff_type:
                    if divs_open <= 2:
                        ul_li_open += 1
                        divs_open += 1
                        new_line.append(
                            f"<ul class=\"actions\"><li class=\"update\"><div class=\"summary\" onclick=\"accordion(this)\"><span class=\"badge\">Update</span></div><div class\"changes\"><pre>{n}")
                    else:
                        new_line.append(f"{n}")

                elif 'NoDiff' in diff_type:
                    if divs_open <= 2:
                        ul_li_open += 1
                        divs_open += 1
                        new_line.append(
                            f"<ul class=\"actions\"><li class=\"read\"><div class=\"summary\" onclick=\"accordion(this)\"><span class=\"badge\">No Diff</span></div><div class\"changes\"><pre>{n}")
                    else:
                        new_line.append(f"{n}")

        while ul_li_open > 0:
            ul_li_open -= 1
            divs_open -= 1
            new_line.append('</pre></div></li></ul>')

        while divs_open > 0:
            divs_open -= 1
            new_line.append('</div>')

        stacks[idx] = '\n'.join(new_line)

    #
    # If there are no stacks, then we can print this as a giant error
    #
    if not stacks:
        print(
            "cdk-diff-pretty.__main__(): ERROR: No stacks found. Outputting diff as ERROR.")
        stacks.append(
            "<div class=\"stack\"><h2>CDK DIFF ERROR</h2><button onclick=\"accordion(this)\">Expand this Stack</button><div class=\"changes\">")
        stacks.append("<ul class=\"actions\"><li class=\"destroy\"><div class=\"summary\" onclick=\"accordion(this)\"><span class=\"badge\">CDK DIFF ERROR</span></div><div class\"changes\"><pre>")
        stacks.append(f"{cdk_out}")
        stacks.append('</pre></div></li></ul>')
        stacks.append('</div></div>')

    html_template = html_template.replace(
        '<h1>prettyplan</h1>', '<h1>CDK Diff</h1>')
    html_template = html_template.replace(
        '<title>prettyplan</title>', '<title>CDK Diff</title>')

    html_template = html_template.replace(
        '<div id="stacks"></div>', f"<div id=\"stacks\">{' '.join(stacks)}</div>")

    if _VERBOSE:
        loggy.info(
            f"diff_pretty(): Writing output file to {_CDK_HTML_OUTPUT_FILE}")

    Path(_CDK_HTML_OUTPUT_FILE).write_text(html_template)
    if _VERBOSE:
        loggy.info("diff_pretty(): END")

    return True

def verify_npm_installed() -> bool:
    """
    verify_npm_installed()

    Ensure npm is installed, if not, install it.
    """
    loggy.info("cdk.verify_npm_installed(): BEGIN")

    npm_path = shutil.which('npm')
    if not npm_path:
      process_output = subprocess.run(
          ['sudo', 'apt', 'update'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
      process_output = subprocess.run(
          ['sudo', 'apt', 'install', 'npm'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    return True

def get_cdk_installed_version() -> str:
    """
    get_cdk_installed_version()

    Get the CDK installed version.

    Returns: String representing the installed version
    """

    loggy.info("cdk.get_cdk_installed_version(): BEGIN")

    cdk_path = shutil.which('cdk')
    if cdk_path:
      process_output = subprocess.run(
          ['cdk', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

      return process_output.stdout.decode().split(' ')[0]
    
    return None

def get_python_version() -> str:
    """
    get_python_version()

    Get the python installed version.

    Returns: String representing the installed version
    """

    loggy.info("cdk.get_python_version(): BEGIN")

    cdk_path = shutil.which('python')
    if cdk_path:
      process_output = subprocess.run(
          ['python', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

      return process_output.stdout.decode().split(' ')[1].strip()
    
    return None

def get_cdk_required_version() -> str:
    """
    get_cdk_required_version()

    Get the CDK required version. If `cdk_lock_version` file exists, pulls the
    version value from there. Otherwise, returns the installed version of CDK.

    Returns: String representing the required version
    """
    loggy.info("cdk.get_cdk_required_version(): BEGIN")
    if os.path.exists('cdk_lock_version'):
        _CDK_REQUIRED_VERSION = Path('cdk_lock_version').read_text().strip()
    else:
        _CDK_REQUIRED_VERSION = get_cdk_installed_version()

    loggy.info("cdk.get_cdk_required_version(): END")
    return _CDK_REQUIRED_VERSION


def set_cdk_installed_version() -> str:
    """
    set_cdk_installed_version()

    Set the CDK installed version. If the required version of CDK is different
    from the installed version, run the npm commands to install the correct
    version.

    Returns: String representing the required version
    """

    loggy.info("cdk.set_cdk_installed_version(): BEGIN")

    verify_npm_installed()

    _CDK_REQUIRED_VERSION = get_cdk_required_version()
    if not _CDK_REQUIRED_VERSION:
      _CDK_REQUIRED_VERSION = 'latest'

    _CDK_INSTALLED_VERSION = get_cdk_installed_version()

    if _CDK_REQUIRED_VERSION:
      loggy.info(
          "cdk.set_cdk_installed_version(): _CDK_REQUIRED_VERSION: " + _CDK_REQUIRED_VERSION)
    if _CDK_INSTALLED_VERSION:
      loggy.info("cdk.set_cdk_installed_version(): _CDK_INSTALLED_VERSION: " +
                _CDK_INSTALLED_VERSION)

    if _CDK_REQUIRED_VERSION != _CDK_INSTALLED_VERSION:
        subprocess.run(['sudo', 'npm', 'install', '-g', 'aws-cdk@' + _CDK_REQUIRED_VERSION],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    loggy.info("cdk.set_cdk_installed_version(): END")
    return _CDK_REQUIRED_VERSION

def bootstrap_cdk_environment(cdk_lang: str, aws_session_env: dict, poetry_install_cmd: typing.Optional[str] = None) -> bool:
    """
    bootstrap_cdk_environment()

    Ensure the AWS account has been bootstrapped.

    cdk_lang: String representing the type of CDK code to deploy

    Returns: True/False
    """
    loggy.info("cdk.bootstrap_cdk_environment(): BEGIN - Force bootstrapping")
    POETRY = "poetry run " if poetry_install_cmd else ""
    # Run Bootstrap to ensure it's up to date
    CDK_BOOTSTRAP_CMD = f"{POETRY}cdk bootstrap".split(' ')

    # Dont check, just run the stupid thing
    subprocess.run(
      CDK_BOOTSTRAP_CMD, check=False, env=aws_session_env)

    loggy.info("cdk.bootstrap_cdk_environment(): END")
    return True


def install_cdk_requirements(cdk_lang: str, poetry_install_cmd: typing.Optional[str] = None) -> bool:
    """
    install_cdk_requirements()

    Install requirements for the specific type/language of cdk deployment.

    cdk_lang: String representing the type of CDK code to deploy

    Returns: True/False
    """
    loggy.info("cdk.install_cdk_requirements(): BEGIN")
    _cdk_required_version = set_cdk_installed_version()
    if cdk_lang == 'python':
        loggy.info(
            "cdk.install_cdk_requirements(): Installing python requirements.")

        if os.path.exists('pyproject.toml') and os.path.exists('poetry.lock'):
            loggy.info(
                "cdk.install_cdk_requirements(): Poetry config files found.")

            python_version = get_python_version()

            subprocess.run(
                ['poetry', 'env', 'use', python_version], check=True)

            #
            # Grab poetry_install_cmd and convert it to a list
            #
            _POETRY_INSTALL_CMD = poetry_install_cmd
            if not _POETRY_INSTALL_CMD:
              _POETRY_INSTALL_CMD = "poetry install".split(' ')
            else:
              _POETRY_INSTALL_CMD = _POETRY_INSTALL_CMD.split(' ')

            subprocess.run(
                _POETRY_INSTALL_CMD, check=True)

        elif os.path.exists('requirements.txt'):
            loggy.info(
                "cdk.install_cdk_requirements(): Installing pips from requirements.txt file.")

            subprocess.run(
                ['pip', 'install', '-r', 'requirements.txt'], check=True)

        elif os.path.exists('setup.py'):
            loggy.info(
                "cdk.install_cdk_requirements(): Install from setup.py file.")

            _file_contents = Path('setup.py').read_text()
            loggy.info(_file_contents)

            #
            # TAW 20220529 - Setting required version changes between cdk v1 and v2
            #
            if _cdk_required_version.startswith('1'):
                loggy.info(
                    "cdk.install_cdk_requirements(): Detected cdk v1. Adding version number to aws_cdk.aws_*.")
                _file_contents = re.sub(
                    'aws_cdk.aws_(.*)"', r'aws_cdk.aws_\1=='+_cdk_required_version+'"', _file_contents)
            elif _cdk_required_version.startswith('2'):
                loggy.info(
                    "cdk.install_cdk_requirements(): Detected cdk v2. Adding version number to aws-cdk-lib*.")
                _file_contents = re.sub(
                    'aws-cdk-lib(.*)"', r'aws-cdk-lib\1=='+_cdk_required_version+'"', _file_contents)
                _file_contents = re.sub(
                    'aws_cdk_lib(.*)"', r'aws_cdk_lib\1=='+_cdk_required_version+'"', _file_contents)
            else:
                loggy.info(
                    "cdk.install_cdk_requirements(): Detected unknown cdk version. You might need to modify cdk.py in gocd library to support this.")

            with open('setup.py', 'w') as file:
                file.write(_file_contents)

            # subprocess.run(['sed', '-i', '-E', '\'s|aws_cdk.aws_(.*)"|aws_cdk.aws_\1=='+_cdk_required_version+'"|g\'', 'setup.py'], check=True)
            # sed -i -E 's|aws_cdk.aws_(.*)"|aws_cdk.aws_\1=='$_CDK_REQUIRED_VERSION'"|g' setup.py

            loggy.info(
                "cdk.install_cdk_requirements(): Modified setup.py file.")
            _new_file_contents = Path('setup.py').read_text()
            loggy.info(_new_file_contents)

            subprocess.run(
                ['pip3', 'install', '-e', '.'], check=True)


        else:
          loggy.info(f"cdk.install_cdk_requirements(): Only supports installing from poetry, setup.py or requirements files.")
          return False

    elif cdk_lang == 'ts' or cdk_lang == 'typescript':
        loggy.info("cdk.install_cdk_requirements(): Installing npm requirements.")
        subprocess.run(['npm', 'install'], check=True)

    else:
        loggy.info(f"cdk_lang ({cdk_lang}) unsupported.")
        return False

    loggy.info("cdk.install_cdk_requirements(): END")
    return True


def get_cdk_path(path: typing.Optional[str]) -> str:
    if path is not None:
        return path

    cdk_path_env = os.getenv("CDK_PATH", None)

    if cdk_path_env is not None:
        return cdk_path_env

    return os.path.dirname(
        glob.glob('**/cdk.json', recursive=True)[0])

