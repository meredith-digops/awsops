#!/usr/bin/env python

from __future__ import print_function

import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo


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


def fetch_available_volumes(ec2, filters=None):
    """
    Generator of available EBS volumes

    :param ec2: EC2 resource
    :type ec2: boto3.resources.factory.ec2.ServiceResource
    :param filters: Optional list of filters
    :type filters: None|list
    :returns: volumes collection
    :rtype: boto3.resources.collection.ec2.volumesCollection
    """
    # Set an empty filter set if none provided
    if filters is None:
        filters = []

    # Append the filter for finding only volumes that are in the 'available'
    # state.
    # Ref: http://docs.aws.amazon.com/AWSEC2/latest/APIReference/API_DescribeVolumes.html
    filters.append({
        'Name': 'status',
        'Values': ['available'],
    })
    return ec2.volumes.filter(
        Filters=filters
    )


def get_abandoned_volumes(since, *args, **kwargs):
    """
    Generate of available EBS volumes created some time ago

    :param since: Datetime where all volumes created prior to are considered abandoned
    :type since: datetime.datetime
    :returns: (iterator) of volumes
    :rtype: boto3.resources.factory.ec2.Volume
    """
    for vol in fetch_available_volumes(*args, **kwargs):
        # Ignore volumes created after `since` parameter
        if vol.meta.data['CreateTime'] > since:
            continue

        yield vol


def lambda_handler(event, context):
    """
    Delete abandoned EBS snapshots that exceed reasonable retention
    """
    # Set the default retention period if none was provided to the lambda
    # invocation
    if 'Retention' not in event:
        event['Retention'] = DEFAULT_RETENTION_DAYS

    if event['Retention'] is None:
        # Don't delete anything
        raise AttributeError("No Retention specified")

    if 'DryRun' not in event:
        event['DryRun'] = False

    if 'Filters' not in event:
        event['Filters'] = [{
            'Name': 'tag-key',
            'Values': [
                'ops:retention'
            ]
        }]

    since = datetime.now(UTC()) - timedelta(float(event['Retention']))
    ec2 = boto3.resource('ec2')
    old_volumes = get_abandoned_volumes(since,
                                        ec2=ec2,
                                        filters=event['Filters'])

    for volume in old_volumes:
        print("Deleting: {id}".format(
            id=volume.id
        ))

        try:
            volume.delete(DryRun=event['DryRun'])
        except ClientError as e:
            if e.response['Error']['Code'] == 'DryRunOperation':
                pass


if __name__ == '__main__':
    from terminaltables import AsciiTable
    since = datetime.now(UTC()) - timedelta(3*365/12)

    print("Since: {}".format(
        since.isoformat()))

    table_headers = [
        [
            'created',
            'id',
            'size',
            'type',
            'tags',
        ]
    ]
    table_data = []
    vols = get_abandoned_volumes(
        since,
        ec2=boto3.resource('ec2'))

    for v in vols:
        table_data.append([
            v.meta.data['CreateTime'].isoformat(),
            v.id,
            v.size,
            v.volume_type,
            "" if v.tags is None else
                "\n".join("{k}: {v}".format(
                    k=i['Key'],
                    v=i['Value']
                ) for i in v.tags),
        ])

    table_data.sort(key=lambda x: x[0])
    print(AsciiTable(table_headers + table_data).table)
