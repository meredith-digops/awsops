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
from copy import copy
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from dateutil import tz


log = logging.getLogger(__name__)


DATE_FORMAT = '%Y-%m-%d'
LOCAL_TZ = tz.tzlocal()
ZERO = timedelta(0)

DEFAULT_SNS_SUBJECT = "EC2 Instance Reservation Report ({account}, {region})"

LAMBDA_DEFAULTS = {
    'Local_TZ': 'America/Chicago',
    'SNS_Send': True,
    # Define an SNS_Topic by default, or during Lambda invocation to specify
    # what topic should receive the summary.
    # 'SNS_Topic':

    # Define an explicit SNS_Subject to be sent, otherwise the default will
    # be "EC2 Instance Reservation Report ({account_alias}, {region})"
    #'SNS_Subject':
    'SES': {
        'Source': 'no-reply@your.ses.domain.com',
        'Destination': {
            'ToAddresses': [
                'awsops@your.domain.com',
            ],
        },
        'Subject': 'EC2 Instance Reservation Report',
    },
    'Region': None,
    'ReportOn': [
        'unused',
        'unreserved',
    ],
    'UnreservedDays': 90,
}


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


class ReservationDisplay(object):
    def __init__(self, checker):
        """
        Instantiates a new display instance
        :param checker: Reservation checker
        :type checker: ReservationChecker
        """
        self.checker = checker

    @property
    def reservation_data(self):
        table_headers = [
            'AvailabilityZone',
            'InstanceType',
            'InstanceCount',
            'Start',
            'End',
        ]

        table_data = []
        for ri in self.checker.reservations:
            table_row = []
            for key in table_headers:
                col_value = ri[key]

                if type(col_value) is datetime:
                    # Return datetimes in a prettier fashion
                    col_value = col_value.replace() \
                        .astimezone(LOCAL_TZ) \
                        .strftime(DATE_FORMAT)

                table_row.append(col_value)
            table_data.append(table_row)

        return [table_headers] + sorted(table_data,
                                        key=lambda x: x[0] + x[1])

    @property
    def unreserved_data(self):
        table_headers = [
            'AvailabilityZone',
            'InstanceType',
            'InstanceCount',
        ]

        # Reduce the unreserved instances to a dict grouping that a table
        # can be built from.
        unreserved_instances = {}
        for instance in self.checker.unreserved:
            instance_az = instance.placement['AvailabilityZone']
            instance_type = instance.instance_type

            if instance_az not in unreserved_instances:
                unreserved_instances[instance_az] = {}

            if instance_type not in unreserved_instances[instance_az]:
                unreserved_instances[instance_az][instance_type] = 0

            unreserved_instances[instance_az][instance_type] += 1

        table_data = []
        for az, instance_res in unreserved_instances.iteritems():
            for instance_type, instance_count in instance_res.iteritems():
                table_data.append([
                    az,
                    instance_type,
                    instance_count,
                ])

        return [table_headers] + sorted(table_data,
                                        reverse=True,
                                        key=lambda x: x[2])

    @property
    def unused_data(self):
        table_headers = [
            'AvailabilityZone',
            'InstanceType',
            'InstanceCount',
        ]

        table_data = []
        for az, instance_res in self.checker.unused.iteritems():
            for instance_type, instance_count in instance_res.iteritems():
                table_data.append([
                    az,
                    instance_type,
                    instance_count,
                ])

        return [table_headers] + sorted(table_data,
                                        reverse=True,
                                        key=lambda x: x[2])


class ReservationDisplayTerminal(ReservationDisplay):
    @property
    def reservation_table(self):
        return "\n".join([
            "",
            AsciiTable(self.reservation_data,
                       "Reservations ({})".format(self.checker.region)).table
        ])

    @property
    def unreserved_table(self):
        return "\n".join([
            "",
            AsciiTable(self.unreserved_data,
                       "Unreserved ({})".format(self.checker.region)).table
        ])

    @property
    def unused_table(self):
        return "\n".join([
            "",
            AsciiTable(self.unused_data,
                       "Unused ({})".format(self.checker.region)).table
        ])


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

    def __init__(self, unreserved_days=None, **kwargs):
        """
        Instantiate class to recon used/unused instance reservations

        :param unreserved_days: Number of days to consider an instance unreserved
        :type unreserved_days: int
        :param region: Explicit EC2 region to examine. Uses config as default
        :type region: None|str
        """
        self.unreserved_days = unreserved_days
        self._reservations = None
        self._unreserved = None
        self._unused = None

        # Instantiate client
        self.ec2 = boto3.resource('ec2', **kwargs)

    @property
    def region(self):
        return self.ec2.meta.client.meta.region_name

    def _find_unused_or_unreserved(self):
        """
        Filters through all instances to propogate `unused` and `unreserved`
        """
        # Determine what AZs to look through for instances
        reserved_azs = [ri['AvailabilityZone'] for ri in self.reservations]
        log.debug("Filtering through AZ: {}".format(reserved_azs))

        # Construct a request to find all EC2 instances that are not stopped or
        # terminated
        all_instances = [i for i in self.ec2.instances.filter(**{
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
        })]

        # Order instances based on their creation time
        all_instances = sorted(all_instances, key=lambda i: i.launch_time)

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

        # Determine most recent datetime for which instances started on or
        # before should be considered for the unreserved instance report.
        if self.unreserved_days is not None:
            launched_before = datetime.now(UTC()) \
                    - timedelta(int(self.unreserved_days))

        # Iterate through all instances and tick off the ones that are
        # reserved
        self._unreserved = []
        for instance in all_instances:
            az = instance.placement['AvailabilityZone']
            instance_type = instance.instance_type

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
                if self.unreserved_days is not None \
                        and instance.launch_time <= launched_before:
                    # Old enough to be reported on
                    self._unreserved.append(instance)

    @property
    def reservations(self):
        if self._reservations is None:
            log.debug("Lazy loading reservations...")
            self._reservations = self.fetch_active_instance_reservations(
                self.ec2.meta.client)
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


def get_aws_account_id():
    """ Returns the AWS account Id
    """
    return boto3.client('sts').get_caller_identity() \
        .get('Account')


def lambda_handler(event, context):
    """
    Assesses instance reservations and produces a report on them
    """
    import json

    event_settings = copy(LAMBDA_DEFAULTS)
    event_settings.update(event)

    # Set the local timezone for datetime formatting if the parameter was
    # passed to the Lambda function
    if 'Local_TZ' in event_settings:
        LOCAL_TZ = tz.gettz(event_settings['Local_TZ'])

    # Instatiate checker
    rc = ReservationChecker(
            unreserved_days=int(event_settings['UnreservedDays']),
            region_name=event_settings['Region'])

    # Should a report be generated?
    report_text = None
    if 'ReportOn' in event_settings:
        # Instantiate display class
        rcd = ReservationDisplay(rc)

        # Compose the report text
        report_text = "\n".join([
            '###############################',
            '# Instance Reservation Report #',
            '###############################',
            '',
            '',
        ])

        for report_item in event_settings['ReportOn']:
            report_text += "\n".join([
                ":" * (4 + len(report_item)),
                ": " + report_item + " :",
                ":" * (4 + len(report_item)),
                "",
            ])
            for data_row in  getattr(rcd, report_item + '_data'):
                report_text += str(data_row) + "\n"
            report_text += "\n"

        print(report_text)

    if report_text is not None and event_settings['SNS_Send']:
        print("\n\nSending report to SNS:" + event_settings['SNS_Topic'])
        sns = boto3.client('sns', region_name=event_settings['Region'])
        resp = sns.publish(
            TargetArn=event_settings['SNS_Topic'],
            Subject=event_settings.get('SNS_Subject', DEFAULT_SNS_SUBJECT).format(
                account=get_aws_account_id(),
                region=event_settings['Region'] or sns.meta.region_name),
            Message=report_text)
        print(json.dumps(resp,
                         indent=4,
                         separators=(',', ': '),
                         sort_keys=False))


if __name__ == '__main__':
    from docopt import docopt
    from terminaltables import AsciiTable

    # Define explicit client arguments, such as region, that will be used
    # to instantiate the boto3 client
    client_args = {}

    # Parse command line arguments
    args = docopt(__doc__, version='dev')
    show_reservations = args['--reservations']
    show_unused = args['--unused']
    show_unreserved = True if args['--unreserved'] else False

    # Instantiate checker
    rc = ReservationChecker(
        unreserved_days=args['--unreserved'],
        region_name=args['--region'])

    # Instantiate display class
    rcd = ReservationDisplayTerminal(rc)

    if show_reservations:
        print(rcd.reservation_table)

    if show_unused:
        print(rcd.unused_table)

    if show_unreserved:
        print(rcd.unreserved_table)
