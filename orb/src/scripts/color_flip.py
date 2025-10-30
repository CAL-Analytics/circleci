#!/usr/bin/env python3
"""
color_flip

Flip color to live

"""
import os
import sys
import json

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ
from release import get_version, get_routing_info, set_active_color, FULL_ROUTING
from aws import ssm_get_parameter, cloudfront_get_kvs_key

loggy.info("color_flip(): BEGIN")

#
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_COLOR = get_environ('COLOR')
_RECORD_NAME = get_environ('RECORD_NAME')
_KVS_ARN = get_environ('KVS_ARN')
_KVS_KEY = get_environ('KVS_KEY')

if not _COLOR or (not _RECORD_NAME and not _KVS_ARN and not _KVS_KEY):
    loggy.info("color_flip(): Pipeline error. COLOR or one of RECORD_NAME, KVS, or KVS_KEY not set on environment.")
    loggy.info("color_flip(): Dumping available ENV vars for debugging:")
    for key, value in os.environ.items():
        loggy.info(f"{key}={value}")
    sys.exit(1)

if _KVS_ARN and _KVS_ARN.startswith('/'):
    loggy.info(f"color_flip(): Setting KVS_ARN from SSM Param {_KVS_ARN}")
    _KVS_ARN = ssm_get_parameter(name=_KVS_ARN)                                

#
# Set up our info dict for writing the new color to the routing TXT record
#
if _KVS_ARN:
    info = cloudfront_get_kvs_key(kvs_arn=_KVS_ARN, kvs_key=_KVS_KEY)
    if info.startswith('{'):
        info = json.loads(info.replace("'", '"'))
else:
    info = get_routing_info(record_name=_RECORD_NAME)

info[_COLOR] = get_version()
info['weight'] = FULL_ROUTING[_COLOR]

if not set_active_color(info=info, record_name=_RECORD_NAME, kvs_arn=_KVS_ARN, kvs_key=_KVS_KEY):
    loggy.info(f"color_flip(): Failed to flip {_COLOR} to LIVE.")
    sys.exit(1)

loggy.info("color_flip(): LIVE Color flipped to {_COLOR}.")
sys.exit(0)