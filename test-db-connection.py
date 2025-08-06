#!/usr/bin/env python3
"""
Test database connection to Viewpoint SQL Server
"""

import sys
import os
sys.path.append('/app')

from services.viewpoint_api import ViewpointAPI
from config.settings import VIEWPOINT_CONN_STRING, SQL_AUTH_MODE
from sqlalchemy import text
import time

def test_connection():
    print("🔍 Testing Viewpoint Database Connection")
    print("=" * 50)
    
    print(f"SQL_AUTH_MODE: {SQL_AUTH_MODE}")
    print(f"Connection String: {VIEWPOINT_CONN_STRING}")
    print()
    
    try:
        print("📡 Initializing Viewpoint API...")
        v = ViewpointAPI()
        print("✅ Viewpoint API initialized successfully")
        
        print("🔌 Testing database connection...")
        start_time = time.time()
        
        with v._get_connection() as conn:
            print("✅ Database connection established!")
            print(f"⏱️ Connection time: {time.time() - start_time:.2f} seconds")
            
            # Test a simple query first
            print("🔍 Testing simple query...")
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"✅ Basic query successful: {row}")
            
            # Test the actual bPREH table query
            print("🔍 Testing bPREH table query...")
            query_start = time.time()
            result = conn.execute(text("SELECT TOP 1 Employee FROM bPREH"))
            row = result.fetchone()
            print(f"✅ bPREH query successful: {row}")
            print(f"⏱️ Query time: {time.time() - query_start:.2f} seconds")
            
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {str(e)}")
        print(f"⏱️ Time taken: {time.time() - start_time:.2f} seconds")
        return False
    
    return True

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1) 