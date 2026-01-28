#!/usr/bin/env python3
"""
Batch Sync Script for SafetyAmp Integration

This script runs sync operations directly for use with Kubernetes CronJobs.
It performs the same sync operations as the main application but runs once and exits.
"""

import sys
import os
import time
from sync.sync_departments import DepartmentSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_titles import TitleSyncer
from sync.sync_vehicles import VehicleSync
from utils.logger import get_logger

logger = get_logger("sync_batch")


def run_sync_operations():
    """Run all sync operations once"""
    logger.info("Starting batch sync operations")

    start_time = time.time()
    results = {}

    try:
        # Employee sync
        logger.info("Starting employee sync...")
        ee_syncer = EmployeeSyncer()
        result = ee_syncer.sync()
        results["employees"] = result
        logger.info(f"Employee sync completed: {result}")

        # Department sync
        logger.info("Starting department sync...")
        dept_syncer = DepartmentSyncer()
        result = dept_syncer.sync()
        results["departments"] = result
        logger.info(f"Department sync completed: {result}")

        # Job sync
        logger.info("Starting job sync...")
        job_syncer = JobSyncer()
        result = job_syncer.sync()
        results["jobs"] = result
        logger.info(f"Job sync completed: {result}")

        # Title sync
        logger.info("Starting title sync...")
        title_syncer = TitleSyncer()
        result = title_syncer.sync()
        results["titles"] = result
        logger.info(f"Title sync completed: {result}")

        # Vehicle sync
        logger.info("Starting vehicle sync...")
        vehicle_syncer = VehicleSync()
        result = vehicle_syncer.sync_vehicles()
        results["vehicles"] = result
        logger.info(f"Vehicle sync completed: {result}")

        sync_duration = time.time() - start_time
        logger.info(
            f"All sync operations completed successfully in {sync_duration:.2f} seconds"
        )
        logger.info(f"Sync results: {results}")

        return True, results

    except Exception as e:
        error_msg = f"Batch sync error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, {"error": error_msg}


if __name__ == "__main__":
    logger.info("Starting SafetyAmp batch sync")

    # Run sync operations
    success, results = run_sync_operations()

    if success:
        logger.info("Batch sync completed successfully")
        sys.exit(0)
    else:
        logger.error("Batch sync failed")
        sys.exit(1)
