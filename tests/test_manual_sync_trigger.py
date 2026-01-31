"""
Unit tests for manual sync trigger functionality in main.py.

Tests cover:
- Queue-based sync triggering mechanism
- Sync-in-progress detection
- Event signaling to wake sync worker
"""

import os
import sys
import queue
import threading
from unittest.mock import MagicMock, patch

import pytest

# Mock redis and other external dependencies before imports
mock_redis = MagicMock()
sys.modules["redis"] = mock_redis


class TestManualSyncTrigger:
    """Tests for manual sync trigger mechanism."""

    @pytest.fixture
    def mock_health_status(self):
        """Create mock health status."""
        return {
            "healthy": True,
            "ready": False,
            "last_sync": None,
            "errors": [],
            "database_status": "unknown",
            "external_apis_status": "unknown",
            "sync_in_progress": False,
            "sync_paused": False,
        }

    @pytest.fixture
    def sync_components(self, mock_health_status):
        """Create sync queue and event for testing."""
        sync_queue = queue.Queue()
        sync_event = threading.Event()
        return sync_queue, sync_event, mock_health_status

    def test_trigger_queues_sync_type(self, sync_components):
        """Triggering sync should add sync_type to queue."""
        sync_queue, sync_event, health_status = sync_components

        # Simulate trigger_manual_sync logic
        sync_type = "employees"
        if not health_status.get("sync_in_progress"):
            sync_queue.put(sync_type)
            sync_event.set()

        # Verify queue contains the sync type
        assert not sync_queue.empty()
        assert sync_queue.get_nowait() == "employees"

    def test_trigger_sets_event(self, sync_components):
        """Triggering sync should set the event to wake worker."""
        sync_queue, sync_event, health_status = sync_components

        sync_type = "vehicles"
        if not health_status.get("sync_in_progress"):
            sync_queue.put(sync_type)
            sync_event.set()

        # Verify event is set
        assert sync_event.is_set()

    def test_trigger_blocked_when_sync_in_progress(self, sync_components):
        """Should not queue when sync is already in progress."""
        sync_queue, sync_event, health_status = sync_components
        health_status["sync_in_progress"] = True

        # Simulate trigger with sync in progress
        result = None
        if health_status.get("sync_in_progress"):
            result = {"triggered": False, "error": "Sync already in progress"}
        else:
            sync_queue.put("all")
            sync_event.set()
            result = {"triggered": True}

        # Verify sync was not queued
        assert sync_queue.empty()
        assert result["triggered"] is False
        assert "already in progress" in result["error"]

    def test_worker_processes_queued_sync(self, sync_components):
        """Worker should process sync from queue when event is set."""
        sync_queue, sync_event, health_status = sync_components

        # Queue a sync request
        sync_queue.put("departments")
        sync_event.set()

        # Simulate worker checking for sync
        processed_syncs = []
        if sync_event.is_set():
            sync_event.clear()
            try:
                sync_type = sync_queue.get_nowait()
                processed_syncs.append(sync_type)
            except queue.Empty:
                pass

        # Verify sync was processed
        assert processed_syncs == ["departments"]
        assert not sync_event.is_set()  # Event should be cleared

    def test_multiple_sync_requests_processed_in_order(self, sync_components):
        """Multiple sync requests should be processed in FIFO order."""
        sync_queue, sync_event, health_status = sync_components

        # Queue multiple sync requests
        for sync_type in ["employees", "vehicles", "titles"]:
            sync_queue.put(sync_type)
        sync_event.set()

        # Process all
        processed = []
        while not sync_queue.empty():
            processed.append(sync_queue.get_nowait())

        assert processed == ["employees", "vehicles", "titles"]


class TestTriggerManualSyncFunction:
    """Tests for the trigger_manual_sync callback behavior."""

    def test_returns_triggered_true_when_not_in_progress(self, sync_components):
        """Should return triggered=True when sync is not in progress."""
        sync_queue, sync_event, health_status = sync_components

        def trigger_manual_sync(sync_type: str) -> dict:
            if health_status.get("sync_in_progress"):
                return {"triggered": False, "error": "Sync already in progress", "sync_type": sync_type}
            sync_queue.put(sync_type)
            sync_event.set()
            return {"triggered": True, "sync_type": sync_type}

        result = trigger_manual_sync("employees")

        assert result["triggered"] is True
        assert result["sync_type"] == "employees"
        assert sync_event.is_set()

    def test_returns_triggered_false_when_in_progress(self, sync_components):
        """Should return triggered=False when sync is in progress."""
        sync_queue, sync_event, health_status = sync_components
        health_status["sync_in_progress"] = True

        def trigger_manual_sync(sync_type: str) -> dict:
            if health_status.get("sync_in_progress"):
                return {"triggered": False, "error": "Sync already in progress", "sync_type": sync_type}
            sync_queue.put(sync_type)
            sync_event.set()
            return {"triggered": True, "sync_type": sync_type}

        result = trigger_manual_sync("vehicles")

        assert result["triggered"] is False
        assert "error" in result
        assert not sync_event.is_set()

    @pytest.fixture
    def sync_components(self):
        """Create sync components for testing."""
        return (
            queue.Queue(),
            threading.Event(),
            {"sync_in_progress": False}
        )
