#!/usr/bin/env python3
"""
Comprehensive AMI Usage Checker
Combines both Usage Reports (for shared AMIs) and Reference Check (for account audit)
"""

import boto3
import csv
import sys
from datetime import datetime
from collections import defaultdict

def check_usage_reports(ec2, amis, region):
    """Check cross-account AMI usage via Usage Reports"""
    print("\n" + "="*70)
    print("USAGE REPORTS - Cross-Account Shared AMI Usage")
    print("="*70)
    print("Purpose: Track which AWS accounts are using your shared AMIs\n")
    
    results = []
    ami_ids = [ami['ImageId'] for ami in amis]
    
    # Create reports
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
                'ami_name': ami.get('Name', 'N/A'),
                'creation_date': ami.get('CreationDate', 'N/A')
            }
        except Exception as e:
            print(f"  ✗ Failed to create report for {ami_id}: {e}")
    
    if not report_map:
        print("No reports created")
        return results
    
    print(f"Created {len(report_map)} reports. Waiting 30 seconds...\n")
    import time
    time.sleep(30)
    
    # Retrieve report details
    for ami_id, info in report_map.items():
        report_id = info['report_id']
        ami_name = info['ami_name']
        
        try:
            status_resp = ec2.describe_image_usage_reports(ReportIds=[report_id])
            state = status_resp['ImageUsageReports'][0]['State']
            
            if state == 'available':
                entries_resp = ec2.describe_image_usage_report_entries(ReportIds=[report_id])
                entries = entries_resp.get('ImageUsageReportEntries', [])
                
                if entries:
                    print(f"✓ {ami_id} ({ami_name})")
                    for entry in entries:
                        account = entry.get('AccountId')
                        rtype = entry.get('ResourceType')
                        count = entry.get('UsageCount', 0)
                        print(f"    Account {account}: {rtype} count={count}")
                        results.append({
                            'ami_id': ami_id,
                            'ami_name': ami_name,
                            'check_type': 'Usage Report',
                            'account_id': account,
                            'resource_type': rtype,
                            'count': count
                        })
                else:
                    print(f"  {ami_id} ({ami_name}): No cross-account usage")
            else:
                print(f"  {ami_id}: Report state={state}")
        except Exception as e:
            print(f"  ✗ Error retrieving report for {ami_id}: {e}")
    
    return results

def check_references(ec2, amis, region):
    """Check in-account AMI references via Reference Check"""
    print("\n" + "="*70)
    print("REFERENCE CHECK - In-Account Resource Audit")
    print("="*70)
    print("Purpose: Audit which resources in YOUR account reference AMIs\n")
    
    results = []
    ami_ids = [ami['ImageId'] for ami in amis]
    
    try:
        response = ec2.describe_image_references(
            ImageIds=ami_ids,
            IncludeAllResourceTypes=True
        )
        
        ami_map = {ami['ImageId']: ami for ami in amis}
        refs_by_ami = defaultdict(list)
        
        for ref in response.get('ImageReferences', []):
            refs_by_ami[ref['ImageId']].append(ref)
        
        for ami in amis:
            ami_id = ami['ImageId']
            ami_name = ami.get('Name', 'N/A')
            refs = refs_by_ami.get(ami_id, [])
            
            if refs:
                print(f"✓ {ami_id} ({ami_name}): {len(refs)} reference(s)")
                by_type = defaultdict(list)
                for ref in refs:
                    by_type[ref['ResourceType']].append(ref['Arn'])
                
                for rtype, arns in by_type.items():
                    print(f"    {rtype}: {len(arns)}")
                    for arn in arns:
                        resource_id = arn.split('/')[-1]
                        print(f"      - {resource_id}")
                        results.append({
                            'ami_id': ami_id,
                            'ami_name': ami_name,
                            'check_type': 'Reference Check',
                            'resource_type': rtype,
                            'resource_id': resource_id,
                            'resource_arn': arn
                        })
            else:
                print(f"  {ami_id} ({ami_name}): No in-account references")
        
    except Exception as e:
        print(f"✗ Error checking references: {e}")
    
    return results

def generate_recommendations(usage_results, ref_results, amis):
    """Generate cleanup recommendations"""
    print("\n" + "="*70)
    print("RECOMMENDATIONS")
    print("="*70)
    
    ami_map = {ami['ImageId']: ami for ami in amis}
    
    # AMIs with usage
    used_in_usage = set(r['ami_id'] for r in usage_results)
    used_in_refs = set(r['ami_id'] for r in ref_results)
    all_ami_ids = set(ami_map.keys())
    
    # Unused AMIs
    unused = all_ami_ids - used_in_usage - used_in_refs
    
    print(f"\nTotal AMIs: {len(all_ami_ids)}")
    print(f"  - Shared with other accounts: {len(used_in_usage)}")
    print(f"  - Used in your account: {len(used_in_refs)}")
    print(f"  - Completely unused: {len(unused)}")
    
    if unused:
        print("\n✓ SAFE TO DELETE (not used anywhere):")
        for ami_id in sorted(unused):
            ami = ami_map[ami_id]
            print(f"  - {ami_id} ({ami.get('Name', 'N/A')}) - Created: {ami.get('CreationDate', 'N/A')}")
    
    if used_in_usage and not used_in_refs:
        print("\n⚠ SHARED BUT NOT USED IN YOUR ACCOUNT:")
        for ami_id in sorted(used_in_usage - used_in_refs):
            ami = ami_map[ami_id]
            print(f"  - {ami_id} ({ami.get('Name', 'N/A')})")
            print(f"    Action: Check if other accounts still need access before unsharing")
    
    if used_in_refs:
        print("\n⚠ IN USE IN YOUR ACCOUNT (DO NOT DELETE):")
        for ami_id in sorted(used_in_refs):
            ami = ami_map[ami_id]
            print(f"  - {ami_id} ({ami.get('Name', 'N/A')})")

def export_csv(usage_results, ref_results, region):
    """Export combined results to CSV"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'ami_check_report_{region}_{timestamp}.csv'
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['AMI ID', 'AMI Name', 'Check Type', 'Account/Resource', 
                        'Resource Type', 'Count/ID', 'ARN'])
        
        for r in usage_results:
            writer.writerow([
                r['ami_id'], r['ami_name'], r['check_type'],
                r['account_id'], r['resource_type'], r['count'], '-'
            ])
        
        for r in ref_results:
            writer.writerow([
                r['ami_id'], r['ami_name'], r['check_type'],
                r['resource_id'], r['resource_type'], '-', r['resource_arn']
            ])
    
    print(f"\n✓ Report exported to: {filename}")
    return filename

def main():
    region = sys.argv[1] if len(sys.argv) > 1 else 'cn-northwest-1'
    
    print("="*70)
    print("COMPREHENSIVE AMI USAGE CHECKER")
    print("="*70)
    print(f"Region: {region}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    ec2 = boto3.client('ec2', region_name=region)
    
    # Get all AMIs
    print("Fetching AMI list...")
    response = ec2.describe_images(Owners=['self'])
    amis = response['Images']
    print(f"Found {len(amis)} AMI(s)\n")
    
    if not amis:
        print("No AMIs found")
        return
    
    # Run both checks
    usage_results = check_usage_reports(ec2, amis, region)
    ref_results = check_references(ec2, amis, region)
    
    # Generate recommendations
    generate_recommendations(usage_results, ref_results, amis)
    
    # Export CSV
    export_csv(usage_results, ref_results, region)
    
    print("\n" + "="*70)
    print("CHECK COMPLETE")
    print("="*70)

if __name__ == '__main__':
    main()
