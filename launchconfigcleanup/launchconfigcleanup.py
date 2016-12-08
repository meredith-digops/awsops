#!/usr/bin/env python
"""

launchconfigcleanup - Assists in cleaning up unused LaunchConfigurations

Usage: launchconfigcleanup.py [options]

Options:
    -a, --minage DAYS   Minimum number of days a LaunchConfiguration must be
                        to be considered a deletion candidate.

    -D, --delete        Delete a candidate if one is present

    -n, --maxlcs NUM    Maximum number of LaunchConfigurations allowed in the
                        AWS account. A candidate will only be presented if the
                        account is at its limit.
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

DEFAULT_MINIMUM_AGE = 5
"""Min age (days) a LaunchConfiguration must be to be a candidate"""

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


class AllCandidatesTooNew(Exception):
    """
    Defines a failure to find an old enough unused LC deletion candidate
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


def get_launchconfigurations_delete_candidate(asg_client,
        lc_limit=None,
        min_age=DEFAULT_MINIMUM_AGE):
    """
    Return the name of a LaunchConfiguration to delete if space is needed

    :param asg_client: boto3 autoscaling client
    :type asg_client: botocore.client.AutoScaling
    :param lc_limit: Max number of LaunchConfigurations allowed in account
    :type lc_limit: int
    :param min_age: Days old a LaunchConfiguration must be to be a candidate
    :type min_age: int
    """
    if lc_limit is None:
        # If not explicit LaunchConfiguration limit provided, determine the
        # max number allowed for the client account
        lc_limit = get_max_launchconfigurations(asg_client)

    all_lcs = [lc for lc in get_all_launchconfigurations(asg_client)]

    if len(all_lcs) < lc_limit:
        # No LC needs to be deleted
        log.info("{lc} < {limit}, no LaunchConfiguration deletion needed".format(
            lc=len(all_lcs),
            limit=lc_limit))
        return None

    log.warning("At LaunchConfiguration limit! ({limit})".format(
        limit=lc_limit))

    # Find LCs that are in-use
    used_lcs = [lc_name for lc_name in get_inuse_launchconfigurations(asg_client)]
    log.debug("Found {} LaunchConfigurations in-use".format(len(used_lcs)))

    # Determine unused LCs
    unused = [lc for lc in all_lcs if lc['LaunchConfigurationName'] not in used_lcs]
    log.debug("Found {} LaunchConfigurations unused".format(len(unused)))

    # Find old enough candidates
    min_created_time = datetime.now(UTC()) - timedelta(days=min_age)
    log.warning("Finding LCs from before {}".format(min_created_time.isoformat()))
    unused = [lc for lc in unused
              if lc['CreatedTime'] <= min_created_time]

    log.debug("Found {c} LaunchConfiguration candidate{s}".format(
        c=len(unused),
        s="" if len(unused) == 1 else "s"))

    # If there are no old enough candidates, raise an exception
    if len(unused) == 0:
        raise AllCandidatesTooNew(
            "No candidates at least {d} day{s} old!".format(
                d=min_age,
                s="" if min_age == 1 else "s"))

    return sorted(unused, key=lambda k: k['CreatedTime'])[0]


if __name__ == '__main__':
    import json
    import sys
    from docopt import docopt

    # Setup logging
    logging.basicConfig(**{
        'level': logging.INFO,
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    })

    # Parse CLI arguments
    args = docopt(__doc__, version='dev')

    do_delete = args['--delete']

    max_lcs = int(args['--maxlcs'] or -1)
    min_age = int(args['--minage'] or DEFAULT_MINIMUM_AGE)

    # Create boto client for ASG API
    client = boto3.client('autoscaling')

    # If no maxlcs was passed, determine the accounts maximum allowed
    if max_lcs < 1:
        max_lcs = get_max_launchconfigurations(client)

    # Find a deletion candidate
    candidate = get_launchconfigurations_delete_candidate(
        client,
        max_lcs,
        min_age)

    # If no candidate is present, exit
    if candidate is None:
        log.warning("No deletion candidate found")
        sys.exit(0)

    # Convert the candidates CreatedTime field to a string for serialization
    if 'CreatedTime' in candidate:
        candidate.update({
            'CreatedTime': candidate['CreatedTime'].isoformat()
        })

    log.info("Candidate:")
    log.info(json.dumps(
        candidate,
        indent=4,
        separators=(',', ': ')))

    if do_delete:
        # Execution the deletion
        log.info("Attempting to delete the LaunchConfiguration")

        try:
            client.delete_launch_configuration(
                LaunchConfigurationName=candidate['LaunchConfigurationName'])

        except AllCandidatesTooNew as e:
            log.critical("Could not find an old enough deletion candidate!")
            sys.exit(1)

        except ClientError as e:
            log.critical("Failed to delete LaunchConfiguration", exc_info=True)
            sys.exit(254)

        except Exception as e:
            log.critical("Unknown failure!", exc_info=True)
            sys.exit(254)
