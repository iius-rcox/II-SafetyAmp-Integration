from utils.logger import get_logger
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI

CLUSTER_ROOT_ID = 0
CLUSTER_ROOT_NAME = "I&I"

logger = get_logger("sync_departments")

class DepartmentSyncer:
    def __init__(self):
        self.api_client = SafetyAmpAPI()
        self.viewpoint = ViewpointAPI()
        logger.info("Fetching department data from Viewpoint...")
        self.source_data = self.viewpoint.get_departments()
        logger.info(f"Retrieved {len(self.source_data)} department records from Viewpoint.")
        logger.info("Fetching existing clusters from SafetyAmp...")
        self.existing_clusters = self.api_client.get_site_clusters()
        logger.info(f"Retrieved {len(self.existing_clusters)} existing clusters from SafetyAmp.")

    def ensure_cluster(self, name, parent_id, external_code):
        for cluster in self.existing_clusters.values():
            if cluster.get('name') == name and cluster.get('external_code') in (None, external_code):
                if (cluster.get('parent_cluster_id') or None) != parent_id:
                    patch_data = {"parent_cluster_id": parent_id}
                    self.api_client.put(f"/api/site_clusters/{cluster['id']}", patch_data)
                    logger.info(f"Moved cluster: {name} to new parent_id: {parent_id}")
                # else:
                    # logger.info(f"Cluster already exists and is correctly assigned: {name}")
                return cluster['id']

        cluster_data = {
            "name": name,
            "parent_cluster_id": parent_id,
            "external_code": external_code,
            "osha_establishment": 0
        }
        created_cluster = self.api_client.create_cluster(cluster_data)
        if isinstance(created_cluster, dict):
            logger.info(f"Created cluster: {name} (parent_id: {parent_id})")
            self.existing_clusters[str(created_cluster["id"])] = created_cluster
        else:
            logger.warning(f"Failed to create cluster: {name}")
        return created_cluster.get('id') if isinstance(created_cluster, dict) else None

    def sync(self):
        logger.info("Starting department cluster sync...")

        # Ensure I&I root cluster exists
        # logger.info(f"Ensuring root cluster '{CLUSTER_ROOT_NAME}' exists...")
        root_cluster_id = self.ensure_cluster(CLUSTER_ROOT_NAME, None, CLUSTER_ROOT_NAME)

        # Build map of region clusters
        region_cluster_ids = {}
        for row in self.source_data:
            region = row.get('udRegion')
            if region and region not in region_cluster_ids:
                # logger.info(f"Ensuring region cluster '{region}' under root cluster ID {root_cluster_id}...")
                region_cluster_ids[region] = self.ensure_cluster(region, root_cluster_id, region)

        # Ensure department clusters under each region cluster
        for row in self.source_data:
            region = row.get('udRegion')
            pr_dept = row.get('PRDept')
            desc = row.get('Description')

            if region and pr_dept and desc:
                dept_name = f"{pr_dept} - {desc}"
                external_code = str(pr_dept)
                cluster_id = region_cluster_ids.get(region)
                # logger.info(f"Ensuring department cluster '{dept_name}' under region '{region}'...")
                self.ensure_cluster(dept_name, cluster_id, external_code)

        logger.info("Department cluster sync complete.")