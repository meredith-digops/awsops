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


DEFAULT_RETENTION_DAYS = 30
"""Define number of days to retain a stopped instance by default"""

RETENTION_TAG_KEY = 'ops:retention'
"""Define tag that can explicitly set retention days on per-instance basis"""

log = logging.getLogger(__name__)


def get_stale_instances(ec2, filters, retention_days=DEFAULT_RETENTION_DAYS):
    """
    Find EC2 instance IDs that have been stopped long enough we want to remove
    :param ec2: boto3 ec2 resource
    :param filters: List of filters
    :type filters: list
    :param retention_days: Number of days
    :type retention_days: int
    :return: List of instance IDs
    :rtype: list
    """
    # Define what stop actions we should consider okay to terminate an instance
    # from.
    allowed_stop_reasons = [
        'User initiated'
    ]

    # Find all stopped instances matching our filter(s)
    stopped_instances = [i for i in ec2.instances.filter(Filters=filters)]
    log.info("Found {c} instances matching filter".format(
        c=len(stopped_instances)
    ))
    log.info("Filters: {f}".format(
        f=filters
    ))

    # Prepare a regex to find the reason & datetime of the stop action
    stoptime_regex = re.compile(r'^(.*)\s+\(([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9]{2}:[0-9]{2}:[0-9]{2}\s+[^\s]+)\s*\)\s*$')

    # Define when "now" is to determine relative time since instance stoppage
    now = datetime.now()

    # Define a list of instance ids that will be returned if they are truly
    # determined to be stale
    stale_instances = []

    # Loop through the stopped instances to see which ones we can assert are
    # stopped and candidates for termination
    for instance in stopped_instances:
        regex_search = stoptime_regex.search(
            instance.meta.data['StateTransitionReason'])

        if not regex_search:
            # No matches found, no way for us to determine the stop time and
            # whether or not this instance is subject to cleanup
            continue

        stopped_reason = regex_search.group(1)
        stopped_at = datetime.strptime(regex_search.group(2), "%Y-%m-%d %H:%M:%S %Z")

        # Ensure the instance was stopped for what we consider a reasonable
        # cause
        if stopped_reason not in allowed_stop_reasons:
            log.warning(
                "Instance {id} stopped for '{reason}', not terminating".format(
                    id=instance.id,
                    reason=stopped_reason
                ))
            continue

        # Determine the retention days or use the default provided to this
        # function call
        instance_retention = retention_days
        if instance.tags:
            for tag in instance.tags:
                if tag['Key'] == RETENTION_TAG_KEY:
                    instance_retention = int(tag['Value'])

        # If the instance was stopped for longer than the retention period is,
        # report this instance id as stale
        if stopped_at <= (now - timedelta(days=instance_retention)):
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

    # Ensure we're only checking stopped instances
    event['Filters'].append({
        'Name': 'instance-state-name',
        'Values': [
            'stopped',
        ]
    })

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