from __future__ import print_function
import boto3
import json
import os


def process_record(record, sns, no_relay_messages, relay_topic_arn=None):
    """
    Filters "nominal" messages and relays import ones to another SNS topic

    :param record: SNS record from ElastiCache
    :type record: dict
    :param sns: boto3 SNS client
    :param no_relay_messages: List of message types to relay
    :param no_relay_topic_arn: ARN to relay unknown/critical messages to
    :type relay_topic_arn: str|None
    """
    assert 'Sns' in record, \
        "Record is not an event from SNS"

    # Parse the message from SNS
    raw_sns_record = record['Sns']
    message = json.loads(raw_sns_record['Message'])

    # Determine if we should relay this record or not
    should_relay = False

    for k in message.keys():
        if k.lower() not in no_relay_messages:
            # This is an important message
            should_relay = True

        # Break early if we should already be relaying the message
        if should_relay:
            break

    if not should_relay:
        # Don't bother relaying this message
        return False

    # Compose message subject for VictorOps topic
    message_subject = ";".join([
        "{} - {}".format(k, v)
        for k, v in message.iteritems()
    ])
    print("Relaying message:\n" + json.dumps(message))

    if not relay_topic_arn:
        # Message SHOULD be relayed, but no relay topic ARN received
        raise Exception("No relay ARN passed to relay message to: " + json.dumps(message))

    sns.publish(
        TopicArn=relay_topic_arn,
        Subject=message_subject,
        Message=json.dumps(message, indent=4))


def lambda_handler(event, context):
    """
    Handles inbound SNS events from the ElastiCache service
    """
    assert 'Records' in event, \
        "No event records key relayed"
    assert len(event['Records']) > 0, \
        "No event records relayed"

    sns = boto3.client('sns')
    relay_topic_arn = os.environ.get('RELAY_TOPIC', None)
    no_relay_messages_json = json.loads(
        '{"no_relay_messages": [' + os.environ.get('NO_RELAY_MESSAGES') + ']}'
    )
    no_relay_messages = no_relay_messages_json['no_relay_messages']

    for record in event['Records']:
        process_record(record, sns, no_relay_messages, relay_topic_arn)
