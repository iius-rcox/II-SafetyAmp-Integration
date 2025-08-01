#!/usr/bin/env python3
"""
Test Single Vehicle Sync

This script tests syncing one vehicle from Samsara to SafetyAmp to verify the integration.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.samsara_api import SamsaraAPI
from services.safetyamp_api import SafetyAmpAPI
from utils.logger import get_logger
import json
import requests

logger = get_logger("test_single_vehicle")

class SingleVehicleTest:
    def __init__(self):
        self.samsara_api = SamsaraAPI()
        self.safetyamp_api = SafetyAmpAPI()
        
        # Status mapping (SafetyAmp uses numeric status: 1=active, 0=inactive)
        self.status_mapping = {
            "regulated": 1,
            "unregulated": 0
        }
        
        # Default values for missing fields
        self.defaults = {
            "created_by": "system",
            "updated_by": "system",
            "deleted_at": None
        }
        
        # Cache for SafetyAmp users lookup (emp_id -> user_id)
        self.safetyamp_users_cache = {}
        self._load_safetyamp_users_cache()
    
    def _load_safetyamp_users_cache(self):
        """Load SafetyAmp users into cache for efficient lookup"""
        try:
            logger.info("Loading SafetyAmp users cache...")
            safetyamp_users = self.safetyamp_api.get_all_paginated("/api/users", "id")
            
            # Store full user objects in cache
            self.safetyamp_users_cache = safetyamp_users
            
            logger.info(f"Loaded {len(self.safetyamp_users_cache)} SafetyAmp users into cache")
            
        except Exception as e:
            logger.error(f"Error loading SafetyAmp users cache: {e}")
            self.safetyamp_users_cache = {}
    
    def get_driver_safetyamp_id(self, driver_id):
        """Get SafetyAmp user ID and home_site_id by looking up employee ID in SafetyAmp users cache"""
        try:
            if not driver_id:
                return None, None
                
            # First, get the driver details from Samsara to get the employee ID from notes
            endpoint = f"{self.samsara_api.base_url}/fleet/drivers/{driver_id}"
            
            response = self.samsara_api._exponential_retry(
                self.samsara_api._rate_limited_request, 
                requests.get, 
                endpoint
            )
            driver_data = self.samsara_api._handle_response(response, "GET", endpoint)
            
            if not driver_data:
                logger.warning(f"Could not fetch driver data for ID: {driver_id}")
                return None, None
            
            # Extract employee ID from notes
            notes = driver_data.get("data", {}).get("notes", "")
            if not notes:
                logger.warning(f"No notes found for driver ID: {driver_id}")
                return None, None
            
            # Look for employee ID in notes (4+ digits)
            import re
            match = re.search(r'(\d{4,})', notes)
            if not match:
                logger.warning(f"No employee ID found in driver notes for ID: {driver_id}")
                return None, None
            
            employee_id = match.group(1).strip()
            logger.info(f"Found employee ID '{employee_id}' in driver notes")
            
            # Look up employee ID in cached SafetyAmp users
            for user in self.safetyamp_users_cache.values():
                if user.get("emp_id") == employee_id:
                    safetyamp_user_id = user.get("id")
                    home_site_id = user.get("home_site_id")
                    logger.info(f"Found SafetyAmp user ID '{safetyamp_user_id}' with home_site_id '{home_site_id}' for employee ID '{employee_id}'")
                    return safetyamp_user_id, home_site_id
            
            logger.warning(f"No SafetyAmp user found for employee ID: {employee_id}")
            return None, None
            
        except Exception as e:
            logger.error(f"Error fetching driver data for ID {driver_id}: {e}")
            return None, None

    def transform_vehicle_to_asset(self, vehicle):
        """Transform Samsara vehicle data to SafetyAmp asset format"""
        try:
            # Extract basic vehicle info
            vehicle_id = vehicle.get("id")
            name = vehicle.get("name", "")
            make = vehicle.get("make", "")
            model = vehicle.get("model", "")
            year = vehicle.get("year", "")
            license_plate = vehicle.get("licensePlate", "")
            vin = vehicle.get("vin", "")
            serial = vehicle.get("serial", "")
            notes = vehicle.get("notes", "")
            regulation_mode = vehicle.get("vehicleRegulationMode", "")
            
            # Extract driver info
            driver = vehicle.get("staticAssignedDriver", {})
            driver_name = driver.get("name", "") if driver else ""
            driver_id = driver.get("id", "") if driver else ""
            
            # Get SafetyAmp user ID by looking up driver in SafetyAmp users
            safetyamp_user_id = None
            home_site_id = None
            if driver_id:
                safetyamp_user_id, home_site_id = self.get_driver_safetyamp_id(driver_id)
            
            # Extract department/site info from tags
            tags = vehicle.get("tags", [])
            department_tag = next((tag for tag in tags if "Department" in tag.get("name", "")), {})
            department_name = department_tag.get("name", "") if department_tag else ""
            department_id = department_tag.get("id", "") if department_tag else ""
            
            # Transform timestamps
            created_at = vehicle.get("createdAtTime", "")
            updated_at = vehicle.get("updatedAtTime", "")
            
            # Build SafetyAmp asset data
            asset_data = {
                # Direct mappings
                "name": name,
                "model": model,
                "serial": serial,
                "description": notes,
                "created_at": created_at,
                "updated_at": updated_at,
                
                # Derived mappings
                "code": license_plate or f"Unit_{vehicle_id[-4:]}" if vehicle_id else "",
                "asset_type_id": 3183,  # Use the specific vehicle asset type ID from SafetyAmp
                "status": self.status_mapping.get(regulation_mode, 1),
                "current_user_id": safetyamp_user_id,  # Use SafetyAmp user ID from lookup
                "site_id": home_site_id,  # Use home_site_id from user record
                "location_id": None,  # Optional field
                
                # Default values
                "created_by": self.defaults["created_by"],
                "updated_by": self.defaults["updated_by"],
                "deleted_at": self.defaults["deleted_at"]
            }
            
            # Add VIN as additional identifier if available
            if vin:
                asset_data["vin"] = vin
            
            # Add year if available
            if year:
                asset_data["year"] = year
            
            logger.debug(f"Transformed vehicle {vehicle_id} to asset format")
            return asset_data
            
        except Exception as e:
            logger.error(f"Error transforming vehicle {vehicle.get('id', 'unknown')}: {e}")
            return None
    
    def test_single_vehicle(self, dry_run=True):
        """Test syncing a single vehicle from Samsara to SafetyAmp"""
        logger.info("Testing single vehicle sync from Samsara to SafetyAmp")
        
        try:
            # Get just one vehicle from Samsara (much faster)
            logger.info("Fetching single vehicle from Samsara...")
            endpoint = f"{self.samsara_api.base_url}/fleet/vehicles"
            params = {"limit": 1}  # Only get 1 vehicle
            
            response = self.samsara_api._exponential_retry(
                self.samsara_api._rate_limited_request, 
                requests.get, 
                endpoint, 
                params=params
            )
            data = self.samsara_api._handle_response(response, "GET", endpoint)
            
            vehicles = data.get("data", [])
            if not vehicles:
                logger.warning("No vehicles found in Samsara")
                return {"synced": 0, "errors": 0, "skipped": 0}
            
            # Take the first vehicle (should have serial number)
            test_vehicle = vehicles[0]
            
            if not test_vehicle.get("serial"):
                logger.warning("First vehicle has no serial number, skipping")
                return {"synced": 0, "errors": 0, "skipped": 0}
            
            logger.info(f"Testing with vehicle: {test_vehicle.get('name')} (ID: {test_vehicle.get('id')})")
            
            # Show the original Samsara vehicle data
            print("\n" + "=" * 60)
            print("ORIGINAL SAMSARA VEHICLE DATA")
            print("=" * 60)
            print(json.dumps(test_vehicle, indent=2, default=str))
            
            # Transform vehicle to asset format
            asset_data = self.transform_vehicle_to_asset(test_vehicle)
            if not asset_data:
                logger.error("Failed to transform vehicle data")
                return {"synced": 0, "errors": 1, "skipped": 0}
            
            # Show the transformed SafetyAmp asset data
            print("\n" + "=" * 60)
            print("TRANSFORMED SAFETYAMP ASSET DATA")
            print("=" * 60)
            print(json.dumps(asset_data, indent=2, default=str))
            
            # Check if asset already exists
            existing_assets = self.safetyamp_api.get_all_paginated("/api/assets", "id")
            existing_asset = None
            for asset in existing_assets.values():
                if asset.get("serial") == asset_data.get("serial"):
                    existing_asset = asset
                    break
            
            if existing_asset:
                print(f"\n" + "=" * 60)
                print("EXISTING ASSET FOUND")
                print("=" * 60)
                print(json.dumps(existing_asset, indent=2, default=str))
                
                # Check if update is needed (only essential fields)
                fields_to_check = ["current_user_id", "asset_type_id", "site_id"]
                needs_update = False
                
                for field in fields_to_check:
                    existing_value = str(existing_asset.get(field, "")).strip()
                    new_value = str(asset_data.get(field, "")).strip()
                    if existing_value != new_value:
                        print(f"Field '{field}' would change: '{existing_value}' -> '{new_value}'")
                        needs_update = True
                
                if needs_update:
                    if not dry_run:
                        # Update existing asset
                        result = self.safetyamp_api.update_asset(existing_asset["id"], asset_data)
                        if result:
                            logger.info(f"Updated asset {asset_data.get('serial')}")
                            return {"synced": 1, "errors": 0, "skipped": 0}
                        else:
                            logger.error(f"Failed to update asset {asset_data.get('serial')}")
                            return {"synced": 0, "errors": 1, "skipped": 0}
                    else:
                        logger.info(f"[DRY RUN] Would update asset {asset_data.get('serial')}")
                        return {"synced": 1, "errors": 0, "skipped": 0}
                else:
                    logger.info(f"Asset {asset_data.get('serial')} is up to date")
                    return {"synced": 0, "errors": 0, "skipped": 1}
            else:
                print(f"\n" + "=" * 60)
                print("NO EXISTING ASSET FOUND - WOULD CREATE NEW")
                print("=" * 60)
                
                if not dry_run:
                    # Create new asset
                    result = self.safetyamp_api.create_asset(asset_data)
                    if result:
                        logger.info(f"Created asset {asset_data.get('serial')}")
                        return {"synced": 1, "errors": 0, "skipped": 0}
                    else:
                        logger.error(f"Failed to create asset {asset_data.get('serial')}")
                        return {"synced": 0, "errors": 1, "skipped": 0}
                else:
                    logger.info(f"[DRY RUN] Would create asset {asset_data.get('serial')}")
                    return {"synced": 1, "errors": 0, "skipped": 0}
            
        except Exception as e:
            logger.error(f"Error during single vehicle test: {e}")
            return {"synced": 0, "errors": 1, "skipped": 0}

def main():
    """Main function for testing single vehicle sync"""
    test = SingleVehicleTest()
    
    print("Testing Single Vehicle Sync")
    print("=" * 60)
    
    # Run dry run test first
    print("\nRunning dry run test...")
    result = test.test_single_vehicle(dry_run=True)
    print(f"\nDry run result: {result}")
    
    # Ask user if they want to proceed with live test
    print("\n" + "=" * 60)
    response = input("Do you want to proceed with live sync? (y/N): ").strip().lower()
    
    if response == 'y':
        print("\nRunning live test...")
        result = test.test_single_vehicle(dry_run=False)
        print(f"\nLive test result: {result}")
    else:
        print("Live test skipped.")

if __name__ == "__main__":
    main() 