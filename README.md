# AMI Usage Checker

Comprehensive tool to check AMI usage using both AWS Usage Reports and Reference Check APIs.

## Features

- **Usage Reports**: Track cross-account shared AMI usage
- **Reference Check**: Audit in-account resource references
- **Recommendations**: Identify safe-to-delete AMIs
- **CSV Export**: Detailed report for analysis
- **Lambda Support**: Deploy as serverless function with cross-account capability

## Deployment Options

### Option 1: CLI Tool (Local Execution)

**Requirements:**
- Python 3.x with boto3
- AWS CLI v2
- Appropriate IAM permissions

**Usage:**
```bash
# Check specific region
/path/to/venv/bin/python3 ami_checker.py <region>

# Examples
python3 ami_checker.py us-east-1
python3 ami_checker.py cn-north-1
```

### Option 2: Lambda Function (Serverless)

**Features:**
- Cross-account AMI checking via AssumeRole
- Scheduled execution support
- JSON output for automation
- Cost-effective (~$1/month for 10 accounts)

**Quick Deploy:**
```bash
sam build
sam deploy --guided
```

**See [LAMBDA_DEPLOYMENT.md](LAMBDA_DEPLOYMENT.md) for detailed instructions.**

## Understanding the Results

### Usage Reports
- **Purpose**: Track which AWS accounts are using your shared AMIs
- **Shows**: Cross-account usage (when you share AMIs with other accounts)
- **Resource Types**: EC2 instances, Launch templates

### Reference Check
- **Purpose**: Audit which resources in YOUR account reference AMIs
- **Shows**: In-account usage (your own resources)
- **Resource Types**: EC2 instances, Launch templates, SSM parameters, Image Builder recipes

### Recommendations

1. **SAFE TO DELETE**: AMIs not used anywhere (neither shared nor referenced)
2. **SHARED BUT NOT USED IN YOUR ACCOUNT**: Check with other accounts before unsharing
3. **IN USE IN YOUR ACCOUNT**: Do NOT delete these AMIs

## Output Files

- Console output with detailed results
- CSV report: `ami_check_report_<region>_<timestamp>.csv`

## Key Differences

| Feature | Usage Reports | Reference Check |
|---------|--------------|-----------------|
| Scope | Cross-account | In-account |
| Use Case | Shared AMIs | Account audit |
| Resource Types | 2 types | 5 types |
| Delay | 24 hours | Real-time |

## AWS Documentation

- [AMI Usage Reports](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/your-ec2-ami-usage.html)
- [AMI Reference Check](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-ami-references.html)
