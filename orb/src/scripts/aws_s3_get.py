#!/usr/bin/env python3
"""
aws_s3_get.py

Get file from an AWS S3 Bucket

"""
import os
import sys

sys.path.insert(0, '/home/circleci/bin')

import loggy
from common import add_bash_exports_to_env, get_environ
from aws import s3_get, ssm_get_parameter

loggy.info("aws_s3_get(): BEGIN")

# 
# Every command should check and load any BASH_ENV exports set from other commands.
#
add_bash_exports_to_env()

_S3_BUCKET = get_environ('S3_BUCKET', get_environ('ARTIFACTS_BUCKET'))
_S3_PATH = get_environ('S3_PATH')
_FILE_NAME = get_environ('FILE_NAME')
_EXTRACTED_ROOT = get_environ('EXTRACTED_ROOT')

if not _S3_BUCKET:
    loggy.info("aws_s3_get(): Must set parameters for s3_bucket_from_ssm or s3_bucket. And ARTIFACTS_BUCKET is not set.")
    sys.exit(1)

if _S3_BUCKET.startswith('/'):
    loggy.info(f"aws_s3_get(): Setting S3_BUCKET from SSM Param {_S3_BUCKET}")
    _S3_BUCKET = ssm_get_parameter(name=_S3_BUCKET)                                

if not _S3_BUCKET.startswith('s3://'):
    loggy.info(f"aws_s3_get(): Adding s3:// from S3_BUCKET for boto3 commands.")
    _S3_BUCKET = f"s3://{_S3_BUCKET}"

if not _FILE_NAME:
    loggy.info(f"aws_s3_get(): Setting FILE_NAME to end path of S3_PATH.")
    _FILE_NAME = _S3_PATH.split('/')[-1]

loggy.info(f"aws_s3_get(): Getting {_FILE_NAME} from {_S3_BUCKET}/{_S3_PATH}")

if not s3_get(s3_bucket=_S3_BUCKET, 
            s3_path=_S3_PATH, 
            file_name=_FILE_NAME,
            extracted_root=_EXTRACTED_ROOT):
    sys.exit(1)


sys.exit(0)

