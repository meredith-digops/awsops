#!/usr/bin/env python
"""
instancecleanup.py

Usage:
    instancecleanup.py [options]

Options:
    -h, --help          Show this screen
    --version           Show the script version
    --hot-run           Actually terminate instance(s)
    --days=<D>          Number of days since the instance was stopped
    --log-level LEVEL   Logging level (see logging module)
"""

from __future__ import print_function
import boto3
import logging
import re
from datetime import datetime
from datetime import timedelta
from botocore.exceptions import ClientError


DEFAULT_RETENTION_DAYS = None
"""Define number of days to retain a stopped instance by default, if None is unused"""

RETENTION_TAG_KEY = 'ops:retention'
"""Define tag that can explicitly set retention days on per-instance basis"""

log = logging.getLogger(__name__)


def get_stale_instances(ec2, filters, retention_days):
    """
    Find EC2 instance IDs that have been created long enough ago we want to remove

    :param ec2: boto3 ec2 resource
    :param filters: List of filters
    :type filters: list
    :param retention_days: Number of days
    :type retention_days: int
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

    # Loop through the candidate instances to see which ones we can assert are
    # candidates for termination
    for instance in candidate_instances:
        # Determine the retention days or use the default provided to this
        # function call
        instance_retention = retention_days
        if instance.tags:
            # TODO: The following will raise an exception if no tags present
            for tag in instance.tags:
                if tag['Key'] == RETENTION_TAG_KEY:
                    instance_retention = int(tag['Value'])

        # If the instance was started longer ago than the retention period is,
        # report this instance id as stale for potential termination
        now = datetime.now(instance.meta.data['LaunchTime'].tzinfo)
        if instance_retention and \
                instance.meta.data['LaunchTime'] <= (now - timedelta(days=instance_retention)):
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

    if 'Retention' not in event:
        event['Retention'] = DEFAULT_RETENTION_DAYS

    ec2 = boto3.resource('ec2')
    stale_instances = get_stale_instances(ec2,
                                          event['Filters'],
                                          event['Retention'])

    if event['DryRun']:
        print("WARNING: DryRun only, no instances will be terminated!")

    log.info("Found {c} stale instances (stopped >= {ret} days ago)".format(
        c=len(stale_instances),
        ret=event['Retention']
    ))
    print("Found {c} stale instances (stopped >= {ret} days ago)".format(
        c=len(stale_instances),
        ret=event['Retention']
    ))

    for instance_id in stale_instances:
        log.warning("Terminating: {id}".format(
            id=instance_id
        ))
        print("Terminating: {id}".format(
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
            elif e.response['Error']['Code'] == 'OperationNotPermitted':
                if 'disableApiTermination' in e.response['Error']['Message']:
                    # Terminate protection is enabled, ignore
                    log.debug("{id} has termination protection enabled, ignoring".format(
                        id=instance_id))


if __name__ == '__main__':
    from docopt import docopt

    args = docopt(__doc__, version='unspecified')
    log_level = args['--log-level'] if args['--log-level'] \
                                    else 'warning'
    retention_days = int(args['--days']) if args['--days'] \
                                         else DEFAULT_RETENTION_DAYS
    dry_run = not args['--hot-run']

    logging.basicConfig(**{
        'level': getattr(logging, log_level.upper()),
        'format': '[%(asctime)s][%(levelname)s] %(message)s',
    })

    lambda_handler(
        event={
            'Retention': retention_days,
            'DryRun': dry_run,
        },
        context={})
