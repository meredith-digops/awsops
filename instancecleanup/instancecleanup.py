#!/usr/bin/env python
"""
instancecleanup.py

Usage:
    instancecleanup.py [options]

Options:
    -h, --help          Show this screen
    --version           Show the script version
    --hot-run           Actually terminate instance(s)
    --log-level LEVEL   Logging level (see logging module)
"""

import boto3
import logging
import re
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from botocore.exceptions import ClientError


RETENTION_TAG_KEY = 'ops:retention'
"""Define tag that can explicitly set retention days on per-instance basis"""

ZERO = timedelta(0)


log = logging.getLogger(__name__)

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


def get_stale_instances(ec2, filters, include_protected=True):
    """
    Find EC2 instance IDs that have been created long enough ago we want to remove

    :param ec2: boto3 ec2 resource
    :type ec2: boto3.resources.factory.ec2.ServiceResource
    :param filters: List of filters
    :type filters: list
    :param include_protected: Flag to include or exclude termination protected instances
    :type include_protected: bool
    :return: List of instance IDs
    :rtype: list
    """
    # Find all applicable instances matching our filter(s)
    candidate_instances = [i for i in ec2.instances.filter(Filters=filters)]
    log.info("Found {c} instances matching filter".format(
        c=len(candidate_instances)
    ))
    log.info("Filters: {f}".format(
        f=filters
    ))

    # Define a list of instance ids that will be returned if they are truly
    # determined to be stale
    stale_instances = []

    now = datetime.now(UTC())

    # Loop through the candidate instances to see which ones we can assert are
    # candidates for termination
    for instance in candidate_instances:
        # Determine the retention days or use the default provided to this
        # function call
        instance_retention = None
        if instance.tags:
            try:
                for tag in instance.tags:
                    if tag['Key'] == RETENTION_TAG_KEY:
                        instance_retention = int(tag['Value'])
            except TypeError:
                # instance.tags == None
                pass

        # Ignore instances missing the retention tag
        if not instance_retention:
            continue

        # If the instance was started longer ago than the retention period is,
        # report this instance id as stale for potential termination
        if instance.meta.data['LaunchTime'] <= (now - timedelta(days=instance_retention)):
            if include_protected:
                # If the request is including instances with termination
                # protection, simply assume it doesn't the for the following
                # conditional
                has_protection = False
            else:
                # This instance might be considered stale, but first check if it
                # has termination protection enabled
                has_protection = ec2.meta.client.describe_instance_attribute(
                    InstanceId=instance.id,
                    Attribute='disableApiTermination')['DisableApiTermination']['Value']

            if not has_protection:
                # Instances are only stale if they don't have termination
                # protection enabled
                stale_instances.append(instance.id)

    return stale_instances


def lambda_handler(event, context):
    """
    Terminate instances that are stopped & out of retention
    """

    if 'DryRun' not in event:
        # If DryRun is not being specified, assume we're doing a real run
        event['DryRun'] = False

    if 'Filters' not in event:
        # If no filter is specified, at least make an empty list
        event['Filters'] = []

    ec2 = boto3.resource('ec2')
    stale_instances = get_stale_instances(ec2,
                                          event['Filters'])

    if event['DryRun']:
        log.warning("WARNING: DryRun only, no instances will be terminated!")

    log.info("Found {c} stale instances".format(
        c=len(stale_instances)
    ))

    for instance_id in stale_instances:
        log.warning("Terminating: {id}".format(
            id=instance_id
        ))

        if event['DryRun']:
            continue

        try:
            # Attempt instance termination
            ec2.instances.filter(InstanceIds=[instance_id]).terminate(
                DryRun=event['DryRun']
            )

        except ClientError as e:
            if e.response['Error']['Code'] == 'DryRunOperation':
                pass

            log.debug(e.message, exc_info=True)
            log.error(e.message)


if __name__ == '__main__':
    from docopt import docopt

    args = docopt(__doc__, version='unspecified')
    log_level = args['--log-level'] if args['--log-level'] \
                                    else 'warning'
    dry_run = not args['--hot-run']

    logging.basicConfig(**{
        'level': getattr(logging, log_level.upper()),
        'format': '[%(asctime)s][%(levelname)s] %(message)s',
    })

    lambda_handler(
        event={
            'DryRun': dry_run,
        },
        context={})
