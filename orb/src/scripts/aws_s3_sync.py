#!/usr/bin/env python3
"""
aws_s3_sync.py

Sync files to an AWS S3 Bucket

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ
from aws import s3_sync, ssm_get_parameter

loggy.info("aws_s3_sync(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_S3_BUCKET = get_environ('S3_BUCKET')
_SYNC_FILES = get_environ('SYNC_FILES')
_S3_PATH = get_environ('S3_PATH')
_NO_DELETE = get_environ('NO_DELETE')
_S3_METADATA = get_environ('S3_METADATA')
_S3_METADATA_DIRECTIVE = get_environ('S3_METADATA_DIRECTIVE')
_S3_CACHE_CONTROL = get_environ('S3_CACHE_CONTROL')

if not _S3_BUCKET :
    loggy.info("aws_s3_sync(): Must set parameters for s3_bucket_from_ssm or s3_bucket.")
    sys.exit(1)

if _S3_BUCKET:
    loggy.info(f"aws_s3_sync(): Setting S3_BUCKET from SSM Param {_S3_BUCKET}")
    _S3_BUCKET = ssm_get_parameter(name=_S3_BUCKET)                                

loggy.info(f"aws_s3_sync(): Sending files from {_SYNC_FILES} to s3://{_S3_BUCKET}/{_S3_PATH}")

if _S3_METADATA:
    loggy.info(f"aws_s3_sync(): Adding this metadata to each file: {_S3_METADATA}")

if _S3_METADATA_DIRECTIVE:
    loggy.info(f"aws_s3_sync(): Adding this metadata directive to each file: {_S3_METADATA_DIRECTIVE}")

if _S3_CACHE_CONTROL:
    loggy.info(f"aws_s3_sync(): Adding this cache control to each file: {_S3_CACHE_CONTROL}")

if not s3_sync(s3_bucket=f"s3://{_S3_BUCKET}", 
            s3_path=_S3_PATH, 
            files=_SYNC_FILES, 
            no_delete=_NO_DELETE, 
            s3_metadata=_S3_METADATA, 
            s3_metadata_directive=_S3_METADATA_DIRECTIVE, 
            s3_cache_control=_S3_CACHE_CONTROL):
    sys.exit(1)

sys.exit(0)

