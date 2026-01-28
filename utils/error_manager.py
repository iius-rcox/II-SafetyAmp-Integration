"""Error management module for SafetyAmp integration."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorManager:
    """Manages error tracking and reporting for the SafetyAmp integration."""

    def __init__(self):
        self.errors = []
        self.last_error_time = None

    def log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Log an error with optional context."""
        error_info = {
            "timestamp": datetime.utcnow().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {},
        }
        self.errors.append(error_info)
        self.last_error_time = datetime.utcnow()

        logger.error(
            f"Error occurred: {error_info['error_type']} - {error_info['error_message']}",
            extra={"context": context},
        )

    def get_recent_errors(self, limit: int = 10):
        """Get the most recent errors."""
        return self.errors[-limit:] if self.errors else []

    def clear_errors(self):
        """Clear the error history."""
        self.errors = []
        self.last_error_time = None

    def has_recent_errors(self, seconds: int = 300) -> bool:
        """Check if there have been errors in the last N seconds."""
        if not self.last_error_time:
            return False

        time_diff = (datetime.utcnow() - self.last_error_time).total_seconds()
        return time_diff <= seconds


# Global error manager instance
error_manager = ErrorManager()
