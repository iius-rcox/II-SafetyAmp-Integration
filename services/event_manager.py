#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Any, Optional, List
from pathlib import Path
import json
import time
from datetime import datetime, timezone
from utils.logger import get_logger
from utils.metrics import metrics


logger = get_logger("event_manager")


class _ChangeTracker:
    """Internal change tracker (migrated from utils.change_tracker)."""

    def __init__(self, output_dir: str = "output/changes") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: Dict[str, Any] = {
            "session_id": f"sync_{int(time.time())}",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "sync_type": None,
            "changes": {
                "created": [],
                "updated": [],
                "deleted": [],
                "skipped": [],
                "errors": [],
            },
            "summary": {
                "total_processed": 0,
                "total_created": 0,
                "total_updated": 0,
                "total_deleted": 0,
                "total_skipped": 0,
                "total_errors": 0,
                "start_time": None,
                "end_time": None,
                "duration_seconds": 0,
            },
        }
        self.current_session["summary"]["start_time"] = datetime.now(
            timezone.utc
        ).isoformat()

    def start_sync(self, sync_type: str) -> None:
        self.current_session["sync_type"] = sync_type

    def log_creation(
        self, entity_type: str, entity_id: str, data: Dict[str, Any]
    ) -> None:
        self.current_session["changes"]["created"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": "created",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "data": data,
                "status": "success",
            }
        )
        self.current_session["summary"]["total_created"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            metrics.changes_total.labels(entity_type=entity_type, operation="created", status="success").inc()  # type: ignore[attr-defined]
        except Exception:
            pass

    def log_update(
        self,
        entity_type: str,
        entity_id: str,
        changes: Dict[str, Any],
        original_data: Optional[Dict[str, Any]],
    ) -> None:
        self.current_session["changes"]["updated"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": "updated",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "changes": changes,
                "original_data": original_data,
                "status": "success",
            }
        )
        self.current_session["summary"]["total_updated"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            metrics.changes_total.labels(entity_type=entity_type, operation="updated", status="success").inc()  # type: ignore[attr-defined]
        except Exception:
            pass

    def log_deletion(self, entity_type: str, entity_id: str, reason: str) -> None:
        self.current_session["changes"]["deleted"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": "deleted",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "reason": reason,
                "status": "success",
            }
        )
        self.current_session["summary"]["total_deleted"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            metrics.changes_total.labels(entity_type=entity_type, operation="deleted", status="success").inc()  # type: ignore[attr-defined]
        except Exception:
            pass

    def log_skip(self, entity_type: str, entity_id: str, reason: str) -> None:
        self.current_session["changes"]["skipped"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": "skipped",
                "entity_type": entity_type,
                "entity_id": entity_id,
                "reason": reason,
            }
        )
        self.current_session["summary"]["total_skipped"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            metrics.changes_total.labels(entity_type=entity_type, operation="skipped", status="success").inc()  # type: ignore[attr-defined]
        except Exception:
            pass

    def log_error(
        self,
        entity_type: str,
        entity_id: str,
        error: str,
        operation: str,
        data: Optional[Dict[str, Any]],
    ) -> None:
        self.current_session["changes"]["errors"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": operation,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "error": error,
                "data": data,
                "status": "error",
            }
        )
        self.current_session["summary"]["total_errors"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            metrics.changes_total.labels(entity_type=entity_type, operation=operation or "unknown", status="error").inc()  # type: ignore[attr-defined]
        except Exception:
            pass

    def end_sync(self) -> Dict[str, Any]:
        end_time = datetime.now(timezone.utc)
        start_time = datetime.fromisoformat(self.current_session["summary"]["start_time"])  # type: ignore[arg-type]
        duration = (end_time - start_time).total_seconds()
        self.current_session["summary"]["end_time"] = end_time.isoformat()
        self.current_session["summary"]["duration_seconds"] = duration
        session_file = self.output_dir / f"{self.current_session['session_id']}.json"
        try:
            session_file.write_text(
                json.dumps(self.current_session, indent=2, default=str),
                encoding="utf-8",
            )
        except Exception:
            pass
        return self.current_session

    # ---- Reporting helpers for external scripts ----
    def _session_files(self) -> List[Path]:
        try:
            return sorted(
                self.output_dir.glob("sync_*.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        except Exception:
            return []

    def get_recent_changes(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Aggregate recent change events from persisted session files.

        Returns a flat list of change dicts with added session metadata.
        """
        cutoff_ts = datetime.now(timezone.utc).timestamp() - hours * 3600
        all_changes: List[Dict[str, Any]] = []
        for session_path in self._session_files():
            try:
                session = json.loads(session_path.read_text(encoding="utf-8"))
                summary = session.get("summary", {})
                # Include session if it overlaps the cutoff window
                end_time = summary.get("end_time") or summary.get("start_time")
                if not end_time:
                    continue
                try:
                    end_ts = datetime.fromisoformat(str(end_time)).timestamp()
                except Exception:
                    continue
                if end_ts < cutoff_ts:
                    continue
                session_id = session.get("session_id")
                sync_type = session.get("sync_type")
                for op_key in ("created", "updated", "deleted", "skipped", "errors"):
                    for change in session.get("changes", {}).get(op_key, []):
                        # Normalize shape and attach session metadata
                        change["session_id"] = session_id
                        change["sync_type"] = sync_type
                        # Standardize operation key
                        change.setdefault("operation", op_key)
                        all_changes.append(change)
            except Exception:
                continue

        # Sort by timestamp descending
        def _parse_ts(val: str) -> float:
            try:
                return datetime.fromisoformat(val).timestamp()
            except Exception:
                return 0.0

        return sorted(
            all_changes,
            key=lambda c: _parse_ts(str(c.get("timestamp", ""))),
            reverse=True,
        )

    def get_summary_report(self, hours: int = 24) -> Dict[str, Any]:
        """Return a compact summary for dashboards and scripts.

        Structure:
          {
            total_changes, by_operation, by_entity_type, recent_sessions: [...]
          }
        """
        changes = self.get_recent_changes(hours)
        by_operation: Dict[str, int] = {}
        by_entity_type: Dict[str, int] = {}
        for ch in changes:
            op = str(ch.get("operation", "unknown"))
            ent = str(ch.get("entity_type", "unknown"))
            by_operation[op] = by_operation.get(op, 0) + 1
            by_entity_type[ent] = by_entity_type.get(ent, 0) + 1

        # Build recent sessions summary (latest 5)
        sessions: List[Dict[str, Any]] = []
        for session_path in self._session_files()[:5]:
            try:
                session = json.loads(session_path.read_text(encoding="utf-8"))
                summary = session.get("summary", {})
                sessions.append(
                    {
                        "session_id": session.get("session_id"),
                        "sync_type": session.get("sync_type"),
                        "total_processed": summary.get("total_processed", 0),
                        "total_created": summary.get("total_created", 0),
                        "total_updated": summary.get("total_updated", 0),
                        "total_deleted": summary.get("total_deleted", 0),
                        "total_skipped": summary.get("total_skipped", 0),
                        "total_errors": summary.get("total_errors", 0),
                        "duration_seconds": summary.get("duration_seconds", 0),
                        "start_time": summary.get("start_time"),
                        "end_time": summary.get("end_time"),
                    }
                )
            except Exception:
                continue

        return {
            "total_changes": sum(by_operation.values()),
            "by_operation": by_operation,
            "by_entity_type": by_entity_type,
            "recent_sessions": sessions,
        }


class _ErrorNotifier:
    """Internal notifier (migrated from utils.error_notifier)."""

    def __init__(self, data_dir: str = "output/errors") -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.errors_file = self.data_dir / "error_log.json"
        self.last_notification_file = self.data_dir / "last_notification.json"
        if self.errors_file.exists():
            try:
                self.errors: List[Dict[str, Any]] = json.loads(
                    self.errors_file.read_text(encoding="utf-8")
                )
            except Exception:
                self.errors = []
        else:
            self.errors = []

    def _save(self) -> None:
        try:
            self.errors_file.write_text(
                json.dumps(self.errors, indent=2, default=str), encoding="utf-8"
            )
        except Exception:
            pass

    def log_error(
        self,
        error_type: str,
        entity_type: str,
        entity_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
        source: str = "sync",
    ) -> None:
        self.errors.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error_type": error_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "error_message": error_message,
                "error_details": error_details or {},
                "source": source,
            }
        )
        self._save()
        try:
            metrics.errors_total.labels(error_type=error_type, entity_type=entity_type, source=source).inc()  # type: ignore[attr-defined]
        except Exception:
            pass

    def get_errors_since(self, hours: int = 1) -> List[Dict[str, Any]]:
        cutoff = datetime.now(timezone.utc).timestamp() - hours * 3600
        out: List[Dict[str, Any]] = []
        for e in self.errors:
            try:
                ts = datetime.fromisoformat(e.get("timestamp", ""))
                if ts.timestamp() >= cutoff:
                    out.append(e)
            except Exception:
                continue
        return out

    def _should_send(self) -> bool:
        if not self.last_notification_file.exists():
            return True
        try:
            last = json.loads(self.last_notification_file.read_text(encoding="utf-8"))
            last_ts = datetime.fromisoformat(last.get("timestamp", ""))
            return (datetime.now(timezone.utc) - last_ts).total_seconds() >= 3600
        except Exception:
            return True

    def _mark_sent(self) -> None:
        try:
            self.last_notification_file.write_text(
                json.dumps(
                    {"timestamp": datetime.now(timezone.utc).isoformat()}, indent=2
                ),
                encoding="utf-8",
            )
        except Exception:
            pass

    def send_hourly_notification(self) -> bool:
        if not self._should_send():
            return False
        if len(self.get_errors_since(1)) == 0:
            return False
        # No-op email body here; integrate with utils.emailer if desired
        self._mark_sent()
        return True

    def cleanup_old_errors(self, days: int = 7) -> None:
        cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
        filtered: List[Dict[str, Any]] = []
        for e in self.errors:
            try:
                ts = datetime.fromisoformat(e.get("timestamp", ""))
                if ts.timestamp() >= cutoff:
                    filtered.append(e)
            except Exception:
                continue
        self.errors = filtered
        self._save()

    def get_notification_status(self) -> Dict[str, Any]:
        recent = self.get_errors_since(1)
        return {
            "total_errors_last_hour": len(recent),
            "should_send_notification": self._should_send(),
            "last_notification_sent": (
                json.loads(self.last_notification_file.read_text())
                if self.last_notification_file.exists()
                else None
            ),
        }


class EventManager:
    """Unified event manager for sessions, change tracking, and notifications.

    Wraps existing `ChangeTracker` and `ErrorNotifier` to provide a stable API
    for emitting creation/update/deletion events, errors, and session lifecycle.
    """

    def __init__(
        self,
        change_tracker: Optional[_ChangeTracker] = None,
        error_notifier: Optional[_ErrorNotifier] = None,
    ) -> None:
        self.change_tracker = change_tracker or _ChangeTracker()
        self.error_notifier = error_notifier or _ErrorNotifier()
        self._current_session_id: Optional[str] = None

    # ----- Session lifecycle -----
    def start_sync(self, name: str, correlation_id: Optional[str] = None) -> str:
        self.change_tracker.start_sync(name)
        self._current_session_id = self.change_tracker.current_session.get("session_id")
        logger.info(
            "Sync session started",
            extra={
                "sync_type": name,
                "session_id": self._current_session_id,
                "correlation_id": correlation_id,
            },
        )
        return self._current_session_id or ""

    def end_sync(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        summary = self.change_tracker.end_sync()
        logger.info(
            "Sync session ended",
            extra={
                "session_id": session_id or self._current_session_id,
                "summary": summary.get("summary"),
            },
        )
        self._current_session_id = None
        return summary

    # ----- Change events -----
    def log_creation(
        self,
        entity: str,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self.change_tracker.log_creation(entity, entity_id, details or {})

    def log_update(
        self,
        entity: str,
        entity_id: str,
        changes: Optional[Dict[str, Any]] = None,
        original_data: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self.change_tracker.log_update(entity, entity_id, changes or {}, original_data)

    def log_deletion(
        self,
        entity: str,
        entity_id: str,
        reason: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self.change_tracker.log_deletion(entity, entity_id, reason or "sync_cleanup")

    def log_skip(
        self, entity: str, entity_id: str, reason: str, session_id: Optional[str] = None
    ) -> None:
        self.change_tracker.log_skip(entity, entity_id, reason)

    # ----- Errors -----
    def log_error(
        self,
        kind: str,
        entity: Optional[str],
        entity_id: Optional[str],
        message: str,
        exc: Optional[BaseException] = None,
        session_id: Optional[str] = None,
        operation: str = "unknown",
        details: Optional[Dict[str, Any]] = None,
        source: str = "sync",
    ) -> None:
        # Bridge to change tracker
        self.change_tracker.log_error(
            entity_type=entity or "system",
            entity_id=entity_id or "unknown",
            error=message,
            operation=operation,
            data=details,
        )
        # Bridge to notifier
        try:
            self.error_notifier.log_error(
                error_type=kind,
                entity_type=entity or "system",
                entity_id=entity_id or "unknown",
                error_message=message,
                error_details=details,
                source=source,
            )
        except Exception as notify_error:
            logger.error(f"Failed to log error to notifier: {notify_error}")

    # ----- Notifications -----
    def send_hourly_notification(self) -> bool:
        return self.error_notifier.send_hourly_notification()


# Global singleton
event_manager = EventManager()
