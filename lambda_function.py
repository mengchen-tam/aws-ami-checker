"""
AWS Lambda AMI Usage Checker
Supports cross-account checks via AssumeRole
"""

import boto3
import json
import os
from datetime import datetime
from collections import defaultdict

def get_session(account_id=None, role_name=None, region='us-east-1'):
    """Get boto3 session for target account"""
    if account_id and role_name:
        # Cross-account access
        sts = boto3.client('sts')
        role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"
        
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='AMICheckerSession'
        )
        
        credentials = response['Credentials']
        return boto3.Session(
            aws_access_key_id=credentials['AccessKeyId'],
            aws_secret_access_key=credentials['SecretAccessKey'],
            aws_session_token=credentials['SessionToken'],
            region_name=region
        )
    else:
        # Same account
        return boto3.Session(region_name=region)

def check_usage_reports(ec2, amis):
    """Check cross-account AMI usage"""
    results = []
    report_map = {}
    
    for ami in amis:
        ami_id = ami['ImageId']
        try:
            response = ec2.create_image_usage_report(
                ImageId=ami_id,
                ResourceTypes=[
                    {'ResourceType': 'ec2:Instance'},
                    {'ResourceType': 'ec2:LaunchTemplate'}
                ]
            )
            report_map[ami_id] = {
                'report_id': response['ReportId'],
                'ami_name': ami.get('Name', 'N/A')
            }
        except Exception as e:
            print(f"Failed to create report for {ami_id}: {e}")
    
    if not report_map:
        return results
    
    # Wait for reports
    import time
    time.sleep(30)
    
    # Retrieve results
    for ami_id, info in report_map.items():
        try:
            entries_resp = ec2.describe_image_usage_report_entries(
                ReportIds=[info['report_id']]
            )
            
            for entry in entries_resp.get('ImageUsageReportEntries', []):
                results.append({
                    'ami_id': ami_id,
                    'ami_name': info['ami_name'],
                    'check_type': 'UsageReport',
                    'account_id': entry.get('AccountId'),
                    'resource_type': entry.get('ResourceType'),
                    'count': entry.get('UsageCount', 0)
                })
        except Exception as e:
            print(f"Error retrieving report for {ami_id}: {e}")
    
    return results

def check_references(ec2, amis):
    """Check in-account AMI references"""
    results = []
    ami_ids = [ami['ImageId'] for ami in amis]
    
    try:
        response = ec2.describe_image_references(
            ImageIds=ami_ids,
            IncludeAllResourceTypes=True
        )
        
        ami_map = {ami['ImageId']: ami for ami in amis}
        
        for ref in response.get('ImageReferences', []):
            ami_id = ref['ImageId']
            results.append({
                'ami_id': ami_id,
                'ami_name': ami_map[ami_id].get('Name', 'N/A'),
                'check_type': 'ReferenceCheck',
                'resource_type': ref['ResourceType'],
                'resource_id': ref['Arn'].split('/')[-1],
                'resource_arn': ref['Arn']
            })
    except Exception as e:
        print(f"Error checking references: {e}")
    
    return results

def generate_recommendations(usage_results, ref_results, amis):
    """Generate cleanup recommendations"""
    ami_map = {ami['ImageId']: ami for ami in amis}
    
    used_in_usage = set(r['ami_id'] for r in usage_results)
    used_in_refs = set(r['ami_id'] for r in ref_results)
    all_ami_ids = set(ami_map.keys())
    
    unused = all_ami_ids - used_in_usage - used_in_refs
    
    return {
        'total_amis': len(all_ami_ids),
        'shared_with_accounts': len(used_in_usage),
        'used_in_account': len(used_in_refs),
        'completely_unused': len(unused),
        'safe_to_delete': [
            {
                'ami_id': ami_id,
                'ami_name': ami_map[ami_id].get('Name', 'N/A'),
                'creation_date': ami_map[ami_id].get('CreationDate', 'N/A')
            }
            for ami_id in sorted(unused)
        ],
        'in_use': [
            {
                'ami_id': ami_id,
                'ami_name': ami_map[ami_id].get('Name', 'N/A')
            }
            for ami_id in sorted(used_in_refs)
        ]
    }

def lambda_handler(event, context):
    """
    Lambda handler
    
    Event structure:
    {
        "region": "us-east-1",              # Required
        "target_account_id": "123456789012", # Optional for cross-account
        "assume_role_name": "AMICheckerRole", # Optional for cross-account
        "check_types": ["usage", "reference"] # Optional, default both
    }
    """
    
    # Parse input
    region = event.get('region', os.environ.get('AWS_REGION', 'us-east-1'))
    target_account = event.get('target_account_id')
    role_name = event.get('assume_role_name', os.environ.get('ASSUME_ROLE_NAME'))
    check_types = event.get('check_types', ['usage', 'reference'])
    
    print(f"Checking AMIs in region: {region}")
    if target_account:
        print(f"Cross-account check: {target_account}")
    
    try:
        # Get session
        session = get_session(target_account, role_name, region)
        ec2 = session.client('ec2')
        
        # Get AMIs
        response = ec2.describe_images(Owners=['self'])
        amis = response['Images']
        
        print(f"Found {len(amis)} AMI(s)")
        
        if not amis:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'No AMIs found',
                    'region': region
                })
            }
        
        # Run checks
        usage_results = []
        ref_results = []
        
        if 'usage' in check_types:
            print("Running Usage Reports check...")
            usage_results = check_usage_reports(ec2, amis)
        
        if 'reference' in check_types:
            print("Running Reference Check...")
            ref_results = check_references(ec2, amis)
        
        # Generate recommendations
        recommendations = generate_recommendations(usage_results, ref_results, amis)
        
        # Build response
        result = {
            'region': region,
            'target_account': target_account or 'current',
            'timestamp': datetime.utcnow().isoformat(),
            'usage_reports': usage_results,
            'reference_checks': ref_results,
            'recommendations': recommendations
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'region': region
            })
        }
