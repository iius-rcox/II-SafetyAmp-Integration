from utils.logger import get_logger
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI
from sync.sync_base import SyncOperation

logger = get_logger("sync_jobs")

class JobSyncer(SyncOperation):
    def __init__(self):
        super().__init__(name="sync_jobs", sync_type="jobs", entity_type="site")
        logger.info("Fetching existing sites from SafetyAmp...")
        sites_data = self.api_client.get_sites_cached(max_age_hours=1)
        self.existing_sites = sites_data.values()
        logger.info(f"Retrieved {len(self.existing_sites)} existing sites.")
        logger.info("Fetching jobs from Viewpoint...")
        self.jobs = self.viewpoint.get_jobs()
        logger.info(f"Retrieved {len(self.jobs)} jobs from Viewpoint.")
        logger.info("Fetching site clusters from SafetyAmp...")
        self.dept_cluster_map = {
            cluster["external_code"]: cluster["id"]
            for cluster in self.api_client.get_site_clusters().values()
            if cluster.get("depth") == 2 and cluster.get("external_code")
        }
        logger.info(f"Built department-to-cluster map with {len(self.dept_cluster_map)} entries.")

    def find_existing_site(self, name):
        for site in self.existing_sites:
            if site["name"] == name:
                return site
        return None

    def ensure_site(self, job, cluster_id):
        name = f"{job['Job']} - {job['Description']}".strip()
        existing_site = self.find_existing_site(name)

        zip_code = str(job.get("ShipZip") or "00000").strip()

        if existing_site:
            patch_data = {}
            if existing_site.get("cluster_id") != cluster_id:
                patch_data["cluster_id"] = cluster_id
            if existing_site.get("zip_code") != zip_code:
                patch_data["zip_code"] = zip_code
                patch_data["ext_id"] = job["Job"]
            if patch_data:
                patch_data["name"] = name
                self.api_client.put(f"/api/sites/{existing_site['id']}", patch_data)
                logger.info(f"Updated site: {name} with changes: {patch_data}")
            return True, False  # processed, created

        site_data = {
            "name": name,
            "ext_id": job["Job"],
            "street": job.get("ShipAddress") or "Unknown",
            "city": job.get("ShipCity") or "Unknown",
            "state": job.get("ShipState") or "LA",
            "country": "US",
            "timezone": "America/Chicago",
            "zip_code": zip_code,
            "cluster_id": cluster_id
        }

        created = self.api_client.create_site(site_data)
        if isinstance(created, dict):
            logger.info(f"Created site: {name} under cluster {cluster_id}")
            return True, True
        else:
            logger.warning(f"Failed to create site: {name}")
            return False, False

    def perform_sync(self):
        logger.info("Starting job site sync...")
        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for job in self.jobs:
            dept = job.get("Department")
            cluster_id = self.dept_cluster_map.get(dept)
            if not cluster_id:
                logger.warning(f"Skipping job {job['Job']} — unknown department: {dept}")
                skipped += 1
                continue

            try:
                processed, was_created = self.ensure_site(job, cluster_id)
                if processed:
                    if was_created:
                        created += 1
                    else:
                        updated += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                self.logger.error(f"Error ensuring site for job {job.get('Job')}: {e}")

        logger.info("Job site sync complete.")
        return {"processed": len(self.jobs), "created": created, "updated": updated, "skipped": skipped, "errors": errors}