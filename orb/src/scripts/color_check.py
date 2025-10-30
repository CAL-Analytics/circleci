#!/usr/bin/env python3
"""
color_check

Check if this color is live. If it's live, cancel the pipeline. We only want to deploy to a non-live color.

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ, cancel_workflow
from release import get_inactive_color, FULL_ROUTING
from aws import ssm_get_parameter

loggy.info("color_check(): BEGIN")

#
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_COLOR = get_environ('COLOR')
_RECORD_NAME = get_environ('RECORD_NAME')
_KVS_ARN = get_environ('KVS_ARN')
_KVS_KEY = get_environ('KVS_KEY')

if not _COLOR or (not _RECORD_NAME and not _KVS_ARN and not _KVS_KEY):
    loggy.info("Pipeline error. COLOR or one of RECORD_NAME, KVS, or KVS_KEY not set on environment.")
    loggy.info("Dumping available ENV vars for debugging:")
    for key, value in os.environ.items():
        loggy.info(f"{key}={value}")
    sys.exit(1)

if _KVS_ARN and _KVS_ARN.startswith('/'):
    loggy.info(f"color_check(): Setting KVS_ARN from SSM Param {_KVS_ARN}")
    _KVS_ARN = ssm_get_parameter(name=_KVS_ARN)                                

_inactive_color = get_inactive_color(record_name=_RECORD_NAME, kvs_arn=_KVS_ARN, kvs_key=_KVS_KEY)

if not _COLOR in _inactive_color:
    loggy.info(f"color_check(): Color check failed. We will not deploy to {_COLOR} as it is LIVE.")
    if not cancel_workflow():
        loggy.info(f"color_check(): ERROR canceling workflow. Killing workflow.")
        sys.exit(1)

    #
    # The request above could take up to 5-10 seconds to actually cancel the pipeline
    # which means other steps after this might kick off. To avoid it, let's sleep 30 seconds.
    #
    import time
    time.sleep(30)

loggy.info("color_check(): Color check passed. We will deploy to {_COLOR} as it is NOT LIVE.")

sys.exit(0)