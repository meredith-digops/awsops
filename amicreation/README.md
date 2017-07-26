# amicreation

AWS Lambda function to create EBS AMIs.

## Requirements

The script depends on [boto3](http://boto3.readthedocs.org/en/latest/).  It is provided by AWS lambda at runtime but the library is needed to execute the `upload.py` script locally.

## Installation

Set your AWS token via environment variables:

```bash
$ export AWS_DEFAULT_REGION=<region>
$ export AWS_ACCESS_KEY_ID=<XXXXXXXXXXXXXXXX>
$ export AWS_SECRET_ACCESS_KEY=<XXXXXXXXXXXXXXXX>
```

Run the `upload.py` script to setup IAM roles, policies, and lambda function for execution.

```bash
$ python upload.py amicreation
```

## Usage

### Dry Run

A dry run can be executed by setting the `DryRun` attribute to `true`.

```json
{
  "DryRun": true
}
```

### Filters

By default only instances with the `ops:snapshot` tag set will be affected.  The lambda function can be passed filters at runtime to change which EC2 instances are affected:

```json
{
  "Filters": [
        {
            "Name": "tag:Name",
            "Values": [
                "*NFS*"
            ]
        }
    ]
}
```

See [boto3 EC2 service resources](http://boto3.readthedocs.org/en/latest/reference/services/ec2.html#service-resource) for full documentation of the supported filters.

### AMI Creation

AMI creation is opted into by adding the `ops:snapshot` tag to an EC2 instance with `Daily` as the value. Currently, the script will not enforce the `Daily` value, but it should be present for forward compatibility. The script will create an AMI for the instance and will assign a default `ops:retention` tag with a value of 30 to facilitate cleanup in the future.

## Scheduling

Scheduled execution must be set up manually in the lambda console until boto3 adds support. The schedule should be configured to run daily until additional schedule support is added.
