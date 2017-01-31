import boto3
import botocore
from ansible.plugins.lookup import LookupBase
from ansible import errors


class LookupModule(LookupBase):
    """
    Retrieve the AWS account id
    """
    def __init__(self, basedir=None, **kwargs):
        self.basedir = basedir

    def run(self, terms, inject=None, **kwargs):
        try:
            account_id = boto3.client('sts').get_caller_identity().get('Account')
            return [account_id]

        except Exception as e:
            if isinstance(e, botocore.exceptions.ClientError):
                raise e
            else:
                raise errors.AnsibleFilterError(
                    "Failed to retrieve account id"
                )
