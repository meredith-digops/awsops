#!/usr/bin/env python

import json
import sys

import boto3
from botocore.exceptions import ClientError

def get_account_id(context=None):
    """
    Return the root account ID for the current lambda context or iam user.
    """
    if context:
        return context.invoked_function_arn.split(':')[4]

    return boto3.client('iam').get_user()['User']['Arn'].split(':')[4]

def get_config(context=None, bucket=None, key='awsops.json'):
    """
    Return the awsops configparser object for the current account.
    """
    if not bucket:
        bucket = 'awsops-%s' % get_account_id(context)

    try:
        # Get the s3 object
        config_json = boto3.client('s3').get_object(
            Bucket=bucket,
            Key=key
        )['Body']
    except ClientError as e:
        # Let lambda exceptions serialize and exit
        # http://docs.aws.amazon.com/lambda/latest/dg/python-exceptions.html
        if context:
            raise

        if e.response['Error']['Code'] == 'NoSuchBucket':
            sys.exit('S3 bucket "%s" does not exist!' % bucket)

        if e.response['Error']['Code'] == 'NoSuchKey':
            sys.exit('S3 key "%s" does not exist!' % key)

    # Deserialize the json configuration
    config = json.loads(config_json.read().decode('utf-8'))

    # Add the bucket arn so it can be used by jinja2 templates
    # This doesn't make sense to statically set in the configuration json
    config['AWS_S3_ARN'] = 'arn:aws:s3:::%s/*' % bucket

    return config

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
