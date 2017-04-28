#!/usr/bin/env python
"""

launchconfigcleanup - Assists in cleaning up unused LaunchConfigurations

Usage: launchconfigcleanup.py [options]

Options:
    -a, --minage DAYS   Minimum number of days a LaunchConfiguration must be
                        to be considered a deletion candidate. [default: 5]

    -D, --delete NUM    Number of candidates to delete [default: 1]
                        If this number is negative, this script determines how
                        many LaunchConfigurations need to be deleted to ensure
                        that number of slots is available away from the
                        maximum.

    --dry-run           Only log what would happen, do not delete any
                        LaunchConfigurations

    -n, --maxlcs NUM    Maximum number of LaunchConfigurations allowed in the
                        AWS account. This parameter should only be used during
                        testing, otherwise the script will determine what your
                        accounts limitation is.

    -l, --log-level LEVEL   What logging level to use [default: warning]
"""

from __future__ import print_function

import boto3
import logging
from botocore.exceptions import ClientError
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo


log = logging.getLogger(__name__)
"""Create a logger"""

ZERO = timedelta(0)

LAMBDA_DEFAULTS = {
    # --dry-run
    'DryRun': False,
    # --delete
    'LC_Delete': 1,
    # --maxlcs
    'LC_Limit': lambda c: get_max_launchconfigurations(c),
    # --log-level
    'LogLevel': 'info',
    # --minage
    'MinAge': 5,
}
"""Default parameters for Lambda, these mimic the docopt arguments"""


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


class InsufficientCandidates(Exception):
    """
    Defines a failure to delete the requested number of LaunchConfigurations
    """
    pass


def get_max_launchconfigurations(asg_client):
    """
    Return the maximum number of LaunchConfigurations allowed in account
    """
    return asg_client.describe_account_limits()['MaxNumberOfLaunchConfigurations']


def get_all_launchconfigurations(asg_client):
    """
    Generator to find all LaunchConfigurations
    """
    lc_pager = asg_client.get_paginator('describe_launch_configurations')
    lc_iter = lc_pager.paginate()
    for lc_page in lc_iter:
        for lc in lc_page['LaunchConfigurations']:
            yield lc


def get_inuse_launchconfigurations(asg_client):
    """
    Generator to find LaunchConfigurations in-use by ASGs

    :param asg_client: boto3 autoscaling client
    :type asg_client: botocore.client.AutoScaling
    """
    asg_pager = asg_client.get_paginator('describe_auto_scaling_groups')
    asg_iter = asg_pager.paginate()
    for asg_page in asg_iter:
        for asg in asg_page['AutoScalingGroups']:
            yield asg['LaunchConfigurationName']


def get_launchconfiguration_deletion_candidates(asg_client, min_age):
    """
    Get a list of LaunchConfigurations that may be deleted

    :param asg_client: boto3 autoscaling client
    :type asg_client: botocore.client.AutoScaling
    :param min_age: Days old a LaunchConfiguration must be to be a candidate
    :type min_age: int
    :return: Tuple of (deletion_candidates, all_launch_configs)
    :rtype: tuple
    """
    all_lcs = [lc for lc in get_all_launchconfigurations(asg_client)]

    # Find LCs that are in-use
    used_lcs = [lc_name for lc_name in get_inuse_launchconfigurations(asg_client)]
    log.info("Found {} LaunchConfigurations in-use".format(len(used_lcs)))

    # Determine unused LCs
    unused = [lc for lc in all_lcs if lc['LaunchConfigurationName'] not in used_lcs]
    log.info("Found {} LaunchConfigurations unused".format(len(unused)))

    # Find old enough candidates
    min_created_time = datetime.now(UTC()) - timedelta(days=min_age)
    log.warning("Finding LCs from before {}".format(min_created_time.isoformat()))
    candidates = [lc for lc in unused
                  if lc['CreatedTime'] <= min_created_time]

    return sorted(candidates, key=lambda k: k['CreatedTime']), all_lcs


def json_serial(obj):
    """
    Handles formatting datetimes
    Source: http://stackoverflow.com/a/22238613
    """
    if isinstance(obj, datetime):
        return obj.isoformat()

    raise TypeError("{t} is not serializeable".format(t=type(obj)))


def lambda_handler(event, context):
    """
    Delete ASG LaunchConfiguration if at the account limit
    """

    # Setup logging
    log_level = event.get('LogLevel', False) or LAMBDA_DEFAULTS['LogLevel']
    logging.basicConfig(**{
        'level': getattr(logging, log_level.upper()),
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    })

    # Create boto client for ASG API
    client = boto3.client('autoscaling')

    # Determine runtime parameters
    dry_run = bool(event.get('DryRun', LAMBDA_DEFAULTS['DryRun']))
    delete_count = int(event.get('LC_Delete', False) or LAMBDA_DEFAULTS['LC_Delete'])
    resource_limit = int(event.get('LC_Limit', False) or LAMBDA_DEFAULTS['LC_Limit'](client))
    min_age = int(event.get('MinAge', False) or LAMBDA_DEFAULTS['MinAge'])

    # DryRun is not supported by the boto3 autoscaling client
    if dry_run:
        log.warning("DryRun not supported by boto3 or the API!"
                    " A log line will be emitted instead")

    # Find candidates
    candidates, all_lcs = get_launchconfiguration_deletion_candidates(
        client,
        min_age=min_age)

    # Delete the candidate
    log.warning("Found {c} candidate{s}".format(
        c=len(candidates),
        s="" if len(candidates) == 1 else "s"))
    log.debug(json.dumps(
        candidates,
        indent=4,
        default=json_serial))

    if delete_count < 0:
        # We want to delete as many as necessary to be this many below the
        # resource limit
        delete_count = ((resource_limit - len(all_lcs)) + delete_count) * -1

    # Execute the deletion
    log.warning("Attempting to delete {c} LaunchConfiguration resource{s}".format(
        c=delete_count,
        s="" if delete_count == 1 else "s"))

    while delete_count > 0:
        try:
            lc = candidates.pop(0)
        except IndexError as e:
            raise InsufficientCandidates(
                "Failed to delete {c} remaining resource{s}".format(
                    c=delete_count,
                    s="" if delete_count == 1 else "s")
            )

        if not dry_run:
            client.delete_launch_configuration(
                LaunchConfigurationName=lc['LaunchConfigurationName'])
        else:
            log.warning(
                "DryRun: Would have deleted this LaunchConfiguration:\n"
                + json.dumps(lc,
                             indent=4,
                             default=json_serial)
            )

        delete_count -= 1

    log.warning("Successfully deleted LaunchConfiguration(s)")


if __name__ == '__main__':
    import json
    import sys
    from docopt import docopt

    # Parse CLI arguments
    args = docopt(__doc__, version='dev')

    try:
        lambda_handler(
            event={
                'DryRun': args['--dry-run'],
                'LC_Delete': args['--delete'],
                'LC_Limit': args['--maxlcs'],
                'LogLevel': args['--log-level'],
                'MinAge': args['--minage'],
            },
            context={}
        )

    except InsufficientCandidates as e:
        log.critical(str(e))
        log.info(str(e), exc_info=True)
        sys.exit(1)
