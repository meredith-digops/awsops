#!/usr/bin/env python

from __future__ import print_function

import os.path
import sys
from tempfile import TemporaryFile
from zipfile import ZipFile

import boto3
from botocore.exceptions import ClientError

assume_role_policy_document = """{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "",
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}"""

try:
    function_name = sys.argv[1]
except IndexError:
    print('You must provide a function name as an argument to this script!')
    sys.exit(1)

function_file = os.path.join(function_name, '%s.py' % function_name)
lambda_name = 'awsops-%s' % function_name
policy_file = os.path.join(function_name, '%s.json' % function_name)
policy_name = 'lambda-%s-policy' % function_name
role_name = 'labmda-%s-role' % function_name

def already_exists(e):
    return 'already exist' in str(e)

iam = boto3.resource('iam')

try:
    role = iam.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=assume_role_policy_document
    )
except ClientError as e:
    if already_exists(e):
        role = iam.Role(role_name)

try:
    with open(policy_file) as f:
        policy_document = f.read()
        policy = iam.create_policy(
            PolicyName=policy_name,
            PolicyDocument=policy_document
        )
except ClientError as e:
    if already_exists(e):
        policy = role.Policy(policy_name)
        policy.put(
            PolicyDocument=policy_document
        )

lambda_client = boto3.client('lambda', region_name='us-east-1')

with TemporaryFile() as f:
    with ZipFile(f, 'w') as z:
        z.write(function_file, os.path.basename(function_file))

    f.seek(0)

    zipped_bytes = f.read()

    def create():
        lambda_client.create_function(
            FunctionName=lambda_name,
            Runtime='python2.7',
            Role=role.arn,
            Handler='%s.lambda_handler' % function_name,
            Description='AWS Operations: %s' % function_name,
            Timeout=60,
            MemorySize=256,
            Code={
                'ZipFile': zipped_bytes
            }
        )

    try:
        create()

    except ClientError as e:
        if already_exists(e):
            lambda_client.delete_function(
                FunctionName=lambda_name
            )
            create()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
