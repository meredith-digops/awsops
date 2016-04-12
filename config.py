#!/usr/bin/env python

import configparser
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

def get_config(context=None, bucket=None, key='awsops.ini'):
    """
    Return the awsops configparser object for the current account.
    """
    if not bucket:
        bucket = 'awsops-%s' % get_account_id(context)

    try:
        # Get the s3 object
        ini = boto3.client('s3').get_object(
            Bucket=bucket,
            Key=key
        )['Body']
    except ClientError as e:
        # Let lambda exceptions serialize and exit
        # http://docs.aws.amazon.com/lambda/latest/dg/python-exceptions.html
        if context:
            pass

        if e.response['Error']['Code'] == 'NoSuchBucket':
            sys.exit('S3 bucket "%s" does not exist!' % bucket)

        if e.response['Error']['Code'] == 'NoSuchKey':
            sys.exit('S3 key "%s" does not exist!' % key)

    # Create and return configparser object from s3 object body
    config = configparser.ConfigParser()
    config.read_string(ini.read().decode('utf-8'), source=key)
    return config

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
