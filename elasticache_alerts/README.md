# elasticache_alerts

Script that ingests SNS messages from ElastiCache, filters out known
or insignificant events, and relays the remaining events to a separate
SNS topic.

This allows for alerting to significant/critical events.

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
$ python upload.py elasticache_alerts
```

There are several facets of installation that _are not_ addressed by this script:

- Creation of SNS topic
- Configuration of ElastiCache to use the SNS topic
- Creation of SNS topic to relay important messages to
- Configuration of `RELAY_TOPIC` and `RELAY_MESSAGES` environmental variables
for Lambda execution.

## Usage

### Dry Run

There is no DryRun supported by this API.

### Lambda Settings

| Name | Descrption |
| ---- | ---------- |
| `RELAY_TOPIC` | SNS ARN to relay important messages to |
| `RELAY_MESSAGES` | List of message types to relay |

Example `RELAY_MESSAGES`:

```
"elasticache:addcachenodecomplete","elasticache:cacheclusterparameterschanged","elasticache:cacheclusterprovisioningcomplete","elasticache:cacheclusterscalingcomplete","elasticache:cacheclustersecuritygroupmodified","elasticache:cachenodereplacecomplete","elasticache:createreplicationgroupcomplete","elasticache:deletecacheclustercomplete","elasticache:removecachenodecomplete","elasticache:replicationgroupscalingcomplete","elasticache:snapshotcomplete"
```

**Note:** `RELAY_MESSAGES` must be compliant input for a JSON list and each
message type should be in all lowercase.

A full listing of events can be found in
[Event Notifications and Amazon SNS](http://docs.aws.amazon.com/AmazonElastiCache/latest/UserGuide/ElastiCacheSNS.html).
