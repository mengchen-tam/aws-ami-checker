# AMI Usage Checker

Comprehensive tool to check AMI usage using both AWS Usage Reports and Reference Check APIs.

## Features

- **Usage Reports**: Track cross-account shared AMI usage
- **Reference Check**: Audit in-account resource references
- **Recommendations**: Identify safe-to-delete AMIs
- **CSV Export**: Detailed report for analysis

## Requirements

- Python 3.x with boto3
- AWS CLI v2 (for manual checks)
- Appropriate IAM permissions

## Usage

```bash
# Check specific region
/path/to/venv/bin/python3 ami_checker.py <region>

# Examples
/home/ubuntu/venv_ami/bin/python3 ami_checker.py cn-north-1
/home/ubuntu/venv_ami/bin/python3 ami_checker.py cn-northwest-1
```

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
