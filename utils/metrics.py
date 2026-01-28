from typing import List, Optional
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    REGISTRY,
)


class MetricsCollector:
    """Centralized metrics collector with safe get-or-create semantics.

    Exposes commonly used application metrics as attributes, and provides
    helpers to obtain additional counters, gauges, and histograms on demand.
    """

    def __init__(self) -> None:
        # Pre-populated metrics are initialized lazily on first access
        self._initialized: bool = False

        # Well-known metrics exposed as attributes after initialization
        self.sync_operations_total: Optional[Counter] = None
        self.sync_duration_seconds: Optional[Histogram] = None
        self.records_processed_total: Optional[Counter] = None
        self.current_sync_operations: Optional[Gauge] = None
        self.health_check_duration: Optional[Histogram] = None
        self.database_connections_active: Optional[Gauge] = None
        self.sync_in_progress_gauge: Optional[Gauge] = None
        self.last_sync_timestamp_seconds: Optional[Gauge] = None

        # Cache metrics
        self.cache_last_updated_ts: Optional[Gauge] = None
        self.cache_items_total: Optional[Gauge] = None
        self.cache_ttl_seconds: Optional[Gauge] = None

        # Domain metrics
        self.changes_total: Optional[Counter] = None
        self.errors_total: Optional[Counter] = None

        # Failed sync tracker metrics
        self.failed_sync_skipped_total: Optional[Counter] = None
        self.failed_sync_retries_total: Optional[Counter] = None
        self.failed_sync_records_gauge: Optional[Gauge] = None

    # ---------- Low-level helpers ----------
    def _get_existing(self, name: str):
        try:
            return REGISTRY._names_to_collectors[name]
        except KeyError:
            return None

    def get_counter(
        self, name: str, description: str, labelnames: Optional[List[str]] = None
    ) -> Counter:
        existing = self._get_existing(name)
        if isinstance(existing, Counter):
            return existing
        if existing is not None:
            raise ValueError(
                f"A collector named '{name}' is already registered with a different type"
            )
        return Counter(name, description, labelnames=labelnames or [])

    def get_gauge(
        self, name: str, description: str, labelnames: Optional[List[str]] = None
    ) -> Gauge:
        existing = self._get_existing(name)
        if isinstance(existing, Gauge):
            return existing
        if existing is not None:
            raise ValueError(
                f"A collector named '{name}' is already registered with a different type"
            )
        return Gauge(name, description, labelnames=labelnames or [])

    def get_histogram(
        self,
        name: str,
        description: str,
        labelnames: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        existing = self._get_existing(name)
        if isinstance(existing, Histogram):
            return existing
        if existing is not None:
            raise ValueError(
                f"A collector named '{name}' is already registered with a different type"
            )
        if buckets is not None:
            return Histogram(
                name, description, labelnames=labelnames or [], buckets=buckets
            )
        return Histogram(name, description, labelnames=labelnames or [])

    # ---------- High-level initialization ----------
    def initialize_defaults(self) -> None:
        """Idempotently initialize standard application metrics."""
        if self._initialized:
            return

        # Core sync metrics
        self.sync_operations_total = self.get_counter(
            "safetyamp_sync_operations_total",
            "Total sync operations",
            labelnames=["operation", "status"],
        )
        self.sync_duration_seconds = self.get_histogram(
            "safetyamp_sync_duration_seconds",
            "Sync operation duration",
            labelnames=["operation"],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
        )
        self.records_processed_total = self.get_counter(
            "safetyamp_records_processed_total",
            "Total records processed",
            labelnames=["sync_type"],
        )
        self.current_sync_operations = self.get_gauge(
            "safetyamp_current_sync_operations",
            "Current ongoing sync operations",
        )
        self.health_check_duration = self.get_histogram(
            "safetyamp_health_check_duration_seconds",
            "Health check duration",
        )
        self.database_connections_active = self.get_gauge(
            "safetyamp_database_connections_active",
            "Active database connections",
        )
        self.sync_in_progress_gauge = self.get_gauge(
            "safetyamp_sync_in_progress",
            "Whether a sync is currently in progress (0/1)",
        )
        self.last_sync_timestamp_seconds = self.get_gauge(
            "safetyamp_last_sync_timestamp_seconds",
            "Epoch seconds of last completed sync",
        )

        # Cache telemetry
        self.cache_last_updated_ts = self.get_gauge(
            "safetyamp_cache_last_updated_timestamp_seconds",
            "Epoch seconds of last cache update",
            labelnames=["cache"],
        )
        self.cache_items_total = self.get_gauge(
            "safetyamp_cache_items_total",
            "Number of items stored for a given cache",
            labelnames=["cache"],
        )
        self.cache_ttl_seconds = self.get_gauge(
            "safetyamp_cache_ttl_seconds",
            "Configured TTL seconds for a given cache (remaining TTL when saved)",
            labelnames=["cache"],
        )

        # Domain metrics
        self.changes_total = self.get_counter(
            "safetyamp_changes_total",
            "Total change events by entity type, operation, and status",
            labelnames=["entity_type", "operation", "status"],
        )
        self.errors_total = self.get_counter(
            "safetyamp_errors_total",
            "Total error events by error type, entity type, and source",
            labelnames=["error_type", "entity_type", "source"],
        )

        # Failed sync tracker metrics
        self.failed_sync_skipped_total = self.get_counter(
            "safetyamp_failed_sync_skipped_total",
            "Records skipped due to unchanged problematic fields since last failure",
            labelnames=["entity_type"],
        )
        self.failed_sync_retries_total = self.get_counter(
            "safetyamp_failed_sync_retries_total",
            "Records retried after problematic fields changed",
            labelnames=["entity_type"],
        )
        self.failed_sync_records_gauge = self.get_gauge(
            "safetyamp_failed_sync_records_total",
            "Total failed sync records currently tracked in Redis",
            labelnames=["entity_type"],
        )

        self._initialized = True


# Global singleton instance used across the application
metrics = MetricsCollector()
metrics.initialize_defaults()
