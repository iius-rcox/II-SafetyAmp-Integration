from utils.logger import get_logger
from services.safetyamp_api import SafetyAmpAPI
from services.viewpoint_api import ViewpointAPI
from sync.base import SyncOperation

CLUSTER_ROOT_ID = 0
CLUSTER_ROOT_NAME = "I&I"

logger = get_logger("sync_departments")

class DepartmentSyncer(SyncOperation):
    def __init__(self):
        super().__init__(sync_type="departments", entity_type="cluster", use_viewpoint=True)
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
                    self.safe_call(
                        self.api_client.put,
                        f"/api/site_clusters/{cluster['id']}",
                        patch_data,
                        operation="move_cluster",
                        entity_id=str(cluster['id']),
                        error_details={"name": name, "new_parent_id": parent_id}
                    )
                    logger.info(f"Moved cluster: {name} to new parent_id: {parent_id}")
                    self.log_update(str(cluster['id']), patch_data, original_data=cluster)
                    self.increment("updated")
                return cluster['id']

        cluster_data = {
            "name": name,
            "parent_cluster_id": parent_id,
            "external_code": external_code,
            "osha_establishment": 0
        }
        created_cluster = self.safe_call(
            self.api_client.create_cluster,
            cluster_data,
            operation="create_cluster",
            entity_id=name,
        )
        if isinstance(created_cluster, dict):
            logger.info(f"Created cluster: {name} (parent_id: {parent_id})")
            self.existing_clusters[str(created_cluster["id"])] = created_cluster
            self.log_creation(str(created_cluster["id"]), cluster_data)
            self.increment("created")
            return created_cluster.get('id')
        else:
            logger.warning(f"Failed to create cluster: {name}")
            return None

    def sync(self):
        logger.info("Starting department cluster sync...")
        self.start_sync()

        # Ensure I&I root cluster exists
        root_cluster_id = self.ensure_cluster(CLUSTER_ROOT_NAME, None, CLUSTER_ROOT_NAME)

        # Build map of region clusters
        region_cluster_ids = {}
        for row in self.source_data:
            region = row.get('udRegion')
            if region and region not in region_cluster_ids:
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
                self.ensure_cluster(dept_name, cluster_id, external_code)

        self.counts["processed"] = len(self.source_data)
        session_summary = self.finish_sync()
        logger.info("Department cluster sync complete.")
        return {
            "processed": len(self.source_data),
            "created": self.counts["created"],
            "updated": self.counts["updated"],
            "skipped": self.counts["skipped"],
            "errors": self.counts["errors"],
            "session_summary": session_summary,
        }