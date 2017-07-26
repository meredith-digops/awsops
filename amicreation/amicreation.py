#!/usr/bin/env python

from __future__ import print_function

import boto3
import time
from botocore.exceptions import ClientError
from datetime import datetime


def get_unix_timestamp():
    """
    Generate a Unix timestamp string.
    """

    d = datetime.now()
    t = time.mktime(d.timetuple())
    return str(int(t))


def lambda_handler(event, context):
    """
    Create EBS AMI for instances identified by the filter.
    """

    if not 'DryRun' in event:
        event['DryRun'] = False

    if not 'Filters' in event:
        event['Filters'] = [{
            'Name': 'tag-key',
            'Values': ['ops:snapshot']
        }]

    ec2 = boto3.resource('ec2')

    # Iterate through instances identified by the filter.
    for instance in ec2.instances.filter(Filters=event['Filters']):
        instance_name = instance.instance_id
        instance_tags = []

        # If a Name tag is available, use it to identify the instance
        # instead of the instance_id.
        for tag in instance.tags:
            if tag['Key'] == 'Name' and tag['Value'] != '':
                instance_name = tag['Value']
            else:
                instance_tags.append(tag)

        try:
            # Create the AMI
            image_name = instance_name + '-' + get_unix_timestamp()
            image = instance.create_image(
                        Name=image_name,
                        NoReboot=True,
                        DryRun=event['DryRun']
                    )
            print('Started image creation: ' + image_name)

            image_tags = [{'Key': 'ops:retention', 'Value': '30'}] + instance_tags
            image.create_tags(
                Tags=image_tags,
                DryRun=event['DryRun']
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'DryRunOperation':
                pass
