#!/usr/bin/env python3
"""
SafetyAmp Data Explorer

This script shows the fields available and first 20 raw records from each SafetyAmp API endpoint
for data structure understanding and planning.
"""

import sys
import os
import json
import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.safetyamp_api import SafetyAmpAPI

class SafetyAmpDataExplorer:
    def __init__(self):
        self.api_client = SafetyAmpAPI()
        self.endpoints = [
            ("/api/users", "emp_id"),
            ("/api/sites", "id"),
            ("/api/site_clusters", "id"),
            ("/api/user_titles", "id"),
            ("/api/roles", "id"),
            ("/api/assets", "id"),
            ("/api/asset_categories", "id"),
            ("/api/asset_types", "id")
        ]
    
    def explore_endpoint(self, endpoint, key_field="id", max_records=20):
        """Get fields and first N records from an endpoint"""
        print(f"Exploring {endpoint}...")
        
        try:
            if endpoint == "/api/site_clusters":
                # For site_clusters, we need to get all to understand structure, but limit processing
                data = self.api_client.get_site_clusters()
                items = list(data.values())
                total_records = len(items)
                sample_records = items[:max_records]
            else:
                # For other endpoints, use pagination to get only what we need
                params = {'limit': max_records}
                items = self.api_client.get(endpoint, params=params)
                
                if not items:
                    print(f"No data returned from {endpoint}")
                    return {}
                
                # The API returns a list directly
                total_records = len(items)  # We don't know the total, just what we got
                sample_records = items[:max_records]
            
            if not items:
                print(f"No data returned from {endpoint}")
                return {}
            
            # Get all unique fields from the sample records
            all_fields = set()
            for item in sample_records:
                all_fields.update(item.keys())
            fields = sorted(list(all_fields))
            
            result = {
                'fields': fields,
                'field_count': len(fields),
                'total_records': total_records,
                'sample_records': sample_records
            }
            
            print(f"Found {len(fields)} fields in {len(sample_records)} sample records")
            print(f"Records retrieved: {total_records:,}")
            return result
            
        except Exception as e:
            print(f"Error exploring {endpoint}: {e}")
            return {}
    
    def explore_all(self, max_records=20):
        """Explore all endpoints"""
        print("SafetyAmp Data Explorer")
        print("=" * 60)
        print("Exploring fields and sample data from all endpoints...")
        print("=" * 60)
        
        all_results = {}
        
        for endpoint, key_field in self.endpoints:
            result = self.explore_endpoint(endpoint, key_field, max_records)
            if result:
                all_results[endpoint] = result
            print()  # Add spacing between endpoints
        
        return all_results
    
    def print_summary(self, results):
        """Print field summary"""
        print("\n" + "=" * 60)
        print("SAFETYAMP API FIELD SUMMARY")
        print("=" * 60)
        
        for endpoint, data in results.items():
            print(f"\n[ENDPOINT] {endpoint}")
            print(f"   Records Retrieved: {data['total_records']:,}")
            print(f"   Fields ({data['field_count']}): {', '.join(data['fields'])}")
        
        print("\n" + "=" * 60)
    
    def save_detailed_report(self, results, filename="safetyamp_data_exploration.json"):
        """Save detailed exploration report as JSON"""
        # Prepare the JSON structure
        report_data = {
            "metadata": {
                "generated_at": str(datetime.datetime.now()),
                "description": "SafetyAmp API data exploration report with fields and sample records",
                "total_endpoints": len(results),
                "total_fields": sum(data['field_count'] for data in results.values()),
                "total_records_retrieved": sum(data['total_records'] for data in results.values())
            },
            "endpoints": {}
        }
        
        for endpoint, data in results.items():
            report_data["endpoints"][endpoint] = {
                "records_retrieved": data['total_records'],
                "field_count": data['field_count'],
                "fields": data['fields'],
                "sample_records": data['sample_records']
            }
        
        # Save as JSON with pretty formatting
        with open(filename, "w") as f:
            json.dump(report_data, f, indent=2, default=str)
        
        print(f"\nDetailed exploration report saved to: {filename}")
    
    def save_field_summary(self, results, filename="safetyamp_fields.json"):
        """Save field-only summary as JSON"""
        # Prepare the JSON structure
        field_summary = {
            "metadata": {
                "generated_at": str(datetime.datetime.now()),
                "description": "SafetyAmp API field summary",
                "total_endpoints": len(results),
                "total_fields": sum(data['field_count'] for data in results.values())
            },
            "endpoints": {}
        }
        
        for endpoint, data in results.items():
            field_summary["endpoints"][endpoint] = {
                "field_count": data['field_count'],
                "fields": data['fields']
            }
        
        # Save as JSON with pretty formatting
        with open(filename, "w") as f:
            json.dump(field_summary, f, indent=2)
        
        print(f"Field summary saved to: {filename}")

def main():
    explorer = SafetyAmpDataExplorer()
    
    # Explore all endpoints
    results = explorer.explore_all(max_records=20)
    
    if not results:
        print("No data explored. Check API credentials and connectivity.")
        return
    
    # Print summary
    explorer.print_summary(results)
    
    # Save reports
    explorer.save_detailed_report(results)
    explorer.save_field_summary(results)
    
    # Print statistics
    total_records = sum(data['total_records'] for data in results.values())
    total_fields = sum(data['field_count'] for data in results.values())
    
    print(f"\n📊 EXPLORATION STATISTICS:")
    print(f"   Endpoints: {len(results)}")
    print(f"   Records Retrieved: {total_records:,}")
    print(f"   Total Fields: {total_fields}")
    print(f"   Sample Records Shown: {len(results) * 20}")
    print(f"   Reports Generated: 2")

if __name__ == "__main__":
    main() 