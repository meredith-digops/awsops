#!/usr/bin/python

from __future__ import print_function

from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    Cleanup orphaned AMIs and EBS snapshots.
    """

    if not 'DryRun' in event:
        event['DryRun'] = False

    autoscaling = boto3.client('autoscaling')
    paginator = autoscaling.get_paginator('describe_launch_configurations')

    for page in paginator.paginate():
        # do something with page['Contents']
        pass
