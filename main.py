from flask import Flask, jsonify
from sync.sync_departments import DepartmentSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_titles import TitleSyncer
import signal
import sys
import threading
import time
from utils.logger import get_logger
from config.settings import SYNC_INTERVAL_MINUTES

app = Flask(__name__)
logger = get_logger("main")

# Global health status
health_status = {
    'healthy': True,
    'ready': False,
    'last_sync': None,
    'errors': []
}

@app.route('/health')
def health():
    """Liveness probe endpoint"""
    if health_status['healthy']:
        return jsonify({'status': 'healthy', 'timestamp': time.time()}), 200
    else:
        return jsonify({'status': 'unhealthy', 'errors': health_status['errors']}), 503

@app.route('/ready')
def ready():
    """Readiness probe endpoint"""
    if health_status['ready']:
        return jsonify({'status': 'ready', 'timestamp': time.time()}), 200
    else:
        return jsonify({'status': 'not ready'}), 503

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    # Basic metrics - expand as needed
    return jsonify({
        'sync_operations_total': 0,
        'sync_errors_total': 0,
        'last_sync_duration_seconds': 0
    })

def run_sync_worker():
    """Background sync worker"""
    logger.info("Starting background sync worker")
    while health_status['healthy']:
        try:
            # Run sync operations
            logger.info("Starting sync operations")
            
            # Employee sync (currently active)
            ee_syncer = EmployeeSyncer()
            ee_syncer.sync()
            
            # Uncomment other sync operations as needed
            # dept_syncer = DepartmentSyncer()
            # dept_syncer.sync()
            
            # job_syncer = JobSyncer()
            # job_syncer.sync()
            
            # title_syncer = TitleSyncer()
            # title_syncer.sync()
            
            health_status['last_sync'] = time.time()
            health_status['ready'] = True
            health_status['errors'] = []  # Clear previous errors
            logger.info("Sync operations completed successfully")
            
        except Exception as e:
            error_msg = f"Sync worker error: {str(e)}"
            logger.error(error_msg)
            health_status['errors'].append(error_msg)
            # Don't mark as unhealthy for individual sync failures
            # The worker will continue and retry on the next interval
            
        # Sleep for configurable sync interval (converted from minutes to seconds)
        sync_interval_seconds = SYNC_INTERVAL_MINUTES * 60
        logger.info(f"Sleeping for {SYNC_INTERVAL_MINUTES} minutes ({sync_interval_seconds} seconds)")
        time.sleep(sync_interval_seconds)

def signal_handler(signum, frame):
    """Graceful shutdown handler"""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    health_status['healthy'] = False
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start sync worker in background
    sync_thread = threading.Thread(target=run_sync_worker, daemon=True)
    sync_thread.start()
    
    # Start Flask app
    logger.info("Starting SafetyAmp integration service on port 8080")
    app.run(host='0.0.0.0', port=8080)