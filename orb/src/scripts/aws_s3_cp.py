#!/usr/bin/env python3
"""
aws_s3_cp.py

Sync files to an AWS S3 Bucket

"""
import os
import sys
from pathlib import Path

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ
from aws import s3_cp, ssm_get_parameter
from release import get_version

loggy.info("aws_s3_cp(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_S3_BUCKET = get_environ('S3_BUCKET')
_SYNC_FILES = get_environ('SYNC_FILES')
_S3_PATH = get_environ('S3_PATH')
_S3_METADATA = get_environ('S3_METADATA')
_S3_METADATA_DIRECTIVE = get_environ('S3_METADATA_DIRECTIVE')
_S3_CACHE_CONTROL = get_environ('S3_CACHE_CONTROL')
_S3_CONTENT_TYPE = get_environ('S3_CONTENT_TYPE')
_VERSION_FILE = get_environ('VERSION_FILE')

if not _S3_BUCKET :
    loggy.info("aws_s3_cp(): Must set parameters for s3_bucket_from_ssm or s3_bucket.")
    sys.exit(1)

if _S3_BUCKET.startswith('/'):
    loggy.info(f"aws_s3_cp(): Setting S3_BUCKET from SSM Param {_S3_BUCKET}")
    _S3_BUCKET = ssm_get_parameter(name=_S3_BUCKET)                                

if not _S3_BUCKET.startswith('s3://'):
    loggy.info(f"aws_s3_cp(): Adding s3:// from S3_BUCKET for boto3 commands.")
    _S3_BUCKET = f"s3://{_S3_BUCKET}"

loggy.info(f"aws_s3_cp(): Sending files from {_SYNC_FILES} to {_S3_BUCKET}/{_S3_PATH}")

if _S3_METADATA:
    loggy.info(f"aws_s3_cp(): Adding this metadata to each file: {_S3_METADATA}")

if _S3_METADATA_DIRECTIVE:
    loggy.info(f"aws_s3_sync(): Adding this metadata directive to each file: {_S3_METADATA_DIRECTIVE}")

if _S3_CACHE_CONTROL:
    loggy.info(f"aws_s3_sync(): Adding this cache control to each file: {_S3_CACHE_CONTROL}")

if _S3_CONTENT_TYPE:
    loggy.info(f"aws_s3_sync(): Adding this content type to each file: {_S3_CONTENT_TYPE}")

if _VERSION_FILE:
    _version = get_version()
    p = Path(_SYNC_FILES)
    if p.is_dir():
        loggy.info(f"aws_s3_sync(): Version file only works currently with a single file not a folder.")
        sys.exit(1)
    loggy.info(f"aws_s3_sync(): Versioning file {_SYNC_FILES} with get_version()")
    new_filename = f"{p.stem}-{_version}{p.suffix}" 
    new_path = p.parent / new_filename
    loggy.info(f"aws_s3_sync(): Renaming {_SYNC_FILES} with new version {new_path}")
    p.rename(new_path)
    _SYNC_FILES = new_path

if not s3_cp(s3_bucket=_S3_BUCKET, 
            s3_path=_S3_PATH, 
            files=_SYNC_FILES, 
            s3_metadata=_S3_METADATA, 
            s3_metadata_directive=_S3_METADATA_DIRECTIVE, 
            s3_cache_control=_S3_CACHE_CONTROL,
            s3_content_type=_S3_CONTENT_TYPE):
    sys.exit(1)

sys.exit(0)

