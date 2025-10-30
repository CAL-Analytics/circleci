#!/usr/bin/env python3
"""
aws

Common code useful for AWS functions.

2024-12-09 TAW - Initial Version

Example Usage:
    from utils import aws
    from utils.aws import ssm_get_parameter
"""
import contextlib
import boto3
import json
import os
import sys
import base64
import time
import typing
import logging
import uuid
import shutil
from configparser import ConfigParser

sys.path.insert(0, '/home/circleci/bin')

import loggy
from docker import docker as _docker, login as _docker_login
from common import subprocess_long as _long_run

from subprocess_tee import run as _run

class AwsCreds():
    access_key = None
    secret_access_key = None
    session_token = None
    region = None


class AwsSession():
    session = None
    creds = None
    name = None

    def __init__(self, name):
        self.creds = AwsCreds()
        self.name = name
        self.session = None

boto3.set_stream_logger('', logging.INFO)

ECR_ACCOUNT_ID = os.environ.get('ECR_ACCOUNT_ID')
ECR_ACCOUNT_REGION = os.environ.get('ECR_ACCOUNT_REGION', os.environ.get('AWS_DEFAULT_REGION', None))

"""
Global Utils
"""

def init_session() -> AwsSession:
    """
    init_session()

    This function initializes a boto3 AWS session for use in boto3 clients, using
    the pipeline environment credentials.

    It will prefer an IAM Role before attempting to use IAM User Keys

    Returns a reusable AwsSession object
    """
    _s = AwsSession("cicd")


    if os.environ.get('AWS_ROLE_ARN'):
        loggy.info("aws.init_session(): Generating boto3 default session from Iam Role and Web Identity Token File")

        web_identity_token = os.environ.get('CIRCLE_OIDC_TOKEN_V2')
                       
        if os.environ.get('AWS_WEB_IDENTITY_TOKEN_FILE'):            
            with open(os.getenv("AWS_WEB_IDENTITY_TOKEN_FILE"), "r") as content_file:
                web_identity_token = content_file.read()
        
        if not web_identity_token:
            loggy.info(f"aws.init_session(): No CIRCLE_OIDC_TOKEN_V2 or AWS_WEB_IDENTITY_TOKEN_FILE found. Cannot log into AWS.")
            return None
            
        sts_client = boto3.client('sts')
        assumed_role_object = sts_client.assume_role_with_web_identity(
                RoleArn=os.environ.get('AWS_ROLE_ARN'),
                WebIdentityToken=web_identity_token,
                RoleSessionName="AssumeRoleSessionCICDRole"
            )

        loggy.info(f"aws.init_session(): Assumed Role object: {str(assumed_role_object)}")

        # From the response that contains the assumed role, get the temporary 
        # credentials that can be used to make subsequent API calls
        credentials=assumed_role_object['Credentials']
        # loggy.info(f"aws.init_session(): Credentials: {str(credentials)}")


        _s.creds.access_key = credentials['AccessKeyId']
        _s.creds.secret_access_key = credentials['SecretAccessKey']
        _s.creds.session_token = credentials['SessionToken']
        _s.creds.region = os.environ.get('AWS_DEFAULT_REGION', "us-east-1")

        _s.session = boto3.Session(
            aws_access_key_id=_s.creds.access_key,
            aws_secret_access_key=_s.creds.secret_access_key,
            aws_session_token=_s.creds.session_token,
            region_name=_s.creds.region
        )

        # Define the path to the credentials file
        aws_dir = os.path.expanduser("~/.aws")
        credentials_path = os.path.join(aws_dir, "credentials")

        # Ensure the ~/.aws directory exists
        if not os.path.exists(aws_dir):
            os.makedirs(aws_dir)
            print(f"Created directory: {aws_dir}")

        # Write the credentials to the ~/.aws/credentials file
        config = ConfigParser()

        # Read existing credentials if the file already exists
        if os.path.exists(credentials_path):
            config.read(credentials_path)

        # Add the new profile with temporary credentials
        config['default'] = {
            "aws_access_key_id": _s.creds.access_key,
            "aws_secret_access_key": _s.creds.secret_access_key,
            "aws_session_token": _s.creds.session_token,
            "region": _s.creds.region,
        }

        # Write back to the credentials file
        with open(credentials_path, "w") as f:
            config.write(f)


    elif os.environ.get('AWS_PROFILE'):
        loggy.info("aws.init_session(): Generating boto3 default session from AWS_PROFILE")
        _s.creds.access_key = None
        _s.creds.secret_access_key = None

        _s.session = boto3.Session(
            profile_name=os.environ.get('AWS_PROFILE'),
            region_name=_s.creds.region)

    elif os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('AWS_SECRET_ACCESS_KEY') and os.environ.get('AWS_SESSION_TOKEN'):
        loggy.info("aws.init_session(): Generating boto3 default session from accesskey, secret and session")
        # loggy.info("aws.init_session(): Generating boto3 default session")
        _s.creds.access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        _s.creds.secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        _s.creds.session_token = os.environ.get('AWS_SESSION_TOKEN')
        _s.creds.region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

        _s.session = boto3.Session(
            aws_access_key_id=_s.creds.access_key,
            aws_secret_access_key=_s.creds.secret_access_key,
            aws_session_token=_s.creds.session_token,
            region_name=_s.creds.region)

    elif os.environ.get('AWS_ACCESS_KEY_ID') and os.environ.get('AWS_SECRET_ACCESS_KEY'):
        loggy.info("aws.init_session(): Generating boto3 default session from accesskey and secret")
        _s.creds.access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        _s.creds.secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        _s.creds.region = os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')

        _s.session = boto3.Session(
            aws_access_key_id=_s.creds.access_key,
            aws_secret_access_key=_s.creds.secret_access_key,
            region_name=_s.creds.region)

    return _s

def get_aws_account_id(session: typing.Optional[AwsSession] = None) -> str:
    """
    get_aws_account_id()

    Get the aws account ID using the local AWS_ACCESS_KEY_ID credentials.

    session will either be pre-created and sent in as argument, or one will be made for you.
    """
    _s = init_session() if session is None else session

    loggy.info(f"aws.get_aws_account_id(): BEGIN (using session named: {_s.name})")

    try:
        client = _s.session.client('sts')
        # response = client.get_access_key_info(AccessKeyId=_s.creds.access_key)
        response = client.get_caller_identity()
        if 'Account' not in response:
            loggy.error("Error: Account ID not returned")
    except Exception as e:
        loggy.error("Error: " + str(e))

    return response['Account']


def get_region(session: typing.Optional[AwsSession] = None) -> str:
    """
    get_region()

    Get the aws region from the session.

    session will use a different session to build the client, default is global _sessions
    """
    _s = init_session() if session is None else session

    loggy.info(f"aws.get_region(): BEGIN (using session named: {_s.name})")

    return _s.session.region_name


def get_session(session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None):
    """
    get_session()

    Get the aws session that was instantiated on import. This will be tied to
    the local pipeline environment. Useful if you want to build out your own
    boto3 clients to run commands that aren't yet supported in this library.

    returns: boto3.Session() object
    """
    _s = init_session() if session is None else session

    loggy.info(f"aws.get_session(): BEGIN (using session named: {_s.name})")
    return _s.session


def get_session_env(session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None):
    """
    get_session_env()

    Get the aws session credentials that was instantiated on import. This will be tied to
    the local pipeline environment. Useful if you want to build out your own
    boto3 clients to run commands that aren't yet supported in this library.

    returns: new os.environ.copy() modified with session credentials
    """
    _s = init_session() if session is None else session
    loggy.info(f"aws.get_session(): BEGIN (using session named: {_s.name})")

    new_env = os.environ.copy()
    new_env['AWS_ACCESS_KEY_ID'] = _s.creds.access_key
    new_env['AWS_SECRET_ACCESS_KEY'] = _s.creds.secret_access_key
    new_env['AWS_SESSION_TOKEN'] = _s.creds.session_token
    new_env['AWS_DEFAULT_REGION'] = _s.creds.region

    return new_env



"""
CloudFront Utils
"""


def cloudfront_create_invalidation(dist: str, items: typing.Optional[list] = ["/*"], session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> bool:
    """
    cloudfront_create_invalidation()

    Create an invalidation on a CloudFront distribution.

    dist: String Distribution ID
    items: List of paths. Defualts to ["/*"]. (i.e. ["/hello /path/to/file /another/*"])
    session: will use a different session to build the client, default is _sessions

    returns invalidation_id (String)
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region
    loggy.info(f"aws.cloudfront_create_invalidation(): BEGIN (using session named: {_s.name})")

    try:
        client = _s.session.client('cloudfront', region_name=_r)
        response = client.create_invalidation(
            DistributionId=dist,
            InvalidationBatch={
                'Paths': {
                    'Quantity': len(items),
                    'Items': items
                },
                'CallerReference': str(time.time()).replace(".", "")
            }
        )
        invalidation_id = response['Invalidation']['Id']
        loggy.info(f"aws.cloudfront_create_invalidation(): Invalidation ID: {invalidation_id}")
    except Exception as e:
        loggy.error("Error: " + str(e))
        return False

    return True


def cloudfront_get_kvs_key(kvs_arn: str, kvs_key: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> str:
    """
    cloudfront_get_kvs_key()

    Get the info for a KVS key.

    kvs_arn: String KVS ARN
    kvs_key: String KVS Key
    session: will use a different session to build the client, default is _sessions

    returns kvs_key_info (str) or None if the key is not found
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region
    loggy.info(f"aws.cloudfront_get_kvs_key(): BEGIN (using session named: {_s.name})")

    value = None
    try:
        client = _s.session.client('cloudfront-keyvaluestore', region_name=_r)
        response = client.get_key(
            KvsARN=kvs_arn,
            Key=kvs_key
        )
        loggy.info(f"aws.cloudfront_get_kvs_key(): KVS Key Info: {response}")
        value = response['Value']
    except Exception as e:
        loggy.error("Error: " + str(e))

    return value


def cloudfront_get_kvs_etag(kvs_arn: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> str:
    """
    cloudfront_get_kvs_etag()

    Get the etag for a KVS.

    kvs_arn: String KVS ARN
    session: will use a different session to build the client, default is _sessions

    returns etag (str) or None if the KVS is not found
    """

    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region
    loggy.info(f"aws.cloudfront_get_kvs_etag(): BEGIN (using session named: {_s.name})")

    etag = None
    try:
        client = _s.session.client('cloudfront-keyvaluestore', region_name=_r)
        response = client.describe_key_value_store(
            KvsARN=kvs_arn
        )
        etag = response['ETag']
    except Exception as e:
        loggy.error("Error: " + str(e))

    return etag


def cloudfront_update_kvs_key(kvs_arn: str, kvs_key: str, value: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> bool:
    """
    cloudfront_update_kvs_key()

    Update a KVS key.

    kvs_arn: String KVS ARN
    kvs_key: String KVS Key
    value: String Value to set
    session: will use a different session to build the client, default is _sessions

    returns True/False
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region
    loggy.info(f"aws.cloudfront_update_kvs_key(): BEGIN (using session named: {_s.name})")

    try:
        etag = cloudfront_get_kvs_etag(kvs_arn=kvs_arn, session=_s, region=_r)
        if not etag:
            loggy.error("Error: ETag not found for KVS")
            return False

        client = _s.session.client('cloudfront-keyvaluestore', region_name=_r)
        response = client.put_key(
            KvsARN=kvs_arn,
            Key=kvs_key,
            Value=value,
            IfMatch=etag
        )
        loggy.info(f"aws.cloudfront_update_kvs_key(): KVS Key Info: {response}")
    except Exception as e:
        loggy.error("Error: " + str(e))
        return False

    return True


"""
ECR UTILS
"""


def ecr_get_account_id(session: typing.Optional[AwsSession] = None):
    """
    ecr_get_account_id()

    Determine the ECR account Id. Fallback to the session account.    
    """
    if ECR_ACCOUNT_ID:
        return ECR_ACCOUNT_ID

    _s = init_session() if session is None else session
    return get_aws_account_id(_s)


def ecr_get_region(session: typing.Optional[AwsSession] = None):
    """
    ecr_get_region()

    Determine the ECR region. Fallback to the session account.    
    """
    if not ECR_ACCOUNT_REGION:
        _s = init_session() if session is None else session
        return _s.session.region_name

    return ECR_ACCOUNT_REGION

def ecr_login_build(registry_id: typing.Optional[str] = None, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> bool:
    """
    ecr_login_build()

    Removed old function that logged into a different account with special build creds. 
    We are :cowboy:'s at this company.

    returns ecr_login()
    """
    return ecr_login(registry_id=registry_id, session=session, region=region)

def ecr_login(registry_id: typing.Optional[str] = None, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> bool:
    """
    ecr_login()

    Authenticate Docker against an ECR repository.

    Default: Authenticate using _sessions (current environment) to pull/push there.

    registry_id: Authenticate to a different registry_id (aka AWS ECR)
    session: will use this session to build the client, default is _sessions
    region: will use a specfic region to build the client, default is _sessions.region_name

    Returns: True/False
    """
    loggy.info("aws.ecr_login(): BEGIN")

    _s = init_session() if session is None else session
    _r = ecr_get_region(_s) if region is None else region
    _reg = ecr_get_account_id(_s) if registry_id is None else registry_id

    loggy.info(f"aws.ecr_login(): BEGIN (using session named: {_s.name})")

    try:
        loggy.info(f"aws.ecr_login(): registry_id ({_reg}) region ({_r})")
        client = _s.session.client('ecr', region_name=_r)
        response = client.get_authorization_token(registryIds=[_reg])
    except Exception as e:
        loggy.error("Error: " + str(e))
        raise

    try:
        auth = response["authorizationData"][0]
    except (IndexError, KeyError):
        raise RuntimeError("Unable to get authorization token from ECR!")
    except Exception as e:
        loggy.error("Error: " + str(e))
        raise

    auth_token = base64.b64decode(auth["authorizationToken"]).decode()
    username, password = auth_token.split(":")

    return _docker_login(username=username, password=password, repo=auth["proxyEndpoint"])


def ecr_generate_build_fqcn(container: str, registry_id: typing.Optional[str] = None, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> [str, str]:
    """
    ecr_generate_build_fqcn()

    Generate a fully qualified aws docker container string for build account
    (i.e. 552324424.dkr.ecr.us-east-1.amazonaws.com/mirrored/timothy)

    container: String representing container name:tag

    Returns: String container and String tag (None if tag doesn't exist)
    """
    _s = init_session() if session is None else session
    loggy.info(f"aws.ecr_generate_build_fqcn(): BEGIN (using session named: {_s.name})")
    return ecr_generate_fqcn(container=container, registry_id=registry_id, session=_s, region=region)


def ecr_generate_fqcn(container: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None, registry_id: typing.Optional[str] = None) -> [str, str]:
    """
    ecr_generate_fqcn()

    Generate a fully qualified aws docker container string based on current session Credentials
    (i.e. 552324424.dkr.ecr.us-east-1.amazonaws.com/mirrored/timothy)

    container: String representing container name:tag

    Returns: String container and String tag (None if tag doesn't exist)
    """
    if "dkr.ecr" in container:
        loggy.info(f"aws.ecr_generate_fqcn(): ECR URL already exists: {container}. Stripping container and creating a new ECR URL")
        container = ecr_strip_container_name(container=container)
        # return container.split(':')

    _s = init_session() if session is None else session
    _r = ecr_get_region(_s) if region is None else region
    _reg = ecr_get_account_id(_s) if registry_id is None else registry_id

    loggy.info(f"aws.ecr_generate_fqcn(): BEGIN (using session named: {_s.name})")

    loggy.info(f"aws.ecr_generate_fqcn(): Generated ECR URL: {_reg}.dkr.ecr.{_r}.amazonaws.com/{container}")

    _ret = f"{_reg}.dkr.ecr.{_r}.amazonaws.com/{container}".split(':')
    if len(_ret) < 2:
        return _ret[0], None

    return _ret[0], _ret[1]


def ecr_push(container: str, tag: str, tag_list: typing.Optional[list] = None, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> bool:
    """
    ecr_push()

    Push a new container to build account ECR

    container: String representing container name
    tag: String with existing local tag for container name
    tag_list: Optional String List of additional tags to push with the container
    session: will use a different session to build the client, default is build session

    Returns: True/False
    """
    _s = init_session() if session is None else session
    loggy.info(f"aws.ecr_push(): BEGIN (using session named: {_s.name})")
    ecr_login(session=_s)

    #
    # First, let's add any additional tags from tag_list to the docker image
    #
    for _tag in tag_list:
        loggy.info(f"aws.ecr_push(): Adding Tag {_tag} to {container}")
        if not _docker("tag", f"{container}:{tag}", f"{container}:{_tag}"):
            return False

    #
    # Push all tags at once to save time in pipelines
    #
    loggy.info(f"aws.ecr_push(): Pushing {container} with all tags to ECR.")
    if not _docker("push", container, "--all-tags"):
        return False

    return True


def ecr_strip_container_name(container: str) -> str:
    """"
    ecr_strip_container_name()

    Remove prefix of repo url from the repo name itself

    container: String like "575815261832.dkr.ecr.******.amazonaws.com/mirrored/amazoncorretto"

    Returns: String containing just container like "mirrored/amazoncorretto"
    """
    if 'amazonaws' in container:
        _new = container.split('/')
        del _new[0]
        return '/'.join(_new)

    return container


def ecr_get_manifest(container: str, tag: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> str:
    """
    ecr_get_manifest()

    Get the image manifest for a remote container and tag

    container: String representing container name
    tag: String tag to look up
    session: will use a different session to build the client, default is build session
    region: will use a different region to build the client, default is build region

    Returns: String containing image manifest
    """
    _s = init_session() if session is None else session
    _r = ecr_get_region(_s) if region is None else region
    loggy.info(f"aws.ecr_get_manifest(): BEGIN (using session named: {_s.name})")

    client = _s.session.client('ecr', region_name=_r)

    manifest = None
    try:
        response = client.batch_get_image(
            registryId=ecr_get_account_id(_s),
            repositoryName=ecr_strip_container_name(container),
            imageIds=[
                {
                    'imageTag': tag
                }
            ]
            # acceptedMediaTypes=['application/vnd.docker.distribution.manifest.v2+json'],
        )
        loggy.info(str(response))
        manifest = response['images'][0]['imageManifest']
        loggy.info(f"aws.ecr_get_manifest(): Found manifest {manifest}.")
    except Exception as e:
        loggy.info(f"aws.ecr_get_manifest(): Failed to retrieve manifest: {str(e)}")
        return manifest

    return manifest


def ecr_put_image(container: str, tag: str, manifest: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> bool:
    """
    ecr_put_image()

    Put an image manifest for a remote container and tag. Used for re-tagging an
    existing image

    container: String representing container name
    tag: String new tag to add to image
    manifest: String manifest of image
    session: will use a different session to build the client, default is build session
    region: will use a different region to build the client, default is build region

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = ecr_get_region(_s) if region is None else region
    loggy.info(f"aws.ecr_put_image(): BEGIN (using session named: {_s.name})")

    client = _s.session.client('ecr', region_name=_r)

    try:
        client.put_image(
            registryId=ecr_get_account_id(_s),
            repositoryName=ecr_strip_container_name(container),
            imageTag=tag,
            imageManifest=manifest
        )
        # loggy.info(str(response))
        loggy.info("aws.ecr_put_image(): Successfully put new image.")
    except Exception as e:
        if 'already exists' in str(e):
            loggy.info(f"aws.ecr_put_image(): Image already exists. Passing. {str(e)}")
            return True
        else:
            loggy.info(f"aws.ecr_put_image(): Failed to put image: {str(e)}")
            return False

    return True

def ecr_tag(container: str, tag: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> bool:
    """
    ecr_tag()

    Add a Tag to an existing remote ecr container.
    Example: ecr_tag(container="123456789.dkr.ecr.us-east-1.amazonaws.com/mirrored/timothy:1234", tag="latest")

    container: String containing existing remote container with tag "container:tag"
    tag: String containing new tag to add to the local container

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = ecr_get_region(_s) if region is None else region

    loggy.info(f"aws.ecr_tag(): BEGIN (using session named: {_s.name})")

    loggy.info(f"aws.ecr_tag(): Tagging {container} with {tag}")
    if ':' not in container:
        raise Exception("aws.ecr_tag(): container must include tag")

    _c, _t = ecr_generate_fqcn(container=container, session=_s, region=_r)

    manifest = ecr_get_manifest(container=_c, tag=_t, session=_s, region=_r)

    if ecr_put_image(container=_c, tag=tag, manifest=manifest, session=_s, region=_r):
        loggy.info("aws.ecr_tag(): Successfully added tag to image")
    else:
        loggy.info("aws.ecr_tag(): Failed to add new tag to image")
        return False

    return True



"""
S3 Utils
"""


def s3_sync(s3_bucket: str, 
            s3_path: str, 
            files: str, 
            no_delete: typing.Optional[bool] = False, 
            s3_metadata: typing.Optional[str] = None, 
            s3_metadata_directive: typing.Optional[str] = None,
            s3_cache_control: typing.Optional[str] = None,
            session: typing.Optional[AwsSession] = None,
            region: typing.Optional[str] = None) -> bool:
    """
    s3_sync()

    Authenticate against S3 in the current environment/account and sync files.

    s3_bucket: the bucket to sync files into. This should exist in the account you're pipeline runs under.
    s3_path: the path inside of the artifactory s3 bucket to place files
    files: a string containing either a single file or a folder containing all files you want pushed.
    no_delete: True/False (Default: False - delete files on target that do not exist in source)
    s3_metadata: String containing any metadata to add to the files. i.e. "Cache-Control=public, max-age=31536000"
    s3_metadata_directive: String specifying whether data is COPY'ed or REPLACE'd. Default is REPLACE
    s3_cache_control: String containing any cache-control information to add to the files. i.e. "max-age=86400"
    session: will use this session to build the client, default is _sessions
    region: will use a specific region to build the client, default is _sessions.region_name

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.s3_sync(): BEGIN (using session named: {_s.name})")

    new_env = get_session_env(_s)

    s3_full_path = f"{s3_bucket}/{s3_path}/"

    optional_delete = "" if no_delete else "--delete"

    _metadata = "" if not s3_metadata else f"--metadata \"{s3_metadata}\""
    _cache_control = "" if not s3_cache_control else f"--cache-control \"{s3_cache_control}\""
    _metadata_directive = "--metadata-directive REPLACE" if _cache_control else ""
    if _metadata and not _cache_control:
        _metadata_directive = "--metadata-directive REPLACE" if not s3_metadata_directive else f"--metadata-directive {s3_metadata_directive}"
    loggy.info(f"aws s3 sync {optional_delete} {files} {s3_full_path} {_cache_control} {_metadata} {_metadata_directive}")
    output = _run(f"aws s3 sync {optional_delete} {files} {s3_full_path} {_cache_control} {_metadata} {_metadata_directive}", check=True, shell=True, env=new_env)
    new_env = []
    if output.returncode != 0:
        print(f"aws.s3_sync(): Failed to Sync to S3... {output.stderr}")
        return False

    return True


def s3_cp(s3_bucket: str, 
            s3_path: str, 
            files: str, 
            s3_metadata: typing.Optional[str] = None,
            s3_metadata_directive: typing.Optional[str] = None,
            s3_cache_control: typing.Optional[str] = None,
            s3_content_type: typing.Optional[str] = None,
            session: typing.Optional[AwsSession] = None, 
            region: typing.Optional[str] = None) -> bool:
    """
    s3_cp()

    Authenticate against the current/default S3 and push files.

    s3_bucket: the bucket to use
    s3_path: the path inside of the s3 bucket to place files
    files: a string containing either a single file or a folder containing all files you want pushed.
    s3_metadata: String containing any metadata to add to the files. i.e. "Cache-Control=public, max-age=31536000"
    s3_metadata_directive: String specifying whether data is COPY'ed or REPLACE'd. Default is REPLACE
    s3_cache_control: String containing any cache-control information to add to the files. i.e. "max-age=86400"
    s3_content_type: String containing any content type to add to the files. i.e. "application/json"
    session: will use this session to build the client, default is _sessions
    region: will use a specfic region to build the client, default is _sessions.region_name

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.s3_cp(): BEGIN (using session named: {_s.name})")

    new_env = get_session_env(_s)

    if not s3_bucket.startswith('s3://'):
        s3_bucket = 's3://' + s3_bucket

    s3_full_path = f"{s3_bucket}/{s3_path}"
    
    recursive = "--recursive" if os.path.isdir(files) else ""
    
    _metadata = "" if not s3_metadata else f"--metadata \"{s3_metadata}\""
    _cache_control = "" if not s3_cache_control else f"--cache-control \"{s3_cache_control}\""
    _metadata_directive = "--metadata-directive REPLACE" if _cache_control else ""
    if _metadata and not _cache_control:
        _metadata_directive = "--metadata-directive REPLACE" if not s3_metadata_directive else f"--metadata-directive {s3_metadata_directive}"

    _content_type = "" if not s3_content_type else f"--content-type \"{s3_content_type}\""

    loggy.info(f"aws s3 cp {files} {s3_full_path} {recursive} {_cache_control} {_metadata} {_metadata_directive} {_content_type}")
    output = _run(f"aws s3 cp {files} {s3_full_path} {recursive} {_cache_control} {_metadata} {_metadata_directive} {_content_type}", check=True, shell=True, env=new_env)
    if output.returncode != 0:
        loggy.info(f"aws.s3_cp(): Failed to cp to S3... {output.stderr}")
        return False

    return True



def s3_get(s3_bucket: str, 
            s3_path: str, 
            file_name: typing.Optional[str] = None, 
            extracted_root: typing.Optional[str] = None, 
            session: typing.Optional[AwsSession] = None, 
            region: typing.Optional[str] = None) -> bool:
    """
    s3_get()

    Authenticate against the current/default S3 and get a file.

    s3_bucket: the bucket to use
    s3_path: the object key to retrieve
    file_name: a string containing a single file to save the file, default is s3_path.split('/')[-1]
    extracted_root: Extract the contents of the archive to this folder name. Only supports tar.gz rightn ow. Default is none
    session: will use this session to build the client, default is _sessions
    region: will use a specfic region to build the client, default is _sessions.region_name

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.s3_get(): BEGIN (using session named: {_s.name})")

    new_env = get_session_env(_s)

    if not s3_bucket.startswith('s3://'):
        s3_bucket = 's3://' + s3_bucket

    s3_full_path = f"{s3_bucket}/{s3_path}"
    
    loggy.info(f"aws s3 cp {s3_full_path} {file_name}")
    output = _run(f"aws s3 cp {s3_full_path} {file_name}", check=True, shell=True, env=new_env)
    if output.returncode != 0:
        loggy.info(f"aws.s3_get(): Failed to get {s3_full_path} from S3... {output.stderr}")
        return False

    if extracted_root:
        output = _run(f"mkdir -p {extracted_root}", check=True, shell=True, env=new_env)
        if output.returncode != 0:
            loggy.info(f"aws.s3_get(): Failed to make folder {extracted_root} ... {output.stderr}")
            return False

        output = _run(f"tar -xzf {file_name} --strip-components=1 -C {extracted_root}/", check=True, shell=True, env=new_env)
        if output.returncode != 0:
            loggy.info(f"aws.s3_get(): Failed to extract {file_name} into {extracted_root}... {output.stderr}")
            return False

    return True


"""
SSM Utils
"""


def ssm_get_parameter_from_build(name: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> str:
    """
    ssm_get_parameter_from_build()

    Get an SSM Parameter Value from the build account.

    name: String containing param friendly name or arn. Will convert arn into friendly name before use.
    session: aws.Sessions() will use a different session to build the client, default is _sessions
    region: String defaults to AWS_DEFAULT_REGION or us-east-1

    Returns String containing param value
    """
    _s = init_session() if session is None else session
    loggy.info(f"aws.ssm_get_parameter_from_build(): BEGIN (using session named: {_sessions.name})")
    return _sessions.ssm_get_parameter(name, session, region)


def ssm_get_parameter(name: str, session: typing.Optional[AwsSession] = None, region: typing.Optional[str] = None) -> str:
    """
    ssm_get_parameter()

    Get an SSM Parameter Value

    name: String containing param friendly name or arn. Will convert arn into friendly name before use.
    region: String defaults to AWS_DEFAULT_REGION or us-east-1
    session: aws.Sessions() will use a different session to build the client, default is _sessions

    Returns String containing param value
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.ssm_get_parameter(): BEGIN (using session named: {_s.name})")

    """
    This function only takes a name not an arn
    """
    name = name if ':parameter' not in name else name.split(':parameter')[1]

    try:
        client = _s.session.client(service_name='ssm', region_name=_r)
        response = client.get_parameter(Name=name, WithDecryption=True)

        return response['Parameter']['Value']
    except Exception as e:
        loggy.error("Error: " + str(e))

    return None


def ssm_put_parameter(name: str,
                      value: str,
                      type: typing.Optional[str] = None,
                      session: typing.Optional[AwsSession] = None,
                      region: typing.Optional[str] = None,
                      KeyId: typing.Optional[str] = None,
                      tier: typing.Optional[str] = "Standard") -> bool:
    """
    ssm_put_parameter()

    Create/Update an SSM Parameter

    name and value are required
    type defaults to String
    region defaults to AWS_DEFAULT_REGION or us-east-1
    session will use a different session to build the client, default is _sessions
    KeyId is a string containing the KeyId for the encryption key to use if not default
    tier is an optional string containing Standard, Advanced or Intelligent-Tiering, default is Standard

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.ssm_put_parameter(): BEGIN (using session named: {_s.name})")

    if not type:
        type = "String"

    """
    This function only takes a name not an arn
    """
    name = name if ':parameter' not in name else name.split(':parameter')[1]

    try:
        client = _s.session.client(service_name='ssm', region_name=_r)
        if KeyId:
            response = client.put_parameter(Name=name, Value=value, Type=type, Overwrite=True, KeyId=KeyId, Tier=tier)
        else:
            response = client.put_parameter(Name=name, Value=value, Type=type, Overwrite=True, Tier=tier)

        if response['Version']:
            return True
    except Exception as e:
        loggy.error("Error: " + str(e))

    return False


"""
Lambda Utils
"""

def lambda_update_docker(function_name: str, 
                        image_uri: str,
                        revision_id: typing.Optional[str] = None,
                        session: typing.Optional[AwsSession] = None,
                        region: typing.Optional[str] = None) -> bool:
    """
    lambda_update_docker()

    Update the docker container for a lambda function

    function_name name of function to update
    image_uri full ECR url to docker image, including tag
    revision_id The revision ID of the old lambda, use this to avoid updating the wrong version
    region defaults to AWS_DEFAULT_REGION or us-east-1
    session will use a different session to build the client, default is _sessions

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.lambda_update_docker(): BEGIN (using session named: {_s.name})")

    try:
        client = _s.session.client(service_name='lambda', region_name=_r)

        # Prepare the arguments
        args = {
            'FunctionName': function_name,
            'ImageUri': image_uri,
            'Publish': True,
        }

        # Add RevisionId only if it is not None or empty
        if revision_id:
            args['RevisionId'] = revision_id

        # Call the update_function_code with the dynamically built arguments
        response = client.update_function_code(**args)

        if response['Version']:
            return True
    except Exception as e:
        loggy.error("Error: " + str(e))

    return False


"""
Route53 Utils
"""

def route53_list_hosted_zones_by_name(domain_name: str, 
                        session: typing.Optional[AwsSession] = None,
                        region: typing.Optional[str] = None) -> str:
    """
    route53_list_hosted_zones_by_name()

    Return the hosted zone ID for a single domain name

    domain_name str of domain name
    """
    hosted_zone_id = None

    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.route53_list_hosted_zones_by_name(): BEGIN (using session named: {_s.name})")

    try:
        client = _s.session.client(service_name='route53')
        hosted_zone_id = client.list_hosted_zones_by_name(DNSName=domain_name)['HostedZones'][0]['Id'].split('/')[-1]
    except Exception as e:
        loggy.error("aws.route53_list_hosted_zones_by_name(): Error: " + str(e))

    return hosted_zone_id

def route53_get_record_ttl(hosted_zone_id: str, 
                            record_name: str, 
                            record_type="TXT", 
                            session: typing.Optional[AwsSession] = None,
                            region: typing.Optional[str] = None):
    """
    Fetch the TTL of an existing record in Route 53.

    :param hosted_zone_id: The ID of the Route 53 hosted zone.
    :param record_name: The name of the record to query (e.g., 'example.com').
    :param record_type: The type of the DNS record (e.g., 'TXT').
    region defaults to AWS_DEFAULT_REGION or us-east-1
    session will use a different session to build the client, default is _sessions

    :return: The TTL of the record if it exists, None otherwise.
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.route53_get_record_ttl(): BEGIN (using session named: {_s.name})")

    try:
        client = _s.session.client(service_name='route53')
    
        response = client.list_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            StartRecordName=record_name,
            StartRecordType=record_type,
            MaxItems="1"
        )

        # Check if the record exists and matches the requested name and type
        record_sets = response.get("ResourceRecordSets", [])
        if record_sets:
            record = record_sets[0]
            if record["Name"].rstrip(".") == record_name and record["Type"] == record_type:
                return record.get("TTL")
        loggy.info("aws.route53_get_record_ttl(): Record not found.")
        return None
    except Exception as e:
        loggy.info("aws.route53_get_record_ttl(): Error fetching record TTL:", e)
        return None

def route53_update_txt_record(record_name: str,
                        domain_name: str,
                        txt: str,
                        ttl: typing.Optional[int] = 0,
                        session: typing.Optional[AwsSession] = None,
                        region: typing.Optional[str] = None) -> bool:
    """
    route53_update_txt_record()

    Update a TXT record with a new string. Not multi-string compatible

    NOTE: It can take 15-30 seconds to propagate, so be careful about calling this repeatedly
        or in short bursts. You have been warned.

    record_name str name of DNS entry to update (i.e. routing-api)
    domian_name str name of the domain (i.e. dev.unfur.ly)
    txt str For instance, the routing TXT records are in a "{'weight': 0, 'version': '133455j4kj4'}" format
    region defaults to AWS_DEFAULT_REGION or us-east-1
    session will use a different session to build the client, default is _sessions

    Returns: True/False
    """
    _s = init_session() if session is None else session
    _r = _s.session.region_name if region is None else region

    loggy.info(f"aws.route53_update_txt_record(): BEGIN (using session named: {_s.name})")

    hosted_zone_id = route53_list_hosted_zones_by_name(domain_name=domain_name, session=_s)
    if not hosted_zone_id:
        return False

    fqdn = f"{record_name}.{domain_name}"

    try:
        client = _s.session.client(service_name='route53')

        #
        # If we get a ttl requested, we still need to check to make sure the record exists
        # Otherwise, getting the TTL from route53 is our exist check.
        #
        if not ttl:
            ttl = route53_get_record_ttl(hosted_zone_id=hosted_zone_id, record_name=fqdn, session=_s)
            if not ttl:
                raise Exception("aws.route53_update_txt_record() Could not get TTL from route53")

        #
        # Ensure the record exists before attempting to update it
        #
        response = client.test_dns_answer(
            HostedZoneId=hosted_zone_id,
            RecordName=f"{record_name}.{domain_name}",
            RecordType='TXT',
        )


        response = client.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Comment': 'CircleCI Updating TXT',
                'Changes': [
                    {
                        'Action': 'UPSERT',
                        'ResourceRecordSet': {
                            'Name': f"{record_name}.{domain_name}",
                            'Type': 'TXT',
                            'TTL': ttl,
                            'ResourceRecords': [
                                {'Value': '"' + txt + '"'}
                            ]
                        }
                    }
                ]
            }
        )

        loggy.info(response['ChangeInfo'])
        return True
    except Exception as e:
        loggy.error("aws.route53_update_txt_record(): Error: " + str(e))

    return False