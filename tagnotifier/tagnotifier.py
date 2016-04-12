#!/usr/bin/python

from __future__ import print_function

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

    if not 'EC2_Filters' in event:
        event['EC2_Filters'] = []

        if 'AWS_EC2_TAGS' in config:
            for tag in config['AWS_EC2_TAGS']:
                event['EC2_Filters'].append({
                    'Name': 'tag-key',
                    'Values': [
                        '!%s' % tag
                    ]
                })

    if not 'AMI_Filters' in event:
        event['AMI_Filters'] = [{
            'Name': 'tag-key',
            'Values': [
                '!ops:retention',
                '!ops:expiration'
            ]
        }]

        if 'AWS_AMI_TAGS' in config:
            for tag in config['AWS_AMI_TAGS']:
                event['AMI_Filters'].append({
                    'Name': 'tag-key',
                    'Values': [
                        '!%s' % tag
                    ]
                })

    if not 'SNAP_Filters' in event:
        event['SNAP_Filters'] = [{
            'Name': 'tag-key',
            'Values': [
                '!ops:retention',
                '!ops:expiration'
            ]
        }]

        if 'AWS_SNAP_TAGS' in config:
            for tag in config['AWS_SNAP_TAGS']:
                event['SNAP_Filters'].append({
                    'Name': 'tag-key',
                    'Values': [
                        '!%s' % tag
                    ]
                })

    ec2 = boto3.resource('ec2')

    for instance in ec2.instances.filter(Filters=event['EC2_Filters']):
        print(instance)

    for image in ec2.images.filter(Filters=event['AMI_Filters'], Owners=['self']):
        print(image)

    for snapshot in ec2.snapshots.filter(Filters=event['SNAP_Filters']):
        print(snapshot)
