#!/usr/bin/env python3
"""
SafetyAmp Field Extractor Script

This script extracts all available fields from SafetyAmp API endpoints
and generates a comprehensive report of field names, types, and sample values.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.safetyamp_field_extractor import SafetyAmpFieldExtractor, print_field_summary

def main():
    print("SafetyAmp API Field Extractor")
    print("=" * 50)
    
    try:
        # Create extractor instance
        extractor = SafetyAmpFieldExtractor()
        
        # Print quick summary
        print("\nQuick Field Summary:")
        print_field_summary()
        
        # Generate detailed report
        print("\nGenerating detailed field report...")
        report = extractor.generate_field_report("safetyamp_field_report.txt")
        
        print("\nField extraction completed!")
        print("Detailed report saved to: safetyamp_field_report.txt")
        print("\n" + "=" * 50)
        
        # Print a preview of the report
        print("\nREPORT PREVIEW:")
        print("=" * 50)
        lines = report.split('\n')[:50]  # Show first 50 lines
        for line in lines:
            print(line)
        
        if len(report.split('\n')) > 50:
            print("... (see safetyamp_field_report.txt for full report)")
        
    except Exception as e:
        print(f"Error during field extraction: {e}")
        print("\nMake sure you have:")
        print("1. Valid SafetyAmp API credentials in your .env file")
        print("2. Network connectivity to SafetyAmp API")
        print("3. Proper permissions to access the API endpoints")
        sys.exit(1)

if __name__ == "__main__":
    main() 