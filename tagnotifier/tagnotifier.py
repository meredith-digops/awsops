#!/usr/bin/python

from __future__ import print_function

import re
from datetime import datetime, timedelta, tzinfo

import boto3
from botocore.exceptions import ClientError

from config import get_config

def lambda_handler(event, context):
    """
    Identify EC2 resources which don't meet tag requirements.
    """
    config = get_config(context)

    if not 'DryRun' in event:
        event['DryRun'] = False

    if not 'AWS_EC2_TAGS' in event:
        event['AWS_EC2_TAGS'] = []

        if 'AWS_EC2_TAGS' in config:
            event['AWS_EC2_TAGS'].extend(config['AWS_EC2_TAGS'])

    if not 'AWS_AMI_TAGS' in event:
        event['AWS_AMI_TAGS'] = []

        if 'AWS_AMI_TAGS' in config:
            event['AWS_AMI_TAGS'].extend(config['AWS_AMI_TAGS'])

    if not 'AWS_SNAP_TAGS' in event:
        event['AWS_SNAP_TAGS'] = []

        if 'AWS_SNAP_TAGS' in config:
            event['AWS_SNAP_TAGS'].extend(config['AWS_SNAP_TAGS'])

    ec2 = boto3.resource('ec2')

    for instance in ec2.instances.all():
        for key in event['AWS_EC2_TAGS']:
            matches = (tag['Key'] == key for tag in instance.tags)
            if not any(matches):
                print('Tag %s not set on %s' % (key, instance))

    for image in ec2.images.filter(Owners=['self']):
        for key in event['AWS_AMI_TAGS']:
            if image.tags:
                matches = (tag['Key'] == key for tag in image.tags)
                if not any(matches):
                    print('Tag %s not set on %s' % (key, image))

    for snapshot in ec2.snapshots.all():
        for key in event['AWS_SNAP_TAGS']:
            if snapshot.tags:
                matches = (tag['Key'] == key for tag in snapshot.tags)
                if not any(matches):
                    print('Tag %s not set on %s' % (key, snapshot))
