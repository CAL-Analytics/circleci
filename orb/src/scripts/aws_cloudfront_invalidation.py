#!/usr/bin/env python3
"""
aws_cloudfront_invalidation.py

Run a CloudFront Invalidation

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ
from aws import ssm_get_parameter, cloudfront_create_invalidation

loggy.info("aws_cloudfront_invalidation(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_DISTRIBUTION = get_environ('DISTRIBUTION')
_INVALIDATE_ITEMS = get_environ('INVALIDATE_ITEMS')

if not _DISTRIBUTION and not _INVALIDATE_ITEMS:
    loggy.info("aws_cloudfront_invalidation(): Must set parameters for distribution and items list.")
    sys.exit(1)

if _DISTRIBUTION.startswith('/'):
    loggy.info(f"aws_cloudfront_invalidation(): Setting DISTRIBUTION from SSM Param {_DISTRIBUTION}")
    _DIST = ssm_get_parameter(name=_DISTRIBUTION)                                

loggy.info(f"aws_cloudfront_invalidation(): Invalidating {_INVALIDATE_ITEMS} in {_DIST}")
if not cloudfront_create_invalidation(dist=_DIST, items=_INVALIDATE_ITEMS.split(" ")):
    sys.exit(1)

sys.exit(0)

