#!/usr/bin/env python3
"""
SafetyAmp Batch Sync Script
Optimized for CronJob batch processing with proper error handling and reporting.
"""

import os
import sys
import time
import signal
from datetime import datetime
from utils.logger import get_logger
from sync.sync_departments import DepartmentSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_titles import TitleSyncer
from prometheus_client import Counter, Histogram, push_to_gateway, CollectorRegistry
import structlog

# Initialize structured logging for batch mode
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = get_logger("sync_batch")

# Batch-specific configuration
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
MAX_EXECUTION_TIME = int(os.getenv('MAX_EXECUTION_TIME', '3600'))  # 1 hour
PROMETHEUS_GATEWAY = os.getenv('PROMETHEUS_GATEWAY', 'prometheus-pushgateway:9091')

# Metrics for batch operations
registry = CollectorRegistry()
batch_sync_duration = Histogram('safetyamp_batch_sync_duration_seconds', 
                               'Batch sync duration', ['sync_type'], registry=registry)
batch_records_processed = Counter('safetyamp_batch_records_processed_total', 
                                'Total records processed in batch', ['sync_type'], registry=registry)
batch_sync_status = Counter('safetyamp_batch_sync_status_total', 
                           'Batch sync status', ['sync_type', 'status'], registry=registry)

# Global state for graceful shutdown
shutdown_requested = False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, requesting graceful shutdown...")
    shutdown_requested = True

def run_employee_sync():
    """Run employee synchronization with batch optimization"""
    logger.info("Starting employee batch sync", batch_size=BATCH_SIZE)
    
    with batch_sync_duration.labels(sync_type='employees').time():
        try:
            start_time = time.time()
            syncer = EmployeeSyncer()
            
            # Run sync with batch processing
            result = syncer.sync()
            
            # Record metrics
            if result and 'processed' in result:
                batch_records_processed.labels(sync_type='employees').inc(result['processed'])
                logger.info("Employee sync completed successfully", 
                          records_processed=result['processed'],
                          duration_seconds=time.time() - start_time)
            
            batch_sync_status.labels(sync_type='employees', status='success').inc()
            return True
            
        except Exception as e:
            batch_sync_status.labels(sync_type='employees', status='error').inc()
            logger.error("Employee sync failed", error=str(e), exc_info=True)
            return False

def run_department_sync():
    """Run department synchronization"""
    logger.info("Starting department batch sync")
    
    with batch_sync_duration.labels(sync_type='departments').time():
        try:
            start_time = time.time()
            syncer = DepartmentSyncer()
            result = syncer.sync()
            
            if result and 'processed' in result:
                batch_records_processed.labels(sync_type='departments').inc(result['processed'])
                logger.info("Department sync completed successfully", 
                          records_processed=result['processed'],
                          duration_seconds=time.time() - start_time)
            
            batch_sync_status.labels(sync_type='departments', status='success').inc()
            return True
            
        except Exception as e:
            batch_sync_status.labels(sync_type='departments', status='error').inc()
            logger.error("Department sync failed", error=str(e), exc_info=True)
            return False

def run_job_sync():
    """Run job synchronization"""
    logger.info("Starting job batch sync")
    
    with batch_sync_duration.labels(sync_type='jobs').time():
        try:
            start_time = time.time()
            syncer = JobSyncer()
            result = syncer.sync()
            
            if result and 'processed' in result:
                batch_records_processed.labels(sync_type='jobs').inc(result['processed'])
                logger.info("Job sync completed successfully", 
                          records_processed=result['processed'],
                          duration_seconds=time.time() - start_time)
            
            batch_sync_status.labels(sync_type='jobs', status='success').inc()
            return True
            
        except Exception as e:
            batch_sync_status.labels(sync_type='jobs', status='error').inc()
            logger.error("Job sync failed", error=str(e), exc_info=True)
            return False

def run_title_sync():
    """Run title synchronization"""
    logger.info("Starting title batch sync")
    
    with batch_sync_duration.labels(sync_type='titles').time():
        try:
            start_time = time.time()
            syncer = TitleSyncer()
            result = syncer.sync()
            
            if result and 'processed' in result:
                batch_records_processed.labels(sync_type='titles').inc(result['processed'])
                logger.info("Title sync completed successfully", 
                          records_processed=result['processed'],
                          duration_seconds=time.time() - start_time)
            
            batch_sync_status.labels(sync_type='titles', status='success').inc()
            return True
            
        except Exception as e:
            batch_sync_status.labels(sync_type='titles', status='error').inc()
            logger.error("Title sync failed", error=str(e), exc_info=True)
            return False

def push_metrics_to_gateway():
    """Push metrics to Prometheus Push Gateway"""
    try:
        job_name = f"safetyamp-batch-sync-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        push_to_gateway(PROMETHEUS_GATEWAY, job=job_name, registry=registry)
        logger.info("Successfully pushed metrics to Prometheus Push Gateway")
    except Exception as e:
        logger.warning(f"Failed to push metrics to gateway: {e}")

def main():
    """Main batch sync execution"""
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    start_time = time.time()
    logger.info("Starting SafetyAmp batch sync", 
                timestamp=datetime.now().isoformat(),
                max_execution_time=MAX_EXECUTION_TIME,
                batch_size=BATCH_SIZE)
    
    # Track overall success
    sync_results = {}
    overall_success = True
    
    # Define sync operations in order of dependency
    sync_operations = [
        ('departments', run_department_sync),
        ('jobs', run_job_sync),
        ('titles', run_title_sync),
        ('employees', run_employee_sync),  # Run employees last as it depends on others
    ]
    
    for sync_name, sync_func in sync_operations:
        if shutdown_requested:
            logger.warning(f"Shutdown requested, skipping {sync_name} sync")
            break
            
        # Check execution time limit
        elapsed_time = time.time() - start_time
        if elapsed_time > MAX_EXECUTION_TIME:
            logger.warning(f"Maximum execution time exceeded, skipping {sync_name} sync",
                         elapsed_time=elapsed_time,
                         max_time=MAX_EXECUTION_TIME)
            break
        
        logger.info(f"Running {sync_name} sync...")
        success = sync_func()
        sync_results[sync_name] = success
        
        if not success:
            overall_success = False
            logger.error(f"{sync_name} sync failed")
            
            # Continue with other syncs unless it's a critical failure
            if sync_name in ['departments']:  # Critical dependencies
                logger.error("Critical sync failed, stopping batch execution")
                break
        else:
            logger.info(f"{sync_name} sync completed successfully")
    
    # Calculate final metrics
    total_duration = time.time() - start_time
    
    # Push metrics to Prometheus Push Gateway
    push_metrics_to_gateway()
    
    # Log final summary
    logger.info("Batch sync execution completed",
                total_duration=total_duration,
                overall_success=overall_success,
                sync_results=sync_results,
                shutdown_requested=shutdown_requested)
    
    # Exit with appropriate code
    if overall_success:
        logger.info("Batch sync completed successfully")
        sys.exit(0)
    else:
        logger.error("Batch sync completed with errors")
        sys.exit(1)

if __name__ == "__main__":
    main()