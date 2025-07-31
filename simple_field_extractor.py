#!/usr/bin/env python3
"""
Simple SafetyAmp Field Extractor

This script extracts field names from SafetyAmp API endpoints
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.safetyamp_api import SafetyAmpAPI

def extract_fields_from_endpoint(endpoint, key_field="id"):
    """Extract field names from a single endpoint"""
    api_client = SafetyAmpAPI()
    
    print(f"Extracting fields from {endpoint}...")
    
    try:
        if endpoint == "/api/site_clusters":
            data = api_client.get_site_clusters()
            items = list(data.values())
        else:
            data = api_client.get_all_paginated(endpoint, key_field)
            items = list(data.values())
        
        if not items:
            print(f"No data returned from {endpoint}")
            return []
        
        # Get all unique field names
        all_fields = set()
        for item in items:
            all_fields.update(item.keys())
        
        fields = sorted(list(all_fields))
        print(f"Found {len(fields)} fields in {len(items)} records")
        
        return fields
        
    except Exception as e:
        print(f"Error extracting from {endpoint}: {e}")
        return []

def main():
    print("SafetyAmp API Field Extractor")
    print("=" * 50)
    
    endpoints = [
        ("/api/users", "emp_id"),
        ("/api/sites", "id"),
        ("/api/site_clusters", "id"),
        ("/api/user_titles", "id"),
        ("/api/roles", "id"),
        ("/api/assets", "id"),
        ("/api/asset_categories", "id"),
        ("/api/asset_types", "id")
    ]
    
    all_results = {}
    
    for endpoint, key_field in endpoints:
        fields = extract_fields_from_endpoint(endpoint, key_field)
        if fields:
            all_results[endpoint] = fields
    
    # Print summary
    print("\n" + "=" * 60)
    print("SAFETYAMP API FIELD SUMMARY")
    print("=" * 60)
    
    for endpoint, fields in all_results.items():
        print(f"\n[ENDPOINT] {endpoint}")
        print(f"   Fields ({len(fields)}): {', '.join(fields)}")
    
    print("\n" + "=" * 60)
    
    # Save to file
    with open("safetyamp_fields.txt", "w") as f:
        f.write("SAFETYAMP API FIELD SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        
        for endpoint, fields in all_results.items():
            f.write(f"[ENDPOINT] {endpoint}\n")
            f.write(f"   Fields ({len(fields)}): {', '.join(fields)}\n\n")
    
    print(f"\nField summary saved to: safetyamp_fields.txt")

if __name__ == "__main__":
    main() 