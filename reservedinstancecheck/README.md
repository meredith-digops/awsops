# reservedinstancecheck

Scripts to enumerate EC2 instance reservations and compare that to what
instances are actually in-use.
account has reached it's limit. Or to explicitly clean them up.

## Requirements

The script depends on [boto3](http://boto3.readthedocs.org/en/latest/).  It is
provided by AWS lambda at runtime but the library is needed to execute the
`upload.py` script locally.

## Installation

Set your AWS token via environment variables:

```bash
$ export AWS_DEFAULT_REGION=<region>
$ export AWS_ACCESS_KEY_ID=<XXXXXXXXXXXXXXXX>
$ export AWS_SECRET_ACCESS_KEY=<XXXXXXXXXXXXXXXX>
```

Run the `upload.py` script to setup IAM roles, policies, and lambda function for execution.

```bash
$ python upload.py reservedinstancecheck
```

## Usage

### Dry Run

There is no DryRun supported by this API.

### CLI Usage

```sh
reservedinstancecheck - Checks compliance for reserved instance use

USAGE: reservedinstancecheck [options]

Options:
    -h, --help              Show this dialog

    -r, --region REGION     AWS region to examine
    -R, --reservations      Show active reservations
    -u, --unused            Show unused reservations
    -U, --unreserved DAYS   Show instances launch >= DAYS ago that do not have
                            an active reservation
```

## Scheduling

Scheduled execution must be set up manually in the lambda console until boto3
adds support.
