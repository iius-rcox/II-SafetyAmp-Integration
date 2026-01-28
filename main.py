import os
import signal
import sys
import threading
import time

from flask import Flask, jsonify
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
    start_http_server,
)
import structlog

from config import config
from services.data_manager import data_manager
from services.event_manager import event_manager
from sync.sync_departments import DepartmentSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_titles import TitleSyncer
from sync.sync_vehicles import VehicleSync
from utils.failed_sync_tracker import initialize_tracker
from utils.health import run_health_checks
from utils.logger import get_logger
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
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

app = Flask(__name__)
logger = get_logger("main")

# Configuration from unified config manager
DB_POOL_SIZE = config.DB_POOL_SIZE
DB_MAX_OVERFLOW = config.DB_MAX_OVERFLOW
DB_POOL_TIMEOUT = config.DB_POOL_TIMEOUT
# Convert minutes to seconds for sync interval
SYNC_INTERVAL = max(1, int(config.SYNC_INTERVAL_MINUTES) * 60)
HEALTH_CHECK_TIMEOUT = int(os.getenv("HEALTH_CHECK_TIMEOUT", "5"))

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
    "healthy": True,
    "ready": False,
    "last_sync": None,
    "errors": [],
    "database_status": "unknown",
    "external_apis_status": "unknown",
    "sync_in_progress": False,
}

# Shutdown flag for graceful termination
shutdown_requested = False


@app.route("/health")
def health():
    """Unified comprehensive health endpoint"""
    with metrics.health_check_duration.time():
        overall = run_health_checks()
        status = overall.get("status", "unhealthy")
        # If shutdown requested, force unhealthy for kubernetes to restart/drain
        if shutdown_requested:
            status = "unhealthy"
        code = 200 if status == "healthy" else (200 if status == "degraded" else 503)
        # Update connection metrics best-effort (if available)
        try:
            metrics.database_connections_active.set(get_active_connection_count())
        except Exception:
            pass
        payload = {
            "status": status,
            "timestamp": time.time(),
            "checks": overall.get("checks", {}),
            "last_sync": health_status["last_sync"],
            "sync_in_progress": health_status["sync_in_progress"],
            "errors": health_status["errors"][-5:] if health_status["errors"] else [],
        }
        # Back-compat fields for dashboards
        health_status["database_status"] = (
            overall["checks"].get("database", {}).get("status", "unknown")
        )
        health_status["external_apis_status"] = (
            "healthy"
            if all(
                overall["checks"].get(name, {}).get("status") == "healthy"
                for name in ("safetyamp", "samsara")
            )
            else "degraded"
        )
        return jsonify(payload), code


@app.route("/ready")
def ready():
    """Readiness endpoint for Kubernetes.

    Returns 200 only when the application is ready to serve traffic, which
    requires a healthy database connection. Returns 503 otherwise.
    """
    overall = run_health_checks()
    db_status = overall.get("checks", {}).get("database", {}).get("status", "unhealthy")
    # Ready only if database is healthy
    code = 200 if (not shutdown_requested and db_status == "healthy") else 503
    payload = {
        "status": "ready" if code == 200 else "not_ready",
        "checks": overall.get("checks", {}),
        "timestamp": time.time(),
    }
    return jsonify(payload), code


@app.route("/live")
def live():
    """Liveness endpoint for Kubernetes.

    Should return 200 as long as the process is alive and not shutting down,
    regardless of downstream dependency health.
    """
    code = 200 if not shutdown_requested else 503
    return (
        jsonify(
            {
                "status": "alive" if code == 200 else "shutting_down",
                "timestamp": time.time(),
            }
        ),
        code,
    )


@app.route("/metrics")
def metrics_endpoint():
    """Prometheus metrics endpoint"""
    try:
        metrics.database_connections_active.set(get_active_connection_count())
    except Exception:
        pass
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


def run_sync_worker():
    """Enhanced background sync worker with connection pooling"""
    logger.info(
        "Starting background sync worker",
        extra={"db_pool_size": DB_POOL_SIZE, "db_max_overflow": DB_MAX_OVERFLOW},
    )

    while health_status["healthy"] and not shutdown_requested:
        try:
            logger.info("Starting sync operations")
            health_status["sync_in_progress"] = True
            metrics.current_sync_operations.inc()
            metrics.sync_in_progress_gauge.set(1)

            start_time = time.time()

            # Employee sync (currently active)
            with metrics.sync_duration_seconds.labels(operation="employees").time():
                try:
                    ee_syncer = EmployeeSyncer()
                    result = ee_syncer.sync()
                    metrics.sync_operations_total.labels(
                        operation="employees", status="success"
                    ).inc()
                    if result and "processed" in result:
                        metrics.records_processed_total.labels(
                            sync_type="employees"
                        ).inc(result["processed"])
                except Exception as e:
                    metrics.sync_operations_total.labels(
                        operation="employees", status="error"
                    ).inc()
                    raise e

            # Department sync
            with metrics.sync_duration_seconds.labels(operation="departments").time():
                try:
                    dept_syncer = DepartmentSyncer()
                    result = dept_syncer.sync()
                    metrics.sync_operations_total.labels(
                        operation="departments", status="success"
                    ).inc()
                    if result and "processed" in result:
                        metrics.records_processed_total.labels(
                            sync_type="departments"
                        ).inc(result["processed"])
                except Exception as e:
                    metrics.sync_operations_total.labels(
                        operation="departments", status="error"
                    ).inc()
                    raise e

            # Job sync
            with metrics.sync_duration_seconds.labels(operation="jobs").time():
                try:
                    job_syncer = JobSyncer()
                    result = job_syncer.sync()
                    metrics.sync_operations_total.labels(
                        operation="jobs", status="success"
                    ).inc()
                    if result and "processed" in result:
                        metrics.records_processed_total.labels(sync_type="jobs").inc(
                            result["processed"]
                        )
                except Exception as e:
                    metrics.sync_operations_total.labels(
                        operation="jobs", status="error"
                    ).inc()
                    raise e

            # Title sync
            with metrics.sync_duration_seconds.labels(operation="titles").time():
                try:
                    title_syncer = TitleSyncer()
                    result = title_syncer.sync()
                    metrics.sync_operations_total.labels(
                        operation="titles", status="success"
                    ).inc()
                    if result and "processed" in result:
                        metrics.records_processed_total.labels(sync_type="titles").inc(
                            result["processed"]
                        )
                except Exception as e:
                    metrics.sync_operations_total.labels(
                        operation="titles", status="error"
                    ).inc()
                    raise e

            # Vehicle sync
            with metrics.sync_duration_seconds.labels(operation="vehicles").time():
                try:
                    vehicle_syncer = VehicleSync()
                    result = vehicle_syncer.sync_vehicles()
                    metrics.sync_operations_total.labels(
                        operation="vehicles", status="success"
                    ).inc()
                    if result and "synced" in result:
                        metrics.records_processed_total.labels(
                            sync_type="vehicles"
                        ).inc(result["synced"])
                except Exception as e:
                    metrics.sync_operations_total.labels(
                        operation="vehicles", status="error"
                    ).inc()
                    raise e

            health_status["last_sync"] = time.time()
            health_status["ready"] = True
            health_status["errors"] = []  # Clear previous errors
            sync_duration = time.time() - start_time
            # Update last completed sync timestamp metric
            metrics.last_sync_timestamp_seconds.set(health_status["last_sync"])

            logger.info(
                "Sync operations completed successfully",
                extra={"duration_seconds": sync_duration},
            )

            # Check for error notifications (hourly)
            try:
                event_manager.send_hourly_notification()
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
            health_status["errors"].append(error_msg)
            metrics.sync_operations_total.labels(
                operation="general", status="error"
            ).inc()

            # Log to unified event manager for notifications and tracking
            try:
                event_manager.log_error(
                    kind="sync_worker_error",
                    entity="system",
                    entity_id="sync_worker",
                    message=error_msg,
                    operation="sync_worker",
                    details={
                        "exception_type": type(e).__name__,
                        "sync_in_progress": health_status.get(
                            "sync_in_progress", False
                        ),
                    },
                    source="sync_worker",
                )
            except Exception as notifier_error:
                logger.error(f"Failed to log error to event manager: {notifier_error}")

            # Don't mark as unhealthy for single sync failures
            # Allow recovery on next cycle
            logger.info("Waiting 60 seconds before retry after error")
            time.sleep(60)

        finally:
            health_status["sync_in_progress"] = False
            metrics.current_sync_operations.dec()
            metrics.sync_in_progress_gauge.set(0)


def signal_handler(signum, _frame):
    """Enhanced graceful shutdown handler"""
    global shutdown_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")

    shutdown_requested = True
    health_status["healthy"] = False

    # Wait for ongoing sync operations to complete
    max_wait = 30  # Maximum wait time in seconds
    wait_count = 0
    while health_status["sync_in_progress"] and wait_count < max_wait:
        logger.info(
            f"Waiting for sync operations to complete... ({wait_count}/{max_wait})"
        )
        time.sleep(1)
        wait_count += 1

    if health_status["sync_in_progress"]:
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

    # Validate configuration before starting services (feature flaggable)
    enable_unified_config = (
        os.getenv("ENABLE_UNIFIED_CONFIG", "1") or "1"
    ).lower() in ("1", "true", "yes")
    if enable_unified_config and not config.validate_required_secrets():
        logger.critical(
            "Configuration validation failed - running in degraded mode",
            extra={
                "missing": config.get_configuration_status()["validation"]["missing"]
            },
        )
        # Don't exit - continue running in degraded mode so the pod stays up
        # This allows operators to investigate the issue while the pod remains available

    status = (
        config.get_configuration_status()
        if enable_unified_config
        else {"validation": {"is_valid": True}, "azure": {}}
    )
    logger.info(
        "Starting SafetyAmp integration service",
        extra={
            "port": 8080,
            "db_pool_size": DB_POOL_SIZE,
            "db_max_overflow": DB_MAX_OVERFLOW,
            "sync_interval": SYNC_INTERVAL,
            "config_validation": status["validation"]["is_valid"],
            "azure_key_vault_enabled": status.get("azure", {}).get(
                "azure_key_vault_enabled"
            ),
        },
    )

    # Initialize failed sync tracker
    try:
        initialize_tracker(data_manager, config)
        logger.info("Failed sync tracker initialized successfully")
    except Exception as e:
        logger.error(
            f"Failed to initialize sync tracker: {e}. Continuing without tracker."
        )

    # Start sync worker in background
    sync_thread = threading.Thread(target=run_sync_worker, daemon=True)
    sync_thread.start()

    # Resolve bind addresses and ports from environment (defaults appropriate for containers)
    bind_address = os.getenv("BIND_ADDRESS", "0.0.0.0")
    metrics_bind_address = os.getenv("METRICS_BIND_ADDRESS", bind_address)
    metrics_port = int(os.getenv("METRICS_PORT", "9090"))
    app_port = int(os.getenv("PORT", "8080"))

    # Start dedicated Prometheus metrics HTTP server for scrapers
    try:
        start_http_server(metrics_port, addr=metrics_bind_address)
        logger.info("Prometheus metrics server started", extra={"port": metrics_port})
    except Exception as e:
        logger.error(
            f"Failed to start Prometheus metrics server on :{metrics_port}: {e}"
        )

    # Start Flask app
    app.run(host=bind_address, port=app_port, threaded=True)
