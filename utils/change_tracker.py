#!/usr/bin/env python3
"""
Change Tracker for SafetyAmp Integration

This module provides comprehensive tracking of all changes made during sync operations,
including user creation, updates, deletions, and any errors encountered.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from utils.logger import get_logger
from utils.metrics import get_or_create_counter

logger = get_logger("change_tracker")

_changes_counter = get_or_create_counter(
    'safetyamp_changes_total',
    'Total change events by entity type, operation, and status',
    labelnames=['entity_type', 'operation', 'status']
)

class ChangeTracker:
    """Tracks all changes made during sync operations"""
    
    def __init__(self, output_dir: str = "output/changes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize tracking data
        self.current_session = {
            "session_id": f"sync_{int(time.time())}",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "sync_type": None,
            "changes": {
                "created": [],
                "updated": [],
                "deleted": [],
                "skipped": [],
                "errors": []
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
                "duration_seconds": 0
            }
        }
        
        # Track session start time
        self.current_session["summary"]["start_time"] = datetime.now(timezone.utc).isoformat()
        
    def start_sync(self, sync_type: str):
        """Start tracking a new sync operation"""
        self.current_session["sync_type"] = sync_type
        logger.info(f"Starting change tracking for {sync_type} sync")
        
    def log_creation(self, entity_type: str, entity_id: str, data: Dict[str, Any], 
                    source_system: str = "viewpoint", target_system: str = "safetyamp"):
        """Log a creation operation"""
        change_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "created",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_system": source_system,
            "target_system": target_system,
            "data": data,
            "status": "success"
        }
        
        self.current_session["changes"]["created"].append(change_record)
        self.current_session["summary"]["total_created"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            _changes_counter.labels(entity_type=entity_type, operation='created', status='success').inc()
        except Exception:
            pass
        
        logger.info(f"Created {entity_type} {entity_id} in {target_system}")
        
    def log_update(self, entity_type: str, entity_id: str, changes: Dict[str, Any], 
                  original_data: Optional[Dict[str, Any]] = None,
                  source_system: str = "viewpoint", target_system: str = "safetyamp"):
        """Log an update operation"""
        change_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "updated",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_system": source_system,
            "target_system": target_system,
            "changes": changes,
            "original_data": original_data,
            "status": "success"
        }
        
        self.current_session["changes"]["updated"].append(change_record)
        self.current_session["summary"]["total_updated"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            _changes_counter.labels(entity_type=entity_type, operation='updated', status='success').inc()
        except Exception:
            pass
        
        logger.info(f"Updated {entity_type} {entity_id} in {target_system} with changes: {list(changes.keys())}")
        
    def log_deletion(self, entity_type: str, entity_id: str, reason: str = "sync_cleanup",
                    source_system: str = "viewpoint", target_system: str = "safetyamp"):
        """Log a deletion operation"""
        change_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "deleted",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_system": source_system,
            "target_system": target_system,
            "reason": reason,
            "status": "success"
        }
        
        self.current_session["changes"]["deleted"].append(change_record)
        self.current_session["summary"]["total_deleted"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            _changes_counter.labels(entity_type=entity_type, operation='deleted', status='success').inc()
        except Exception:
            pass
        
        logger.info(f"Deleted {entity_type} {entity_id} from {target_system} - Reason: {reason}")
        
    def log_skip(self, entity_type: str, entity_id: str, reason: str,
                source_system: str = "viewpoint", target_system: str = "safetyamp"):
        """Log a skipped operation"""
        skip_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": "skipped",
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_system": source_system,
            "target_system": target_system,
            "reason": reason
        }
        
        self.current_session["changes"]["skipped"].append(skip_record)
        self.current_session["summary"]["total_skipped"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            _changes_counter.labels(entity_type=entity_type, operation='skipped', status='success').inc()
        except Exception:
            pass
        
        logger.warning(f"Skipped {entity_type} {entity_id} - Reason: {reason}")
        
    def log_error(self, entity_type: str, entity_id: str, error: str, 
                 operation: str = "unknown", data: Optional[Dict[str, Any]] = None,
                 source_system: str = "viewpoint", target_system: str = "safetyamp"):
        """Log an error"""
        error_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_system": source_system,
            "target_system": target_system,
            "error": error,
            "data": data,
            "status": "error"
        }
        
        self.current_session["changes"]["errors"].append(error_record)
        self.current_session["summary"]["total_errors"] += 1
        self.current_session["summary"]["total_processed"] += 1
        try:
            _changes_counter.labels(entity_type=entity_type, operation=operation or 'unknown', status='error').inc()
        except Exception:
            pass
        
        logger.error(f"Error {operation} {entity_type} {entity_id}: {error}")
        
    def end_sync(self) -> Dict[str, Any]:
        """End the current sync session and save the results"""
        # Calculate duration
        end_time = datetime.now(timezone.utc)
        start_time = datetime.fromisoformat(self.current_session["summary"]["start_time"])
        duration = (end_time - start_time).total_seconds()
        
        self.current_session["summary"]["end_time"] = end_time.isoformat()
        self.current_session["summary"]["duration_seconds"] = duration
        
        # Save session to file
        session_file = self.output_dir / f"{self.current_session['session_id']}.json"
        with open(session_file, 'w') as f:
            json.dump(self.current_session, f, indent=2, default=str)
        
        # Log summary
        summary = self.current_session["summary"]
        logger.info(f"Sync completed: {summary['total_processed']} processed, "
                   f"{summary['total_created']} created, {summary['total_updated']} updated, "
                   f"{summary['total_skipped']} skipped, {summary['total_errors']} errors "
                   f"in {duration:.2f} seconds")
        
        return self.current_session
        
    def get_recent_changes(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get all changes from the last N hours"""
        changes = []
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        
        for session_file in self.output_dir.glob("*.json"):
            if session_file.stat().st_mtime < cutoff_time:
                continue
                
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                    
                # Add session info to each change
                for change_type, change_list in session_data["changes"].items():
                    for change in change_list:
                        change["session_id"] = session_data["session_id"]
                        change["sync_type"] = session_data["sync_type"]
                        changes.append(change)
                        
            except Exception as e:
                logger.error(f"Error reading session file {session_file}: {e}")
                
        # Sort by timestamp
        changes.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return changes
        
    def get_summary_report(self, hours: int = 24) -> Dict[str, Any]:
        """Get a summary report of recent sync activity"""
        changes = self.get_recent_changes(hours)
        
        summary = {
            "period_hours": hours,
            "total_changes": len(changes),
            "by_operation": {},
            "by_entity_type": {},
            "by_status": {},
            "recent_sessions": []
        }
        
        # Count by operation
        for change in changes:
            operation = change.get("operation", "unknown")
            entity_type = change.get("entity_type", "unknown")
            status = change.get("status", "unknown")
            
            summary["by_operation"][operation] = summary["by_operation"].get(operation, 0) + 1
            summary["by_entity_type"][entity_type] = summary["by_entity_type"].get(entity_type, 0) + 1
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
        
        # Get recent session summaries
        cutoff_time = datetime.now(timezone.utc).timestamp() - (hours * 3600)
        for session_file in sorted(self.output_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            if session_file.stat().st_mtime < cutoff_time:
                continue
                
            try:
                with open(session_file, 'r') as f:
                    session_data = json.load(f)
                    
                summary["recent_sessions"].append({
                    "session_id": session_data["session_id"],
                    "sync_type": session_data["sync_type"],
                    "start_time": session_data["summary"]["start_time"],
                    "duration_seconds": session_data["summary"]["duration_seconds"],
                    "total_processed": session_data["summary"]["total_processed"],
                    "total_created": session_data["summary"]["total_created"],
                    "total_updated": session_data["summary"]["total_updated"],
                    "total_errors": session_data["summary"]["total_errors"]
                })
                
            except Exception as e:
                logger.error(f"Error reading session file {session_file}: {e}")
        
        return summary 