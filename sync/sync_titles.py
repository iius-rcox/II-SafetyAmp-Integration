from utils.logger import get_logger
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI
from sync.sync_base import SyncOperation

logger = get_logger("sync_titles")

class TitleSyncer(SyncOperation):
    def __init__(self):
        super().__init__(name="sync_titles", sync_type="titles", entity_type="title")
        logger.info("Initializing TitleSyncer and fetching existing titles from SafetyAmp...")
        self.title_map = self._build_title_map()

    def _build_title_map(self):
        titles = self.api_client.get_titles_cached(max_age_hours=1)
        title_map = {
            t["name"].strip(): t["id"]
            for t in titles.values()
            if "name" in t and "id" in t
        }
        logger.info(f"Title map built with {len(title_map)} entries.")
        return title_map

    def ensure_title(self, title_name):
        title_name = title_name.strip()
        if title_name in self.title_map:
            return self.title_map[title_name]

        new_title = {"name": title_name}
        created = self.api_client.create_title(new_title)
        if isinstance(created, dict) and "id" in created:
            title_id = created["id"]
            self.title_map[title_name] = title_id
            logger.info(f"Created new title '{title_name}' with id {title_id}")
            return title_id

        logger.warning(f"Failed to create title '{title_name}'")
        return None

    def perform_sync(self):
        logger.info("Starting title sync from Viewpoint...")
        titles = self.viewpoint.get_titles()
        logger.info(f"Retrieved {len(titles)} titles from Viewpoint.")

        created = 0
        skipped = 0
        errors = 0

        for title in titles:
            title_name = title.get("udEmpTitle")
            if not title_name:
                skipped += 1
                continue
            try:
                existing = self.title_map.get(title_name.strip())
                if existing:
                    continue
                if self.ensure_title(title_name):
                    created += 1
            except Exception as e:
                errors += 1
                self.logger.error(f"Error ensuring title '{title_name}': {e}")

        return {"processed": len(titles), "created": created, "updated": 0, "skipped": skipped, "errors": errors}
