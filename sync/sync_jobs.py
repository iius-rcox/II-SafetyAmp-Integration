from utils.logger import get_logger
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI

logger = get_logger("sync_jobs")

class JobSyncer:
    def __init__(self):
        self.api_client = SafetyAmpAPI()
        self.viewpoint = ViewpointAPI()
        logger.info("Fetching existing sites from SafetyAmp...")
        self.existing_sites = self.api_client.get_sites().values()
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
            # else:
                # logger.info(f"No update needed for existing site: {name}")
            return

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
        else:
            logger.warning(f"Failed to create site: {name}")

    def sync(self):
        logger.info("Starting job site sync...")
        for job in self.jobs:
            dept = job.get("Department")
            cluster_id = self.dept_cluster_map.get(dept)
            if not cluster_id:
                logger.warning(f"Skipping job {job['Job']} — unknown department: {dept}")
                continue

            self.ensure_site(job, cluster_id)
        logger.info("Job site sync complete.")