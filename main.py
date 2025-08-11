from flask import Flask, jsonify
from sync.sync_departments import DepartmentSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_titles import TitleSyncer
from sync.sync_vehicles import VehicleSync
import signal
import sys
import threading
import time
import os
from utils.logger import get_logger
from utils.error_manager import error_manager
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST, REGISTRY, start_http_server
from circuitbreaker import circuit
import structlog
from utils.metrics import metrics

# Initialize structured logging
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

app = Flask(__name__)
logger = get_logger("main")

# Configuration from environment
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '5'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '10'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', '3600'))
HEALTH_CHECK_TIMEOUT = int(os.getenv('HEALTH_CHECK_TIMEOUT', '5'))

# Database connection tracking
_active_connections = set()
_connection_lock = threading.Lock()

def track_connection(connection):
    """Add a connection to the active connections tracker"""
    with _connection_lock:
        _active_connections.add(id(connection))
        logger.debug(f"Connection opened, active count: {len(_active_connections)}")

def untrack_connection(connection):
    """Remove a connection from the active connections tracker"""
    with _connection_lock:
        _active_connections.discard(id(connection))
        logger.debug(f"Connection closed, active count: {len(_active_connections)}")

def get_active_connection_count():
    """Get the current number of active database connections"""
    with _connection_lock:
        return len(_active_connections)

# Global health status with enhanced tracking
health_status = {
    'healthy': True,
    'ready': False,
    'last_sync': None,
    'errors': [],
    'database_status': 'unknown',
    'external_apis_status': 'unknown',
    'sync_in_progress': False
}

# Shutdown flag for graceful termination
shutdown_requested = False

@circuit(failure_threshold=3, recovery_timeout=30, expected_exception=Exception)
def check_database_health():
    """Check database connectivity with circuit breaker"""
    try:
        # This would be replaced with actual database health check
        # For now, simulate a quick connection test
        import time
        time.sleep(0.1)  # Simulate DB check
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise

@circuit(failure_threshold=5, recovery_timeout=60, expected_exception=Exception)
def check_external_apis():
    """Check external API connectivity with circuit breaker"""
    try:
        # This would include checks for SafetyAmp API, Viewpoint, etc.
        # For now, simulate API health checks
        import time
        time.sleep(0.1)  # Simulate API check
        return True
    except Exception as e:
        logger.error(f"External API health check failed: {e}")
        raise

@app.route('/health')
def health():
    """Enhanced liveness probe endpoint"""
    with metrics.health_check_duration.time():
        if health_status['healthy'] and not shutdown_requested:
            return jsonify({
                'status': 'healthy', 
                'timestamp': time.time(),
                'sync_in_progress': health_status['sync_in_progress']
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy', 
                'errors': health_status['errors'],
                'shutdown_requested': shutdown_requested
            }), 503

@app.route('/ready')
def ready():
    """Enhanced readiness probe endpoint with graceful degradation"""
    with metrics.health_check_duration.time():
        overall_status = 'ready'
        status_code = 200
        details = {}
        
        # Check database health
        try:
            check_database_health()
            health_status['database_status'] = 'healthy'
            details['database'] = 'healthy'
        except Exception as e:
            health_status['database_status'] = 'degraded'
            details['database'] = 'degraded'
            overall_status = 'degraded'
            logger.warning(f"Database health degraded: {e}")
        
        # Check external APIs
        try:
            check_external_apis()
            health_status['external_apis_status'] = 'healthy'
            details['external_apis'] = 'healthy'
        except Exception as e:
            health_status['external_apis_status'] = 'degraded'
            details['external_apis'] = 'degraded'
            if overall_status == 'ready':
                overall_status = 'degraded'
            logger.warning(f"External APIs health degraded: {e}")
        
        # Allow readiness during initial sync or if already ready
        if health_status['ready'] or health_status['sync_in_progress'] or overall_status == 'degraded':
            return jsonify({
                'status': overall_status,
                'timestamp': time.time(),
                'details': details,
                'last_sync': health_status['last_sync'],
                'sync_in_progress': health_status['sync_in_progress']
            }), status_code
        else:
            return jsonify({
                'status': 'not ready',
                'details': details
            }), 503

@app.route('/metrics')
def metrics_endpoint():
    """Enhanced Prometheus metrics endpoint"""
    # Update connection pool metrics with actual active connections
    metrics.database_connections_active.set(get_active_connection_count())
    
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

@app.route('/health/detailed')
def detailed_health():
    """Enhanced health check for production monitoring"""
    from services.data_manager import data_manager
    from utils.circuit_breaker import SmartRateLimiter
    
    safetyamp_rate_limiter = SmartRateLimiter("safetyamp")
    samsara_rate_limiter = SmartRateLimiter("samsara")
    
    return jsonify({
        'status': 'healthy' if health_status['healthy'] else 'unhealthy',
        'timestamp': time.time(),
        'last_sync': health_status['last_sync'],
        'active_connections': get_active_connection_count(),
        'database_status': health_status['database_status'],
        'external_apis_status': health_status['external_apis_status'],
        'cache_status': getattr(data_manager, 'get_cache_info', lambda: {'status': 'unknown'})(),
        'rate_limit_status': {
            'safetyamp': safetyamp_rate_limiter.status(),
            'samsara': samsara_rate_limiter.status()
        },
        'sync_in_progress': health_status['sync_in_progress'],
        'errors': health_status['errors'][-5:] if health_status['errors'] else []  # Last 5 errors
    })

def run_sync_worker():
    """Enhanced background sync worker with connection pooling"""
    logger.info("Starting background sync worker", 
                extra={
                    'db_pool_size': DB_POOL_SIZE, 
                    'db_max_overflow': DB_MAX_OVERFLOW
                })
    
    while health_status['healthy'] and not shutdown_requested:
        try:
            logger.info("Starting sync operations")
            health_status['sync_in_progress'] = True
            metrics.current_sync_operations.inc()
            metrics.sync_in_progress_gauge.set(1)
            
            start_time = time.time()
            
            # Employee sync (currently active)
            with metrics.sync_duration_seconds.labels(operation='employees').time():
                try:
                    ee_syncer = EmployeeSyncer()
                    result = ee_syncer.sync()
                    metrics.sync_operations_total.labels(operation='employees', status='success').inc()
                    if result and 'processed' in result:
                        metrics.records_processed_total.labels(sync_type='employees').inc(result['processed'])
                except Exception as e:
                    metrics.sync_operations_total.labels(operation='employees', status='error').inc()
                    raise e
            
            # Department sync
            with metrics.sync_duration_seconds.labels(operation='departments').time():
                try:
                    dept_syncer = DepartmentSyncer()
                    result = dept_syncer.sync()
                    metrics.sync_operations_total.labels(operation='departments', status='success').inc()
                    if result and 'processed' in result:
                        metrics.records_processed_total.labels(sync_type='departments').inc(result['processed'])
                except Exception as e:
                    metrics.sync_operations_total.labels(operation='departments', status='error').inc()
                    raise e
            
            # Job sync
            with metrics.sync_duration_seconds.labels(operation='jobs').time():
                try:
                    job_syncer = JobSyncer()
                    result = job_syncer.sync()
                    metrics.sync_operations_total.labels(operation='jobs', status='success').inc()
                    if result and 'processed' in result:
                        metrics.records_processed_total.labels(sync_type='jobs').inc(result['processed'])
                except Exception as e:
                    metrics.sync_operations_total.labels(operation='jobs', status='error').inc()
                    raise e
            
            # Title sync
            with metrics.sync_duration_seconds.labels(operation='titles').time():
                try:
                    title_syncer = TitleSyncer()
                    result = title_syncer.sync()
                    metrics.sync_operations_total.labels(operation='titles', status='success').inc()
                    if result and 'processed' in result:
                        metrics.records_processed_total.labels(sync_type='titles').inc(result['processed'])
                except Exception as e:
                    metrics.sync_operations_total.labels(operation='titles', status='error').inc()
                    raise e
            
            # Vehicle sync
            with metrics.sync_duration_seconds.labels(operation='vehicles').time():
                try:
                    vehicle_syncer = VehicleSync()
                    result = vehicle_syncer.sync_vehicles()
                    metrics.sync_operations_total.labels(operation='vehicles', status='success').inc()
                    if result and 'synced' in result:
                        metrics.records_processed_total.labels(sync_type='vehicles').inc(result['synced'])
                except Exception as e:
                    metrics.sync_operations_total.labels(operation='vehicles', status='error').inc()
                    raise e
            
            health_status['last_sync'] = time.time()
            health_status['ready'] = True
            health_status['errors'] = []  # Clear previous errors
            sync_duration = time.time() - start_time
            # Update last completed sync timestamp metric
            metrics.last_sync_timestamp_seconds.set(health_status['last_sync'])
            
            logger.info("Sync operations completed successfully", 
                       duration_seconds=sync_duration)
            
            # Check for error notifications (hourly)
            try:
                error_manager.send_hourly_notification()
            except Exception as e:
                logger.error(f"Error sending hourly notification: {e}")
            
            # Sleep for sync interval
            logger.info(f"Sleeping for {SYNC_INTERVAL} seconds until next sync")
            for i in range(SYNC_INTERVAL):
                if shutdown_requested:
                    break
                time.sleep(1)
            
        except Exception as e:
            error_msg = f"Sync worker error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            health_status['errors'].append(error_msg)
            metrics.sync_operations_total.labels(operation='general', status='error').inc()
            
            # Log to error notifier for email notifications
            try:
                error_notifier.log_error(
                    error_type="sync_worker_error",
                    entity_type="system",
                    entity_id="sync_worker",
                    error_message=error_msg,
                    error_details={
                        "exception_type": type(e).__name__,
                        "sync_in_progress": health_status.get('sync_in_progress', False)
                    },
                    source="sync_worker"
                )
            except Exception as notifier_error:
                logger.error(f"Failed to log error to notifier: {notifier_error}")
            
            # Don't mark as unhealthy for single sync failures
            # Allow recovery on next cycle
            logger.info("Waiting 60 seconds before retry after error")
            time.sleep(60)
            
        finally:
            health_status['sync_in_progress'] = False
            metrics.current_sync_operations.dec()
            metrics.sync_in_progress_gauge.set(0)

def signal_handler(signum, frame):
    """Enhanced graceful shutdown handler"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    
    shutdown_requested = True
    health_status['healthy'] = False
    
    # Wait for ongoing sync operations to complete
    max_wait = 30  # Maximum wait time in seconds
    wait_count = 0
    while health_status['sync_in_progress'] and wait_count < max_wait:
        logger.info(f"Waiting for sync operations to complete... ({wait_count}/{max_wait})")
        time.sleep(1)
        wait_count += 1
    
    if health_status['sync_in_progress']:
        logger.warning("Forced shutdown - sync operations may have been interrupted")
    else:
        logger.info("Graceful shutdown completed - all sync operations finished")
    
    # Close database connections here if using connection pools
    # db_pool.close_all()
    
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Log startup configuration
    logger.info("Starting SafetyAmp integration service", 
                extra={
                    'port': 8080,
                    'db_pool_size': DB_POOL_SIZE,
                    'db_max_overflow': DB_MAX_OVERFLOW,
                    'sync_interval': SYNC_INTERVAL
                })
    
    # Start sync worker in background
    sync_thread = threading.Thread(target=run_sync_worker, daemon=True)
    sync_thread.start()
    
    # Resolve bind addresses and ports from environment (defaults appropriate for containers)
    bind_address = os.getenv('BIND_ADDRESS', '0.0.0.0')
    metrics_bind_address = os.getenv('METRICS_BIND_ADDRESS', bind_address)
    metrics_port = int(os.getenv('METRICS_PORT', '9090'))
    app_port = int(os.getenv('PORT', '8080'))

    # Start dedicated Prometheus metrics HTTP server for scrapers
    try:
        start_http_server(metrics_port, addr=metrics_bind_address)
        logger.info("Prometheus metrics server started", extra={"port": metrics_port})
    except Exception as e:
        logger.error(f"Failed to start Prometheus metrics server on :{metrics_port}: {e}")

    # Start Flask app
    app.run(host=bind_address, port=app_port, threaded=True)