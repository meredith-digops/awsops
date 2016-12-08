# launchconfigcleanup

AWS Lambda function to cleanup autoscaling LaunchConfiguration resources if an
account has reached it's limit. Or to explicitly clean them up.

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
$ python upload.py launchconfigcleanup
```

## Usage

### Dry Run

There is no DryRun supported by this API.

### CLI Usage

```sh
launchconfigcleanup - Assists in cleaning up unused LaunchConfigurations

Usage: launchconfigcleanup.py [options]

Options:
    -a, --minage DAYS   Minimum number of days a LaunchConfiguration must be
                        to be considered a deletion candidate.

    -D, --delete        Delete a candidate if one is present

    -n, --maxlcs NUM    Maximum number of LaunchConfigurations allowed in the
                        AWS account. A candidate will only be presented if the
                        account is at its limit.
```

## Scheduling

Scheduled execution must be set up manually in the lambda console until boto3 adds support.
