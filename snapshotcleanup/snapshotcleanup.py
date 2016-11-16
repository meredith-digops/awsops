#!/usr/bin/env python

from __future__ import print_function

from datetime import datetime, timedelta, tzinfo
import boto3
from botocore.exceptions import ClientError


DEFAULT_RETENTION_DAYS = None
"""If None, no default retention is applied"""

ZERO = timedelta(0)


class UTC(tzinfo):
    """
    Implements UTC timezone for datetime interaction
    """
    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


def get_snapshots(ec2, filters, retention):
    """
    Generator of snapshots that exceed retention policy.
    """
    for snapshot in ec2.snapshots.filter(Filters=filters):
        # If the retention is specified in a tag override the default
        if snapshot.tags:
            for tag in snapshot.tags:
                if tag['Key'] == 'ops:retention':
                    retention = int(tag['Value'])

	utc = UTC()
        if retention and \
                snapshot.start_time < (datetime.now(utc) - timedelta(days=retention)):
            yield snapshot


def lambda_handler(event, context):
    """
    Delete EBS snapshots that exceed retention policy.
    """

    if not 'DryRun' in event:
        event['DryRun'] = False

    if not 'Filters' in event:
        event['Filters'] = [{
            'Name': 'tag-key',
            'Values': [
                'ops:retention'
            ]
        }]

    # Set the default retention period if none was provided to the lambda
    # invocation
    if not 'Retention' in event:
        event['Retention'] = DEFAULT_RETENTION_DAYS

    ec2 = boto3.resource('ec2')
    snapshots = get_snapshots(ec2, filters=event['Filters'],
                              retention=event['Retention'])

    for snapshot in snapshots:
        print('Deleting: %s' % snapshot)
        try:
            snapshot.delete(DryRun=event['DryRun'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'DryRunOperation':
                pass
