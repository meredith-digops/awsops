#!/usr/bin/env python
"""

launchconfigcleanup - Assists in cleaning up unused LaunchConfigurations

Usage: launchconfigcleanup.py [options]

Options:
    -D, --delete        Delete a candidate if one is present
    -n, --maxlcs NUM    Maximum number of LaunchConfigurations allowed in the
                        AWS account. A candidate will only be presented if the
                        account is at its limit.
"""

from __future__ import print_function

import boto3
import logging
from botocore.exceptions import ClientError


log = logging.getLogger(__name__)
"""Create a logger"""

DEFAULT_LAUNCHCONFIGURATION_LIMIT = 100
"""Max number of LaunchConfigurations allowed in AWS account"""


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
        lc_limit=DEFAULT_LAUNCHCONFIGURATION_LIMIT):
    """
    Return the name of a LaunchConfiguration to delete if space is needed

    :param asg_client: boto3 autoscaling client
    :type asg_client: botocore.client.AutoScaling
    :param lc_limit: Max number of LaunchConfigurations allowed in account
    :type lc_limit: int
    """
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
    max_lcs = int(args['--maxlcs'] or DEFAULT_LAUNCHCONFIGURATION_LIMIT)

    # Create boto client for ASG API
    client = boto3.client('autoscaling')

    # Find a deletion candidate
    candidate = get_launchconfigurations_delete_candidate(
        client,
        max_lcs)

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

        except ClientError as e:
            log.critical("Failed to delete LaunchConfiguration", exc_info=True)
            sys.exit(254)

        except Exception as e:
            log.critical("Unknown failure!", exc_info=True)
            sys.exit(254)
