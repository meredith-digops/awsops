#!/usr/bin/env python

from __future__ import print_function

import boto3
import os

# Default environment vars
DEFAULT_SPOF_TAG = 'Snowflake'
DEFAULT_REGION = 'us-east-1'

def add_spof_cloudwatch_alarm(instance_list, region):

    # Get account id number from STS API
    account_id = boto3.client('sts').get_caller_identity().get('Account')

    dimensions = []
    for instance in instance_list:

        cwclient = boto3.client('cloudwatch', region_name=region)
        response = cwclient.put_metric_alarm(
            AlarmName='SnowflakeFailure'+instance,
            AlarmDescription='Alarm that triggers if a SPOF instance is has a failure',
            ActionsEnabled=True,
            AlarmActions=[
                'arn:aws:swf:'+region+':'+account_id+':action/actions/AWS_EC2.InstanceId.Recovery/1.0'
            ],
            MetricName='StatusCheckFailed_System',
            Namespace="AWS/EC2",
            Dimensions=[
                {
                    'Name': 'InstanceId',
                    'Value': instance
                }
            ],
            Statistic='Minimum',
            Period=60,
            EvaluationPeriods=5,
            Threshold=1,
            ComparisonOperator='GreaterThanThreshold'
        )

def get_spof_instance(tag_filter, region):
    ec2client = boto3.client('ec2', region_name=region)

    response = ec2client.describe_instances(
        Filters=[
            {
                'Name': 'tag:Name',
                'Values': [tag_filter]
            }
        ]
    )

    instance_list = []

    for reservation in (response["Reservations"]):
        for instance in reservation['Instances']:
            instance_list.append(instance["InstanceId"])
            
    return(instance_list)

def lambda_handler(event, context):
    spof_tag = event.get('TAG', os.environ.get('TAG', DEFAULT_SPOF_TAG))
    region = event.get('REGION', os.environ.get('REGION', DEFAULT_REGION))
    instances = get_spof_instance(spof_tag, region)
    add_spof_cloudwatch_alarm(instances, region)
    return(True)
