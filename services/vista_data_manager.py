import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from utils.logger import get_logger

logger = get_logger("vista_data_manager")

class VistaDataManager:
    def __init__(self):
        self._employee_data: List[Dict] = []
        self._job_data: List[Dict] = []
        self._last_employee_refresh: Optional[datetime] = None
        self._last_job_refresh: Optional[datetime] = None
        self._refresh_interval = timedelta(minutes=30)
        self._lock = asyncio.Lock()
    
    async def get_employee_data(self) -> List[Dict]:
        """Get employee data, refreshing if needed"""
        async with self._lock:
            if self._should_refresh_employees():
                await self._refresh_employee_data()
            return self._employee_data.copy()
    
    async def get_job_data(self) -> List[Dict]:
        """Get job data, refreshing if needed"""
        async with self._lock:
            if self._should_refresh_jobs():
                await self._refresh_job_data()
            return self._job_data.copy()
    
    def set_employee_data(self, employee_data: List[Dict]):
        """Set employee data directly (for synchronous operations)"""
        self._employee_data = employee_data
        self._last_employee_refresh = datetime.now()
        logger.info(f"Loaded {len(employee_data)} employees into memory")
    
    def set_job_data(self, job_data: List[Dict]):
        """Set job data directly (for synchronous operations)"""
        self._job_data = job_data
        self._last_job_refresh = datetime.now()
        logger.info(f"Loaded {len(job_data)} jobs into memory")
    
    def get_employee_by_id(self, employee_id: int) -> Optional[Dict]:
        """Get specific employee by ID"""
        return next((emp for emp in self._employee_data if emp['Employee'] == employee_id), None)
    
    def get_employees_by_department(self, department: str) -> List[Dict]:
        """Get all employees in a specific department"""
        return [emp for emp in self._employee_data if emp.get('PRDept') == department]
    
    def search_employees(self, search_term: str) -> List[Dict]:
        """Search employees by name or email"""
        search_term_lower = search_term.lower()
        return [
            emp for emp in self._employee_data 
            if (search_term_lower in emp.get('FirstName', '').lower() or
                search_term_lower in emp.get('LastName', '').lower() or
                search_term_lower in emp.get('Email', '').lower())
        ]
    
    def get_job_by_code(self, job_code: str) -> Optional[Dict]:
        """Get specific job by job code"""
        return next((job for job in self._job_data if job.get('Job') == job_code), None)
    
    def _should_refresh_employees(self) -> bool:
        return (
            not self._employee_data or 
            not self._last_employee_refresh or 
            datetime.now() - self._last_employee_refresh > self._refresh_interval
        )
    
    def _should_refresh_jobs(self) -> bool:
        return (
            not self._job_data or 
            not self._last_job_refresh or 
            datetime.now() - self._last_job_refresh > self._refresh_interval
        )
    
    async def _refresh_employee_data(self):
        """Refresh employee data from Viewpoint API"""
        # This would be implemented to call the Viewpoint API
        # For now, we'll keep the existing data
        logger.info("Employee data refresh requested")
    
    async def _refresh_job_data(self):
        """Refresh job data from Viewpoint API"""
        # This would be implemented to call the Viewpoint API
        # For now, we'll keep the existing data
        logger.info("Job data refresh requested")

# Global instance for easy access
vista_data_manager = VistaDataManager() 