import os
import pyodbc
from datetime import datetime
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from sqlalchemy.engine import Engine
from urllib.parse import quote_plus
from config import settings
from utils.logger import get_logger
from .vista_data_manager import vista_data_manager

logger = get_logger("viewpoint")

class ViewpointAPI:
    def __init__(self):
        # Build SQLAlchemy connection URL from ODBC connection string
        self.conn_str = settings.VIEWPOINT_CONN_STRING
        
        # Convert ODBC connection string to SQLAlchemy URL
        # Format: mssql+pyodbc:///?odbc_connect=<encoded_connection_string>
        encoded_conn_str = quote_plus(self.conn_str)
        sqlalchemy_url = f"mssql+pyodbc:///?odbc_connect={encoded_conn_str}"
        
        # Create engine with connection pooling
        self.engine = create_engine(
            sqlalchemy_url,
            poolclass=QueuePool,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,  # Verify connections before use
            pool_reset_on_return='commit'  # Reset connections on return
        )
        
        logger.info(f"Initialized Viewpoint API with connection pool (size={settings.DB_POOL_SIZE}, max_overflow={settings.DB_MAX_OVERFLOW})")

    @contextmanager
    def _get_connection(self):
        """Context manager that provides database connections from the pool"""
        connection = None
        try:
            connection = self.engine.connect()
            yield connection
        except Exception as e:
            logger.error(f"Database connection error: {str(e)}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()

    def _fetch_query(self, connection, query):
        """Execute query and return results as list of dictionaries"""
        try:
            result = connection.execute(text(query))
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"Query execution error: {str(e)}")
            logger.error(f"Query: {query}")
            raise

    def get_title_list(self, connection):
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
        return self._fetch_query(connection, query)


    def fetch_recent_jobs(self, connection):
        # Optimized query - using EXISTS instead of CTE for better performance
        query = text("""
        SELECT 
            JC.PREndDate,
            JC.Job,
            JC.Employee,
            JC.Class
        FROM 
            bPRJC AS JC
        INNER JOIN bJCJM AS JM ON JM.JCCo = JC.PRCo AND JM.Job = JC.Job
        WHERE
            PREndDate > :start_date AND
            JM.JobStatus = 1 AND
            JC.PREndDate = (
                SELECT MAX(JC2.PREndDate)
                FROM bPRJC AS JC2
                INNER JOIN bJCJM AS JM2 ON JM2.JCCo = JC2.PRCo AND JM2.Job = JC2.Job
                WHERE JC2.Employee = JC.Employee 
                AND JC2.PREndDate > :start_date 
                AND JM2.JobStatus = 1
            )
        ORDER BY
            JC.Employee
        """)
        recent_jobs = connection.execute(query, {"start_date": "2024-01-01"}).fetchall()
        return {row.Employee: row.Job.strip() if row.Job else None for row in recent_jobs}

    def fetch_employees(self, connection):
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
        return self._fetch_query(connection, query)

    def fetch_job_list(self, connection):
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
        return self._fetch_query(connection, query)

    def get_department_list(self, connection):
        query = """
        SELECT
            DP.PRDept,
            DP.Description,
            DP.udRegion
        FROM
            bPRDP AS DP
        WHERE PRCo = 1
        """
        return self._fetch_query(connection, query)

    def build_employee_json(self, connection, recent_job_map=None):
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
        employees = self._fetch_query(connection, query)
        if recent_job_map:
            for emp in employees:
                emp_id = emp["Employee"]
                if emp_id in recent_job_map:
                    emp["Job"] = recent_job_map[emp_id]
        return employees

    def get_employees(self):
        with self._get_connection() as conn:
            recent_job_map = self.fetch_recent_jobs(conn)
            employees = self.build_employee_json(conn, recent_job_map)
            # Store in memory instead of file
            vista_data_manager.set_employee_data(employees)
            return employees

    def get_jobs(self):
        with self._get_connection() as conn:
            jobs = self.fetch_job_list(conn)
            # Store in memory instead of file
            vista_data_manager.set_job_data(jobs)
            return jobs

    def get_departments(self):
        with self._get_connection() as conn:
            departments = self.get_department_list(conn)
            return departments

    def get_titles(self):
        with self._get_connection() as conn:
            titles = self.get_title_list(conn)
            return titles