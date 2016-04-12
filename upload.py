#!/usr/bin/env python

from __future__ import print_function

import os
import os.path
import sys
from tempfile import TemporaryFile
from zipfile import ZipFile

import boto3
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader

from config import get_config

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
role_name = 'lambda-%s-role' % function_name

# Render policy document with Jinja2 and configparser object
jinja2_env = Environment(loader=FileSystemLoader('.'))
policy_file = os.path.join(function_name, '%s.json' % function_name)
policy_name = 'lambda-%s-policy' % function_name
policy_template = jinja2_env.get_template(policy_file)
policy_document = policy_template.render(**get_config())


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

print('Configured IAM role: %s' % role_name)

try:
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

print('Configured IAM policy: %s' % policy_name)

lambda_client = boto3.client('lambda', region_name='us-east-1')

with TemporaryFile() as f:
    with ZipFile(f, 'w') as z:
        z.write(function_file, os.path.basename(function_file))
        #z.write('config.py', 'config.py')

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

    print('Configured lambda function: %s' % lambda_name)

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
