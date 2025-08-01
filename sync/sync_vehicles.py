#!/usr/bin/env python3
"""
Samsara to SafetyAmp Vehicle Sync

This module syncs vehicles from Samsara to SafetyAmp as assets.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.samsara_api import SamsaraAPI
from services.safetyamp_api import SafetyAmpAPI
from utils.logger import get_logger
from datetime import datetime
import requests
import re

logger = get_logger("vehicle_sync")

class VehicleSync:
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
            safetyamp_users = self.safetyamp_api.get_users_by_id_cached(max_age_hours=1)
            
            # Store full user objects in cache
            self.safetyamp_users_cache = safetyamp_users or {}
            
            logger.info(f"Loaded {len(self.safetyamp_users_cache)} SafetyAmp users into cache")
            
        except Exception as e:
            logger.error(f"Error loading SafetyAmp users cache: {e}")
            self.safetyamp_users_cache = {}
    
    def _get_asset_type_for_site(self, site_id):
        """Get the appropriate asset type ID for a given site"""
        try:
            asset_types = self.safetyamp_api.get_asset_types_cached(max_age_hours=1)
            
            # Look for a vehicle asset type that matches the site
            for asset_type_id, asset_type in asset_types.items():
                if (asset_type.get("name", "").lower() in ["vehicles", "vehicle"] and 
                    asset_type.get("site_id") == site_id):
                    return int(asset_type_id)
            
            # If no site-specific vehicle type found, look for any vehicle type
            for asset_type_id, asset_type in asset_types.items():
                if asset_type.get("name", "").lower() in ["vehicles", "vehicle"]:
                    return int(asset_type_id)
            
            # Fallback to the default vehicle type
            return 3183
            
        except Exception as e:
            logger.error(f"Error getting asset type for site {site_id}: {e}")
            return 3183
    
    def _get_site_for_asset_type(self, asset_type_id):
        """Get the site ID that an asset type is valid for"""
        try:
            asset_types = self.safetyamp_api.get_asset_types_cached(max_age_hours=1)
            if str(asset_type_id) in asset_types:
                return asset_types[str(asset_type_id)].get("site_id")
            return None
        except Exception as e:
            logger.error(f"Error getting site for asset type {asset_type_id}: {e}")
            return None
    
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
                "asset_type_id": 3183,  # Use default vehicle asset type
                "status": self.status_mapping.get(regulation_mode, 1),
                "location_id": None,  # Optional field
                
                # Default values
                "created_by": self.defaults["created_by"],
                "updated_by": self.defaults["updated_by"],
                "deleted_at": self.defaults["deleted_at"]
            }
            
            # Only add current_user_id if we have a valid user
            if safetyamp_user_id:
                asset_data["current_user_id"] = safetyamp_user_id
            
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
    
    def get_existing_assets(self):
        """Get existing SafetyAmp assets for comparison"""
        try:
            assets = self.safetyamp_api.get_assets_cached(max_age_hours=1)
            return {asset.get("serial"): asset for asset in assets.values() if asset.get("serial")}
        except Exception as e:
            logger.error(f"Error fetching existing assets: {e}")
            return {}
    
    def sync_vehicles(self):
        """Sync vehicles from Samsara to SafetyAmp"""
        logger.info("Starting vehicle sync from Samsara to SafetyAmp")
        
        try:
            # Get vehicles from Samsara
            logger.info("Fetching vehicles from Samsara...")
            vehicles = self.samsara_api.get_all_vehicles()
            
            if not vehicles:
                logger.warning("No vehicles found in Samsara")
                return {"synced": 0, "errors": 0, "skipped": 0}
            
            logger.info(f"Found {len(vehicles)} vehicles in Samsara")
            
            # Get existing assets for comparison
            existing_assets = self.get_existing_assets()
            logger.info(f"Found {len(existing_assets)} existing assets in SafetyAmp")
            
            # Process each vehicle
            synced_count = 0
            error_count = 0
            skipped_count = 0
            
            for vehicle in vehicles:
                try:
                    # Transform vehicle to asset format
                    asset_data = self.transform_vehicle_to_asset(vehicle)
                    if not asset_data:
                        error_count += 1
                        continue
                    
                    vehicle_serial = asset_data.get("serial")
                    if not vehicle_serial:
                        logger.warning(f"Vehicle {vehicle.get('id')} has no serial number, skipping")
                        skipped_count += 1
                        continue
                    
                    # Check if asset already exists
                    existing_asset = existing_assets.get(vehicle_serial)
                    
                    if existing_asset:
                        # Asset exists - check if update needed
                        if self._needs_update(existing_asset, asset_data):
                            # Update existing asset
                            result = self.safetyamp_api.update_asset(existing_asset["id"], asset_data)
                            if result:
                                synced_count += 1
                                logger.info(f"Updated asset {vehicle_serial}")
                            else:
                                error_count += 1
                                logger.error(f"Failed to update asset {vehicle_serial}")
                        else:
                            logger.debug(f"Asset {vehicle_serial} is up to date")
                            skipped_count += 1
                    else:
                        # Asset doesn't exist - create new one
                        # Create new asset
                        result = self.safetyamp_api.create_asset(asset_data)
                        if result:
                            synced_count += 1
                            logger.info(f"Created asset {vehicle_serial}")
                        else:
                            error_count += 1
                            logger.error(f"Failed to create asset {vehicle_serial}")
                
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing vehicle {vehicle.get('id', 'unknown')}: {e}")
            
            # Log summary
            logger.info(f"Vehicle sync completed:")
            logger.info(f"  Synced: {synced_count}")
            logger.info(f"  Errors: {error_count}")
            logger.info(f"  Skipped: {skipped_count}")
            
            return {
                "synced": synced_count,
                "errors": error_count,
                "skipped": skipped_count
            }
            
        except Exception as e:
            logger.error(f"Error during vehicle sync: {e}")
            return {"synced": 0, "errors": 1, "skipped": 0}
    
    def _needs_update(self, existing_asset, new_data):
        """Check if asset needs to be updated"""
        # Compare essential fields that might change
        fields_to_check = [
            "current_user_id", "asset_type_id"
        ]
        
        for field in fields_to_check:
            existing_value = str(existing_asset.get(field, "")).strip()
            new_value = str(new_data.get(field, "")).strip()
            
            if existing_value != new_value:
                logger.debug(f"Field {field} changed: '{existing_value}' -> '{new_value}'")
                return True
        
        return False
    
    def get_sync_summary(self):
        """Get summary of sync status"""
        try:
            # Get counts from both systems
            samsara_vehicles = self.samsara_api.get_all_vehicles()
            safetyamp_assets = self.safetyamp_api.get_assets_cached(max_age_hours=1)
            
            # Count vehicles with serial numbers (can be synced)
            syncable_vehicles = [v for v in samsara_vehicles if v.get("serial")]
            
            # Count assets that came from Samsara (by checking serial pattern)
            samsara_assets = [a for a in safetyamp_assets.values() if a.get("serial") and a.get("serial", "").startswith("G")]
            
            return {
                "samsara_vehicles": len(samsara_vehicles),
                "syncable_vehicles": len(syncable_vehicles),
                "safetyamp_assets": len(safetyamp_assets),
                "samsara_assets": len(samsara_assets),
                "pending_sync": len(syncable_vehicles) - len(samsara_assets)
            }
            
        except Exception as e:
            logger.error(f"Error getting sync summary: {e}")
            return {}

def main():
    """Main function for testing vehicle sync"""
    sync = VehicleSync()
    
    # Get sync summary
    summary = sync.get_sync_summary()
    if summary:
        print("Vehicle Sync Summary:")
        print(f"  Samsara Vehicles: {summary.get('samsara_vehicles', 0)}")
        print(f"  Syncable Vehicles: {summary.get('syncable_vehicles', 0)}")
        print(f"  SafetyAmp Assets: {summary.get('safetyamp_assets', 0)}")
        print(f"  Samsara Assets: {summary.get('samsara_assets', 0)}")
        print(f"  Pending Sync: {summary.get('pending_sync', 0)}")
    
    # Run sync
    print("\nRunning vehicle sync...")
    result = sync.sync_vehicles()
    print(f"Sync result: {result}")

if __name__ == "__main__":
    main() 