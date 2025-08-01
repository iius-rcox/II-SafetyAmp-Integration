from utils.logger import get_logger
from services.safetyamp_api import SafetyAmpAPI
from services.samsara_api import SamsaraAPI
from config import settings

logger = get_logger("sync_assets")

class AssetSyncer:
    def __init__(self):
        self.api_client = SafetyAmpAPI()
        self.samsara = SamsaraAPI()
        logger.info("Fetching assets from SafetyAmp...")
        self.existing_assets = self._build_asset_map()
        logger.info("Fetching vehicles from Samsara...")
        self.vehicles = self.samsara.get_all_vehicles()
        logger.info("Fetching users from SafetyAmp...")
        self.users = self._build_user_map()
        self.user_site_map = self._build_user_site_map()

    def _build_asset_map(self):
        assets = self.api_client.get_assets_cached(max_age_hours=1)
        return {asset.get("external_id"): asset for asset in assets.values() if asset.get("external_id")}

    def _build_user_map(self):
        users = self.api_client.get_users_cached(max_age_hours=1)
        return {str(user.get("emp_id")): user.get("id") for user in users.values() if user.get("emp_id") and user.get("id")}

    def _build_user_site_map(self):
        users = self.api_client.get_users_cached(max_age_hours=1)
        return {user.get("id"): user.get("home_site_id") for user in users.values() if user.get("id") and user.get("home_site_id")}

    def format_vehicle_to_asset(self, vehicle):
        driver = vehicle.get("staticAssignedDriver")
        driver_id = driver.get("id") if isinstance(driver, dict) else None
        current_user_id = self.users.get(str(driver_id)) if driver_id else None
        site_id = self.user_site_map.get(current_user_id)

        return {
            "name": vehicle.get("name"),
            "external_id": vehicle.get("vin"),
            "description": f"{vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')} ({vehicle.get('licensePlate')})",
            "status": 1,
            "asset_type_id": settings.VEHICLE_ASSET_TYPE_ID,
            "asset_category_id": 634,
            "site_id": site_id,
            "serial": vehicle.get("serial"),
            "model": vehicle.get("model"),
            "code": vehicle.get("vin"),
            "current_user_id": current_user_id
        }

    def sync(self):
        logger.info("Starting asset sync...")
        for vehicle in self.vehicles:
            vin = vehicle.get("vin")
            if not vin:
                logger.warning("Skipping vehicle without VIN")
                continue

            asset_payload = self.format_vehicle_to_asset(vehicle)
            existing_asset = self.existing_assets.get(vin)

            if existing_asset:
                needs_update = (
                    existing_asset.get("name") != asset_payload["name"] or
                    existing_asset.get("description") != asset_payload["description"] or
                    existing_asset.get("serial") != asset_payload["serial"] or
                    existing_asset.get("model") != asset_payload["model"] or
                    existing_asset.get("code") != asset_payload["code"] or
                    existing_asset.get("current_user_id") != asset_payload["current_user_id"]
                )
                if needs_update:
                    self.api_client.put(f"/api/assets/{existing_asset['id']}", asset_payload)
                    logger.info(f"Updated asset {asset_payload['name']} ({vin})")
            else:
                created = self.api_client.post("/api/assets", asset_payload)
                if isinstance(created, dict):
                    logger.info(f"Created new asset: {asset_payload['name']} ({vin})")
                else:
                    logger.warning(f"Failed to create asset: {asset_payload['name']} ({vin})")

        logger.info("Asset sync complete.")

# Usage:
# syncer = AssetSyncer()
# syncer.sync()
