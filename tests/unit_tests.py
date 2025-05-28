from services.samsara_api import SamsaraAPI
from sync.sync_departments import DepartmentSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_titles import TitleSyncer
from sync.sync_assets import AssetSyncer
if __name__ == "__main__":

    asset_syncer = AssetSyncer()
    asset_syncer.sync()


    ee_syncer = EmployeeSyncer()
    ee_syncer.sync()

    title_syncer = TitleSyncer()
    title_syncer.sync()

    dept_syncer = DepartmentSyncer()
    dept_syncer.sync()



    job_syncer = JobSyncer()
    job_syncer.sync()

