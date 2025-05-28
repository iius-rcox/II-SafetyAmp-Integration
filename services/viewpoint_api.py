import os
import pyodbc
import json
from pathlib import Path
from datetime import datetime
from config import settings
from utils.logger import get_logger

logger = get_logger("viewpoint")

class ViewpointAPI:
    def __init__(self):
        self.conn_str = (
            f"DRIVER={settings.SQL_DRIVER};"
            f"SERVER={settings.SQL_SERVER};"
            f"DATABASE={settings.SQL_DATABASE};"
            "Trusted_Connection=yes;"
            "Encrypt=no;"
        )
        base_dir = Path(__file__).resolve().parent
        self.employee_json_path = base_dir / "vista_employee_data.json"
        self.job_list_json_path = base_dir / "vista_job_list.json"

    def _get_connection(self):
        return pyodbc.connect(self.conn_str)

    def _fetch_query(self, cursor, query):
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_title_list(self, cursor):
        query = """
        SELECT DISTINCT
            udEmpTitle
        FROM
            bPREH
        WHERE
            PRCo = 1 AND
            HireDate IS NOT NULL AND
            TermDate IS NULL
        """
        return self._fetch_query(cursor, query)


    def fetch_recent_jobs(self, cursor):
        query = """
        WITH RankedRecords AS (
            SELECT 
                JC.PREndDate,
                JC.Job,
                JC.Employee,
                JC.Class,
                ROW_NUMBER() OVER (PARTITION BY JC.Employee ORDER BY JC.PREndDate DESC) AS RowNum
            FROM 
                bPRJC AS JC
            LEFT JOIN bJCJM AS JM ON JM.JCCo = JC.PRCo AND JM.Job = JC.Job
            WHERE
                PREndDate > '2024-01-01' AND
                JM.JobStatus = 1
        )
        SELECT 
            PREndDate,
            Job,
            Employee,
            Class
        FROM 
            RankedRecords
        WHERE 
            RowNum = 1
        ORDER BY
            Employee;
        """
        recent_jobs = self._fetch_query(cursor, query)
        return {row['Employee']: row['Job'].strip() if row['Job'] else None for row in recent_jobs}

    def fetch_employees(self, cursor):
        query = """
        SELECT
            FirstName,
            LastName,
            SortName,
            Employee,
            Sex,
            PRDept,
            Email,
            HireDate,
            TermDate
        FROM
            bPREH
        WHERE
            PRCo = 1 AND
            HireDate IS NOT NULL AND
            TermDate IS NULL
        """
        return self._fetch_query(cursor, query)

    def fetch_job_list(self, cursor):
        query = """
        SELECT
            JM.Contract,
            JM.Job,
            JM.Description,
            CM.Department,
            JM.ShipAddress,
            JM.ShipCity,
            JM.ShipState,
            JM.ShipZip
        FROM
            bJCJM AS JM
        LEFT JOIN bJCCM AS CM ON CM.Contract = JM.Contract AND CM.JCCo = JM.JCCo
        WHERE JM.JCCo = 1 AND JM.JobStatus = 1
        """
        return self._fetch_query(cursor, query)

    def get_department_list(self, cursor):
        query = """
        SELECT
            DP.PRDept,
            DP.Description,
            DP.udRegion
        FROM
            bPRDP AS DP
        WHERE PRCo = 1
        """
        return self._fetch_query(cursor, query)

    def build_employee_json(self, cursor, recent_job_map=None):
        query = """
        SELECT
            Employee,
            FirstName,
            MidName,
            LastName,
            Sex,
            PRDept,
            Email,
            udEmpTitle,
            BirthDate,
            HireDate,
            Phone,
            Address,
            City,
            State,
            Zip
        FROM
            bPREH
        WHERE
            PRCo = 1 AND
            HireDate IS NOT NULL AND
            TermDate IS NULL
        """
        employees = self._fetch_query(cursor, query)
        if recent_job_map:
            for emp in employees:
                emp_id = emp["Employee"]
                if emp_id in recent_job_map:
                    emp["Job"] = recent_job_map[emp_id]
        return employees

    def save_to_json(self, data, path):
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def get_employees(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            recent_job_map = self.fetch_recent_jobs(cursor)
            employees = self.build_employee_json(cursor, recent_job_map)
            self.save_to_json(employees, self.employee_json_path)
            return employees

    def get_jobs(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            jobs = self.fetch_job_list(cursor)
            self.save_to_json(jobs, self.job_list_json_path)
            return jobs

    def get_departments(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            departments = self.get_department_list(cursor)
            return departments

    def get_titles(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            titles = self.get_title_list(cursor)
            return titles