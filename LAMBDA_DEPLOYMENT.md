# Lambda Deployment Guide

Deploy AMI Usage Checker as a Lambda function with cross-account support.

## Architecture

```
┌─────────────────┐
│  Account A      │
│  (Lambda)       │
│                 │
│  ┌───────────┐  │
│  │ Lambda    │  │──AssumeRole──┐
│  │ Function  │  │              │
│  └───────────┘  │              │
└─────────────────┘              │
                                 ▼
                    ┌─────────────────────┐
                    │  Account B          │
                    │  (Target)           │
                    │                     │
                    │  ┌───────────────┐  │
                    │  │ AMIChecker    │  │
                    │  │ Role          │  │
                    │  └───────────────┘  │
                    │                     │
                    │  Check AMIs         │
                    └─────────────────────┘
```

## Prerequisites

- AWS SAM CLI installed
- Python 3.12
- AWS credentials configured

## Deployment Steps

### 1. Deploy Lambda Function (Account A)

```bash
# Build and deploy
sam build
sam deploy --guided

# Follow prompts:
# - Stack Name: ami-checker
# - AWS Region: us-east-1
# - AssumeRoleName: AMICheckerRole
# - Confirm changes: Y
# - Allow SAM CLI IAM role creation: Y
```

**Note the Lambda function's AWS Account ID from the output.**

### 2. Deploy Cross-Account Role (Account B, C, ...)

Deploy this in each target account you want to check:

```bash
aws cloudformation deploy \
  --template-file cross-account-role.yaml \
  --stack-name ami-checker-role \
  --parameter-overrides \
      TrustedAccountId=<LAMBDA_ACCOUNT_ID> \
      RoleName=AMICheckerRole \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

Replace `<LAMBDA_ACCOUNT_ID>` with Account A's ID.

## Usage

### Same Account Check

```bash
aws lambda invoke \
  --function-name AMIUsageChecker \
  --payload '{
    "region": "us-east-1",
    "check_types": ["usage", "reference"]
  }' \
  response.json

cat response.json | jq .
```

### Cross-Account Check

```bash
aws lambda invoke \
  --function-name AMIUsageChecker \
  --payload '{
    "region": "us-east-1",
    "target_account_id": "123456789012",
    "assume_role_name": "AMICheckerRole",
    "check_types": ["usage", "reference"]
  }' \
  response.json

cat response.json | jq .
```

### Check Multiple Accounts

```bash
#!/bin/bash
ACCOUNTS=("123456789012" "234567890123" "345678901234")

for account in "${ACCOUNTS[@]}"; do
  echo "Checking account: $account"
  aws lambda invoke \
    --function-name AMIUsageChecker \
    --payload "{
      \"region\": \"us-east-1\",
      \"target_account_id\": \"$account\",
      \"assume_role_name\": \"AMICheckerRole\"
    }" \
    "response_${account}.json"
done
```

## Event Structure

```json
{
  "region": "us-east-1",              // Required: AWS region to check
  "target_account_id": "123456789012", // Optional: for cross-account
  "assume_role_name": "AMICheckerRole", // Optional: role name in target account
  "check_types": ["usage", "reference"] // Optional: default both
}
```

## Response Structure

```json
{
  "statusCode": 200,
  "body": {
    "region": "us-east-1",
    "target_account": "123456789012",
    "timestamp": "2025-12-03T07:00:00",
    "usage_reports": [
      {
        "ami_id": "ami-xxx",
        "ami_name": "my-ami",
        "check_type": "UsageReport",
        "account_id": "999888777666",
        "resource_type": "ec2:Instance",
        "count": 2
      }
    ],
    "reference_checks": [
      {
        "ami_id": "ami-yyy",
        "ami_name": "another-ami",
        "check_type": "ReferenceCheck",
        "resource_type": "ec2:Instance",
        "resource_id": "i-xxx",
        "resource_arn": "arn:aws:ec2:..."
      }
    ],
    "recommendations": {
      "total_amis": 10,
      "shared_with_accounts": 2,
      "used_in_account": 3,
      "completely_unused": 5,
      "safe_to_delete": [
        {
          "ami_id": "ami-zzz",
          "ami_name": "old-ami",
          "creation_date": "2023-01-01"
        }
      ],
      "in_use": [
        {
          "ami_id": "ami-aaa",
          "ami_name": "active-ami"
        }
      ]
    }
  }
}
```

## Scheduled Execution

Enable the EventBridge schedule in the SAM template:

```yaml
Events:
  ScheduledCheck:
    Type: Schedule
    Properties:
      Schedule: cron(0 2 ? * MON *)  # Every Monday at 2 AM UTC
      Enabled: true  # Change to true
```

Then redeploy:
```bash
sam deploy
```

## Cost Considerations

- **Lambda**: ~$0.20 per 1M requests + compute time
- **API Calls**: Free (EC2 describe operations)
- **CloudWatch Logs**: ~$0.50/GB ingested

**Estimated monthly cost for weekly checks across 10 accounts: < $1**

## Troubleshooting

### Permission Denied

Ensure the cross-account role is deployed and the trust relationship includes the Lambda account.

### Timeout

Increase Lambda timeout in `template.yaml`:
```yaml
Timeout: 600  # 10 minutes
```

### No AMIs Found

Verify the Lambda is checking the correct region and account.

## Security Best Practices

1. **Least Privilege**: Role only has read permissions
2. **External ID**: Add external ID for additional security
3. **CloudTrail**: Enable CloudTrail to audit cross-account access
4. **VPC**: Deploy Lambda in VPC if required by security policy

## Clean Up

```bash
# Delete Lambda stack
sam delete --stack-name ami-checker

# Delete cross-account roles (in each target account)
aws cloudformation delete-stack --stack-name ami-checker-role
```
