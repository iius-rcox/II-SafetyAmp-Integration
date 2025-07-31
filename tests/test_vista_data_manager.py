import unittest
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.vista_data_manager import VistaDataManager

class TestVistaDataManager(unittest.TestCase):
    def setUp(self):
        self.data_manager = VistaDataManager()
        
        # Sample test data
        self.sample_employees = [
            {
                "Employee": 1234,
                "FirstName": "John",
                "LastName": "Doe",
                "Email": "john.doe@example.com",
                "PRDept": "44",
                "udEmpTitle": "Engineer"
            },
            {
                "Employee": 5678,
                "FirstName": "Jane",
                "LastName": "Smith",
                "Email": "jane.smith@example.com",
                "PRDept": "95",
                "udEmpTitle": "Manager"
            }
        ]
        
        self.sample_jobs = [
            {
                "Job": "50025",
                "Description": "Test Project 1",
                "Department": "44"
            },
            {
                "Job": "92647",
                "Description": "Test Project 2", 
                "Department": "95"
            }
        ]

    def test_set_and_get_employee_data(self):
        """Test setting and retrieving employee data"""
        self.data_manager.set_employee_data(self.sample_employees)
        retrieved_data = self.data_manager._employee_data
        
        self.assertEqual(len(retrieved_data), 2)
        self.assertEqual(retrieved_data[0]["Employee"], 1234)
        self.assertEqual(retrieved_data[1]["FirstName"], "Jane")

    def test_set_and_get_job_data(self):
        """Test setting and retrieving job data"""
        self.data_manager.set_job_data(self.sample_jobs)
        retrieved_data = self.data_manager._job_data
        
        self.assertEqual(len(retrieved_data), 2)
        self.assertEqual(retrieved_data[0]["Job"], "50025")
        self.assertEqual(retrieved_data[1]["Description"], "Test Project 2")

    def test_get_employee_by_id(self):
        """Test getting employee by ID"""
        self.data_manager.set_employee_data(self.sample_employees)
        
        employee = self.data_manager.get_employee_by_id(1234)
        self.assertIsNotNone(employee)
        self.assertEqual(employee["FirstName"], "John")
        
        # Test non-existent employee
        employee = self.data_manager.get_employee_by_id(9999)
        self.assertIsNone(employee)

    def test_get_employees_by_department(self):
        """Test getting employees by department"""
        self.data_manager.set_employee_data(self.sample_employees)
        
        dept_44_employees = self.data_manager.get_employees_by_department("44")
        self.assertEqual(len(dept_44_employees), 1)
        self.assertEqual(dept_44_employees[0]["Employee"], 1234)

    def test_search_employees(self):
        """Test searching employees by name or email"""
        self.data_manager.set_employee_data(self.sample_employees)
        
        # Search by first name
        results = self.data_manager.search_employees("John")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["Employee"], 1234)
        
        # Search by email
        results = self.data_manager.search_employees("jane.smith")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["Employee"], 5678)

    def test_get_job_by_code(self):
        """Test getting job by code"""
        self.data_manager.set_job_data(self.sample_jobs)
        
        job = self.data_manager.get_job_by_code("50025")
        self.assertIsNotNone(job)
        self.assertEqual(job["Description"], "Test Project 1")
        
        # Test non-existent job
        job = self.data_manager.get_job_by_code("99999")
        self.assertIsNone(job)

if __name__ == '__main__':
    unittest.main() 