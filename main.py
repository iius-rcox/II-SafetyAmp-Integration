from sync.sync_departments import DepartmentSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_titles import TitleSyncer

if __name__ == "__main__":

    #dept_syncer = DepartmentSyncer()
    #dept_syncer.sync()

    #job_syncer = JobSyncer()
    #job_syncer.sync()

    #title_syncer = TitleSyncer()
    #title_syncer.sync()

    ee_syncer = EmployeeSyncer()
    ee_syncer.sync()