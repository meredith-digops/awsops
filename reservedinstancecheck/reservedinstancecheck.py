#!/usr/bin/env python
"""
reservedinstancecheck - Checks compliance for reserved instance use

USAGE: reservedinstancecheck [options]

Options:
    -h, --help              Show this dialog

    -r, --region REGION     AWS region to examine
    -R, --reservations      Show active reservations
    -u, --unused            Show unused reservations
    -U, --unreserved DAYS   Show instances launch >= DAYS ago that do not have
                            an active reservation
"""

from __future__ import print_function

import boto3
import logging
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo


log = logging.getLogger(__name__)


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


class ReservationChecker(object):
    @classmethod
    def fetch_active_instance_reservations(cls, client, filters=[]):
        """
        Finds all active instance reservations

        :param client: boto3 EC2 client
        :type client: botocore.client.EC2
        :param filters: Optional additional list of filters
        :type filters: list
        :return: list of instance reservations
        :rtype: list[dict]
        """
        filters.append({
            'Name': 'state',
            'Values': ['active']
        })
        resp = client.describe_reserved_instances(Filters=filters)

        for ri in resp['ReservedInstances']:
            assert ri['Scope'] == 'Availability Zone', \
                "Unsupported reservation scope: {}".format(ri['Scope'])

        return resp['ReservedInstances']

    def __init__(self, region=None):
        """

        :param region:
        """
        self._reservations = None
        self._unreserved = None
        self._unused = None

        # Client setup
        client_args = {}

        if region is not None:
            client_args.update({
                'region_name': args['--region'],
            })

        # Instantiate client
        self.ec2 = boto3.client('ec2', **client_args)

    @property
    def region(self):
        return self.ec2.meta.region_name

    def _find_unused_or_unreserved(self):
        """

        :return:
        """
        # Determine what AZs to look through for instances
        reserved_azs = [ri['AvailabilityZone'] for ri in self.reservations]

        # Construct a request to find all EC2 instances that are not stopped or
        # terminated
        pager = self.ec2.get_paginator('describe_instances')
        pageiter = pager.paginate(**{
            'Filters': [
                {
                    'Name': 'instance-state-name',
                    'Values': [
                        'pending',
                        'running',
                        'shutting-down',
                        'stopping',
                    ]
                }
            ]
        })

        # Accumulate all the instances from the region
        all_instances = []
        for page in pageiter:
            for r in page['Reservations']:
                all_instances += r['Instances']

        # Order instances based on their creation time
        all_instances = sorted(all_instances, key=lambda k: k['LaunchTime'])

        # Mark all reservations as unused initially
        self._unused = {}
        for res in self.reservations:
            az = res['AvailabilityZone']
            instance_type = res['InstanceType']

            if az not in self._unused:
                self._unused[az] = {}

            if instance_type not in self._unused[az]:
                self._unused[az][instance_type] = 0

            self._unused[az][instance_type] += res['InstanceCount']

        # Iterate through all instances and tick off the ones that are
        # reserved
        self._unreserved = []
        for instance in all_instances:
            az = instance['Placement']['AvailabilityZone']
            instance_type = instance['InstanceType']

            try:
                self._unused[az][instance_type] -= 1

                if self._unused[az][instance_type] == 0:
                    # This reservation is fully in-use
                    del self._unused[az][instance_type]

                if self._unused[az] == 0:
                    # No reservations remaining in AZ
                    del self._unused[az]

            except KeyError:
                # No matching reservation
                self._unreserved.append(instance)

    @property
    def reservations(self):
        if self._reservations is None:
            log.debug("Lazy loading reservations...")
            self._reservations = self.fetch_active_instance_reservations(
                self.ec2)
            log.debug("Found {c} reservation{s}".format(
                c=len(self._reservations),
                s="" if len(self._reservations) == 1 else "s"
            ))

        return self._reservations

    @property
    def unreserved(self):
        if self._unreserved is None:
            self._find_unused_or_unreserved()

        return self._unreserved

    @property
    def unreserved_grouping(self):
        unreserved = {}
        for instance in self.unreserved:
            az = instance['Placement']['AvailabilityZone']
            instance_type = instance['InstanceType']

            if az not in unreserved:
                unreserved[az] = {}

            if instance_type not in unreserved[az]:
                unreserved[az][instance_type] = 0

            unreserved[az][instance_type] += 1

        return unreserved

    def unreserved_older_than(self, **kwargs):
        """
        Return dict of instances older than ```days``` that aren't reserved
        :param days: Number of days since launch time
        :type days: int
        :return: dict
        """
        min_launch_time = datetime.now(UTC()) - timedelta(**kwargs)
        for instance in self.unreserved:
            if instance['LaunchTime'] <= min_launch_time:
                yield instance

    def unreserved_grouping_older_than(self, **kwargs):
        """
        Groups by AZ+instance type all instances launched before a given time
        :return: dict
        """
        unreserved = {}
        for instance in self.unreserved_older_than(**kwargs):
            az = instance['Placement']['AvailabilityZone']
            instance_type = instance['InstanceType']

            if az not in unreserved:
                unreserved[az] = {}

            if instance_type not in unreserved[az]:
                unreserved[az][instance_type] = 0

            unreserved[az][instance_type] += 1

        return unreserved

    @property
    def unused(self):
        if self._unused is None:
            self._find_unused_or_unreserved()

        return self._unused


if __name__ == '__main__':
    from docopt import docopt
    from terminaltables import AsciiTable

    # Define explicit client arguments, such as region, that will be used
    # to instantiate the boto3 client
    client_args = {}

    # Parse command line arguments
    args = docopt(__doc__, version='dev')
    if args['--region']:
        client_args.update({
            'region_name': args['--region'],
        })
    show_reservations = args['--reservations']
    show_unused = args['--unused']
    show_unreserved = True if args['--unreserved'] else False

    # Instantiate checker
    rc = ReservationChecker(region=args['--region'])

    if show_reservations:
        table_headers = [
            'AvailabilityZone',
            'InstanceType',
            'InstanceCount',
            'Start',
            'End',
        ]

        table_data = []
        for ri in rc.reservations:
            table_row = []
            for key in table_headers:
                table_row.append(ri[key])
            table_data.append(table_row)

        # Sort results
        table_data.sort(key=lambda x: x[0] + x[1])

        print()
        print(AsciiTable(
            [table_headers] + table_data,
            "Reservations ({})".format(rc.region)).table)

    if show_unused:
        table_headers = [
            'AvailabilityZone',
            'InstanceType',
            'Count',
        ]

        table_data = []
        for az, typedict in rc.unused.iteritems():
            for instance_type, unused_count in typedict.iteritems():
                table_data.append([
                    az,
                    instance_type,
                    unused_count
                ])

        print()
        print(AsciiTable(
            [table_headers] + table_data,
            "Unused Reservations ({})".format(rc.region)).table)

    if show_unreserved:
        table_headers = [
            'AvailabilityZone',
            'InstanceType',
            'Count',
        ]

        table_data = []
        for az, typedict in rc.unreserved_grouping_older_than(
                days=int(args['--unreserved'])).iteritems():
            for instance_type, unused_count in typedict.iteritems():
                table_data.append([
                    az,
                    instance_type,
                    unused_count
                ])

        print()
        print(AsciiTable(
            [table_headers] + table_data,
            "Unreserved Instances ({})".format(rc.region)).table)