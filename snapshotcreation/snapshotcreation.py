#!/usr/bin/env python

from __future__ import print_function

import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    Create EBS snapshots for instances identified by the filter.
    """

    if not 'DryRun' in event:
        event['DryRun'] = False

    if not 'Filters' in event:
        event['Filters'] = [{
            'Name': 'tag-key',
            'Values': ['ops:needs_snapshot']
        }]

    ec2 = boto3.resource('ec2')

    # Iterate through instances identified by the filter.
    for instance in ec2.instances.filter(Filters=event['Filters']):

        # Iterate through volumes mapped to the instance.
        for block_device_mapping in instance.block_device_mappings:
            instance_name = instance.instance_id

            # If a Name tag is available, use it to identify the snapshot
            # instead of the instance_id.
            for tag in instance.tags:
                if tag['Key'] == 'Name' and tag['Value'] != '':
                    instance_name = tag['Value']
                    break

            # Name the snapshot.
            snapshot_description = instance_name + ' - ' \
                + block_device_mapping['DeviceName']

            try:
                # Create the snapshot.
                snapshot = ec2.create_snapshot(
                    Description=snapshot_description,
                    VolumeId=block_device_mapping['Ebs']['VolumeId'],
                    DryRun=event['DryRun']
                )

                # Add retention tags to the snapshot.
                snapshot.create_tags(
                    Tags=[{'Key': 'ops:retention', 'Value': '30'}],
                    DryRun=event['DryRun']
                )

            except ClientError as e:
                if e.response['Error']['Code'] == 'DryRunOperation':
                    pass
