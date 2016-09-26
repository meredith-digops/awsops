Config Monitoring
=================
This section of the codebase will assist in ensuring that various components'
configurations are in a desired state by employing the
[AWS Config](https://aws.amazon.com/config/) service.

Currently, the service cannot support a large number of resource types so the
functionality of this code is a bit limited. See the [references](#references)
section for details on what is supported and what isn't.

Usage (Initial Setup)
---------------------

**Initial Setup**

```sh
aws cloudformation create-stack \
    --stack-name AWSConfigStack \
    --capabilities CAPABILITY_IAM \
    --template-body file://./init.json
```

**Updating AWS Config Stack**

```sh
aws cloudformation update-stack \
    --stack-name AWSConfigStack \
    --capabilities CAPABILITY_IAM \
    --template-body file://./init.json
```

**Usage Notes**

- All input parameters have a default value, they can be modified by adding the
`--parameters` argument to the above invocations.
- The `CAPABILITY_IAM` capability is required as this template addresses the
creation of the role required for the AWS Config service to interact with the
other various resources.

Usage (Tag Monitoring)
----------------------

Monitoring for the presence of tags can be established by using the 
[tag-monitor.json](tag-monitor.json) template and passing one-or-more tags
in as parameters. There are a maximum of six supported tags that can be
checked in a single rule.  Additionally, checking of instances *and* volumes
is supported by default, but either can be disabled by passing in a parameter
to disable them.

The check is supported by one of the
[managed rules](http://docs.aws.amazon.com/config/latest/developerguide/evaluate-config_use-managed-rules.html)
that AWS maintains.

For example, the following invocation would stand up a config rule to check
for all instances having the `PoC` & `CostCenter` tags:

```sh
aws cloudformation create-stack \
    --stack-name AWSConfigTagMonitor \
    --template-body file://./awsconfig/tag-monitor.json \
    --parameters \
        ParameterKey=Tag1Name,ParameterValue=PoC \
        ParameterKey=Tag2Name,ParameterValue=CostCenter \
        ParameterKey=MonitorVolumes,ParameterValue=n
```

## References
- [[stelligent.com] Security Integration Testing (Part 1): Resource Monitoring with AWS Config Rules](https://stelligent.com/2016/04/19/security-integration-testing-part-1/)
- [[docs.aws.amazon.com] AWS Config - Supported Resource Types](http://docs.aws.amazon.com/config/latest/developerguide/resource-config-reference.html#supported-resources)
- [[aws.amazon.com] AWS Blog - AWS Config Rules - Dynamic Compliance Checking for Cloud Resources](https://aws.amazon.com/blogs/aws/aws-config-rules-dynamic-compliance-checking-for-cloud-resources/)
- [[cloudonaut.io] Optional Parameter in CloudFormation](https://cloudonaut.io/optional-parameter-in-cloudformation/)
