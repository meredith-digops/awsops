# snapshotcleanup

AWS Lambda function to cleanup EBS snapshots.

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
$ python upload.py snapshotcleanup
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

By default only images with the `ops:retention` tag set will be affected.  The lambda function can be passed filters at runtime to change which EC2 AMIs are affected:

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

### Retention

Snapshot retention is looked up via the `ops:retention` tag if available.  Otherwise the retention is configurable at runtime via the `Retention` property.  It defaults to `None` which means only snapshots with the `ops:retention` tag will be explicitly affected:

```json
{
  "Retention": 60
}
```

## Scheduling

Scheduled execution must be set up manually in the lambda console until boto3 adds support.
