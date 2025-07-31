import json
from collections import defaultdict, Counter
from typing import Dict, List, Set, Any
from services.safetyamp_api import SafetyAmpAPI
from utils.logger import get_logger

logger = get_logger("safetyamp_field_extractor")

class SafetyAmpFieldExtractor:
    def __init__(self):
        self.api_client = SafetyAmpAPI()
        self.field_analysis = defaultdict(lambda: {
            'fields': set(),
            'field_types': defaultdict(set),
            'sample_values': defaultdict(list),
            'null_count': Counter(),
            'total_records': 0
        })

    def extract_all_fields(self, endpoint: str, key_field: str = "id", max_samples: int = 5) -> Dict[str, Any]:
        """
        Extract all available fields from a SafetyAmp API endpoint
        
        Args:
            endpoint: API endpoint (e.g., "/api/users")
            key_field: Field to use as key for deduplication
            max_samples: Maximum number of sample values to collect per field
            
        Returns:
            Dictionary containing field analysis
        """
        logger.info(f"Extracting fields from {endpoint}")
        
        # Get all data from the endpoint
        if endpoint == "/api/site_clusters":
            # Special handling for site_clusters due to nested structure
            data = self.api_client.get_site_clusters()
            items = list(data.values())
        else:
            data = self.api_client.get_all_paginated(endpoint, key_field)
            items = list(data.values())
        
        if not items:
            logger.warning(f"No data returned from {endpoint}")
            return {}
        
        logger.info(f"Analyzing {len(items)} records from {endpoint}")
        
        # Analyze each item
        for item in items:
            self._analyze_item(item, endpoint, max_samples)
        
        # Convert sets to lists for JSON serialization
        result = self._format_analysis(endpoint)
        
        return result

    def _analyze_item(self, item: Dict[str, Any], endpoint: str, max_samples: int):
        """Analyze a single item and extract field information"""
        analysis = self.field_analysis[endpoint]
        analysis['total_records'] += 1
        
        for field_name, field_value in item.items():
            # Track field presence
            analysis['fields'].add(field_name)
            
            # Track field type
            field_type = type(field_value).__name__
            analysis['field_types'][field_name].add(field_type)
            
            # Track null values
            if field_value is None:
                analysis['null_count'][field_name] += 1
            
            # Collect sample values (limit to max_samples)
            if len(analysis['sample_values'][field_name]) < max_samples:
                # Truncate long values for readability
                if isinstance(field_value, str) and len(field_value) > 100:
                    sample_value = field_value[:100] + "..."
                elif isinstance(field_value, (list, dict)) and len(str(field_value)) > 100:
                    sample_value = str(field_value)[:100] + "..."
                else:
                    sample_value = field_value
                
                analysis['sample_values'][field_name].append(sample_value)

    def _format_analysis(self, endpoint: str) -> Dict[str, Any]:
        """Format the analysis results for output"""
        analysis = self.field_analysis[endpoint]
        
        return {
            'endpoint': endpoint,
            'total_records': analysis['total_records'],
            'fields': sorted(list(analysis['fields'])),
            'field_details': {
                field: {
                    'types': sorted(list(analysis['field_types'][field])),
                    'null_count': analysis['null_count'][field],
                    'null_percentage': round((analysis['null_count'][field] / analysis['total_records']) * 100, 2),
                    'sample_values': analysis['sample_values'][field]
                }
                for field in analysis['fields']
            }
        }

    def extract_all_safetyamp_fields(self) -> Dict[str, Any]:
        """
        Extract fields from all known SafetyAmp endpoints
        
        Returns:
            Dictionary containing field analysis for all endpoints
        """
        endpoints = [
            ("/api/users", "emp_id"),
            ("/api/sites", "id"),
            ("/api/site_clusters", "id"),
            ("/api/user_titles", "id"),
            ("/api/roles", "id"),
            ("/api/assets", "id")
        ]
        
        all_results = {}
        
        for endpoint, key_field in endpoints:
            try:
                result = self.extract_all_fields(endpoint, key_field)
                if result:
                    all_results[endpoint] = result
            except Exception as e:
                logger.error(f"Error extracting fields from {endpoint}: {e}")
                all_results[endpoint] = {
                    'error': str(e),
                    'endpoint': endpoint
                }
        
        return all_results

    def generate_field_report(self, output_file: str = None) -> str:
        """
        Generate a comprehensive field report
        
        Args:
            output_file: Optional file path to save the report
            
        Returns:
            Formatted report string
        """
        results = self.extract_all_safetyamp_fields()
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("SAFETYAMP API FIELD ANALYSIS REPORT")
        report_lines.append("=" * 80)
        report_lines.append("")
        
                 for endpoint, analysis in results.items():
             if 'error' in analysis:
                 report_lines.append(f"[ERROR] {endpoint}: {analysis['error']}")
                 report_lines.append("")
                 continue
             
             report_lines.append(f"[ENDPOINT] {endpoint}")
             report_lines.append(f"   Total Records: {analysis['total_records']}")
             report_lines.append(f"   Total Fields: {len(analysis['fields'])}")
             report_lines.append("")
             
             # Sort fields by null percentage (most nulls first)
             field_details = analysis['field_details']
             sorted_fields = sorted(
                 field_details.items(),
                 key=lambda x: x[1]['null_percentage'],
                 reverse=True
             )
             
             for field_name, details in sorted_fields:
                 null_status = "[OK]" if details['null_percentage'] == 0 else f"[NULL] {details['null_percentage']}% null"
                 types_str = ", ".join(details['types'])
                 report_lines.append(f"   • {field_name}")
                 report_lines.append(f"     Types: {types_str}")
                 report_lines.append(f"     Null: {null_status}")
                 
                 if details['sample_values']:
                     samples_str = ", ".join(str(v) for v in details['sample_values'][:3])
                     report_lines.append(f"     Samples: {samples_str}")
                 report_lines.append("")
             
             report_lines.append("-" * 80)
             report_lines.append("")
        
        report = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report)
            logger.info(f"Field report saved to {output_file}")
        
        return report

    def get_field_summary(self) -> Dict[str, List[str]]:
        """
        Get a quick summary of all available fields by endpoint
        
        Returns:
            Dictionary mapping endpoints to lists of field names
        """
        results = self.extract_all_safetyamp_fields()
        
        summary = {}
        for endpoint, analysis in results.items():
            if 'error' not in analysis:
                summary[endpoint] = analysis['fields']
        
        return summary

# Convenience function for quick field extraction
def extract_safetyamp_fields(endpoint: str = None, output_file: str = None) -> Dict[str, Any]:
    """
    Quick function to extract SafetyAmp fields
    
    Args:
        endpoint: Specific endpoint to analyze (if None, analyzes all)
        output_file: Optional file to save the report
        
    Returns:
        Field analysis results
    """
    extractor = SafetyAmpFieldExtractor()
    
    if endpoint:
        return extractor.extract_all_fields(endpoint)
    else:
        return extractor.extract_all_safetyamp_fields()

def print_field_summary():
    """Print a quick summary of all available fields"""
    extractor = SafetyAmpFieldExtractor()
    summary = extractor.get_field_summary()
    
    print("\n" + "=" * 60)
    print("SAFETYAMP API FIELD SUMMARY")
    print("=" * 60)
    
    for endpoint, fields in summary.items():
        print(f"\n[ENDPOINT] {endpoint}")
        print(f"   Fields ({len(fields)}): {', '.join(sorted(fields))}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    # Example usage
    print_field_summary()
    
    # Generate detailed report
    extractor = SafetyAmpFieldExtractor()
    report = extractor.generate_field_report("safetyamp_field_report.txt")
    print("\nDetailed report generated. Check safetyamp_field_report.txt") 