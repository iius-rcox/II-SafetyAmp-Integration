#!/usr/bin/env python3
"""
Error Notification System

This module provides comprehensive error tracking and hourly email notifications
for SafetyAmp integration errors.
"""

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from utils.logger import get_logger
from utils.emailer import send_error_email
from utils.metrics import get_or_create_counter

logger = get_logger("error_notifier")

_errors_counter = metrics.errors_total

class ErrorNotifier:
    """Manages error collection and hourly email notifications"""
    
    def __init__(self, data_dir: str = "output/errors"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Error storage
        self.errors_file = self.data_dir / "error_log.json"
        self.last_notification_file = self.data_dir / "last_notification.json"
        
        # Initialize error storage
        self._load_errors()
        
    def _load_errors(self):
        """Load existing errors from file"""
        if self.errors_file.exists():
            try:
                with open(self.errors_file, 'r') as f:
                    self.errors = json.load(f)
            except Exception as e:
                logger.error(f"Error loading error log: {e}")
                self.errors = []
        else:
            self.errors = []
    
    def _save_errors(self):
        """Save errors to file"""
        try:
            with open(self.errors_file, 'w') as f:
                json.dump(self.errors, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving error log: {e}")
    
    def log_error(self, error_type: str, entity_type: str, entity_id: str, 
                  error_message: str, error_details: Optional[Dict[str, Any]] = None,
                  source: str = "sync"):
        """Log an error for notification"""
        error_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "error_message": error_message,
            "error_details": error_details or {},
            "source": source
        }
        
        self.errors.append(error_record)
        self._save_errors()
        
        logger.info(f"Logged error: {error_type} for {entity_type} {entity_id}")
        # Increment Prometheus error counter (low cardinality)
        try:
            _errors_counter.labels(error_type=error_type, entity_type=entity_type, source=source).inc()
        except Exception:
            pass
    
    def get_errors_since(self, hours: int = 1) -> List[Dict[str, Any]]:
        """Get errors from the last N hours"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        cutoff_timestamp = cutoff_time.isoformat()
        
        return [
            error for error in self.errors
            if error["timestamp"] >= cutoff_timestamp
        ]
    
    def get_error_summary(self, hours: int = 1) -> Dict[str, Any]:
        """Get a summary of errors from the last N hours"""
        recent_errors = self.get_errors_since(hours)
        
        if not recent_errors:
            return {
                "period_hours": hours,
                "total_errors": 0,
                "error_types": {},
                "entity_types": {},
                "sources": {},
                "errors": []
            }
        
        summary = {
            "period_hours": hours,
            "total_errors": len(recent_errors),
            "error_types": defaultdict(int),
            "entity_types": defaultdict(int),
            "sources": defaultdict(int),
            "errors": recent_errors
        }
        
        for error in recent_errors:
            summary["error_types"][error["error_type"]] += 1
            summary["entity_types"][error["entity_type"]] += 1
            summary["sources"][error["source"]] += 1
        
        # Convert defaultdict to regular dict
        summary["error_types"] = dict(summary["error_types"])
        summary["entity_types"] = dict(summary["entity_types"])
        summary["sources"] = dict(summary["sources"])
        
        return summary
    
    def should_send_notification(self) -> bool:
        """Check if it's time to send a notification (hourly)"""
        if not self.last_notification_file.exists():
            return True
        
        try:
            with open(self.last_notification_file, 'r') as f:
                last_notification = json.load(f)
                last_time = datetime.fromisoformat(last_notification["timestamp"])
                time_since_last = datetime.now(timezone.utc) - last_time
                return time_since_last >= timedelta(hours=1)
        except Exception as e:
            logger.error(f"Error checking last notification time: {e}")
            return True
    
    def mark_notification_sent(self):
        """Mark that a notification was sent"""
        notification_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sent": True
        }
        
        try:
            with open(self.last_notification_file, 'w') as f:
                json.dump(notification_record, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving notification record: {e}")
    
    def format_error_email(self, summary: Dict[str, Any]) -> tuple[str, str]:
        """Format error summary into email subject and body"""
        subject = f"SafetyAmp Integration Error Report - {summary['total_errors']} errors in last hour"
        
        body = f"""
SafetyAmp Integration Error Report
==================================
Period: Last {summary['period_hours']} hour(s)
Total Errors: {summary['total_errors']}
Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

ERROR BREAKDOWN:
"""
        
        if summary["error_types"]:
            body += "\nError Types:\n"
            for error_type, count in summary["error_types"].items():
                body += f"  - {error_type}: {count}\n"
        
        if summary["entity_types"]:
            body += "\nEntity Types:\n"
            for entity_type, count in summary["entity_types"].items():
                body += f"  - {entity_type}: {count}\n"
        
        if summary["sources"]:
            body += "\nSources:\n"
            for source, count in summary["sources"].items():
                body += f"  - {source}: {count}\n"
        
        if summary["errors"]:
            body += "\nDETAILED ERROR LIST:\n"
            body += "=" * 50 + "\n"
            
            for i, error in enumerate(summary["errors"][:20], 1):  # Limit to first 20 errors
                timestamp = datetime.fromisoformat(error["timestamp"]).strftime("%H:%M:%S")
                body += f"\n{i}. [{timestamp}] {error['error_type']} - {error['entity_type']} {error['entity_id']}\n"
                body += f"   Message: {error['error_message']}\n"
                body += f"   Source: {error['source']}\n"
                
                if error.get("error_details"):
                    body += f"   Details: {json.dumps(error['error_details'], indent=2)}\n"
            
            if len(summary["errors"]) > 20:
                body += f"\n... and {len(summary['errors']) - 20} more errors\n"
        
        body += f"""

This is an automated error report from the SafetyAmp Integration system.
For more details, check the application logs and change tracking reports.
"""
        
        return subject, body
    
    def send_hourly_notification(self) -> bool:
        """Send hourly error notification if needed"""
        if not self.should_send_notification():
            return False
        
        summary = self.get_error_summary(hours=1)
        
        if summary["total_errors"] == 0:
            logger.info("No errors in the last hour, skipping notification")
            return False
        
        try:
            subject, body = self.format_error_email(summary)
            send_error_email(subject, body)
            self.mark_notification_sent()
            
            logger.info(f"Sent hourly error notification with {summary['total_errors']} errors")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send hourly error notification: {e}")
            return False
    
    def cleanup_old_errors(self, days: int = 7):
        """Clean up errors older than N days"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_timestamp = cutoff_time.isoformat()
        
        original_count = len(self.errors)
        self.errors = [
            error for error in self.errors
            if error["timestamp"] >= cutoff_timestamp
        ]
        
        removed_count = original_count - len(self.errors)
        if removed_count > 0:
            self._save_errors()
            logger.info(f"Cleaned up {removed_count} old error records (older than {days} days)")
    
    def get_notification_status(self) -> Dict[str, Any]:
        """Get current notification status"""
        summary = self.get_error_summary(hours=1)
        
        return {
            "total_errors_last_hour": summary["total_errors"],
            "should_send_notification": self.should_send_notification(),
            "last_notification_sent": self._get_last_notification_time(),
            "error_breakdown": summary["error_types"],
            "entity_breakdown": summary["entity_types"]
        }
    
    def _get_last_notification_time(self) -> Optional[str]:
        """Get the timestamp of the last notification"""
        if not self.last_notification_file.exists():
            return None
        
        try:
            with open(self.last_notification_file, 'r') as f:
                data = json.load(f)
                return data.get("timestamp")
        except Exception as e:
            logger.error(f"Error reading last notification time: {e}")
            return None

# Global instance
error_notifier = ErrorNotifier()
