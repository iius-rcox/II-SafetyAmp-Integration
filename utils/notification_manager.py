import time
import json
from collections import defaultdict
from utils.logger import get_logger
from utils.circuit_breaker import RateLimitError, TemporaryAPIError

logger = get_logger("notification_manager")


class NotificationManager:
    """Manages notifications for sync failures with intelligent alerting"""

    def __init__(self):
        self.failure_counts = defaultdict(int)
        self.last_alert_time = defaultdict(float)
        self.alert_cooldown = 300  # 5 minutes between alerts for same issue

    def handle_sync_failure(self, error, sync_type):
        """Handle sync failure with appropriate notification strategy"""
        if isinstance(error, RateLimitError):
            # Rate limits are expected - log but don't alert
            logger.info(f"Rate limit encountered for {sync_type} - will retry")
            return

        if isinstance(error, TemporaryAPIError):
            # Temporary errors - notify after multiple failures
            failure_count = self._increment_failure_count(sync_type)
            if failure_count > 3:
                self._send_alert(f"Multiple {sync_type} sync failures", error)
        else:
            # Critical errors - immediate notification
            self._send_alert(f"Critical {sync_type} sync failure", error)

    def _increment_failure_count(self, sync_type):
        """Increment and return failure count for sync type"""
        self.failure_counts[sync_type] += 1
        return self.failure_counts[sync_type]

    def reset_failure_count(self, sync_type):
        """Reset failure count on successful sync"""
        if sync_type in self.failure_counts:
            del self.failure_counts[sync_type]

    def _send_alert(self, title, error):
        """Send alert if not in cooldown period"""
        error_key = f"{title}_{type(error).__name__}"
        current_time = time.time()

        if current_time - self.last_alert_time[error_key] > self.alert_cooldown:
            self._dispatch_alert(title, error)
            self.last_alert_time[error_key] = current_time

    def _dispatch_alert(self, title, error):
        """Dispatch alert through configured channels"""
        # For now, just log the alert
        # In production, this would integrate with Slack, Teams, email, etc.
        alert_data = {
            "title": title,
            "error": str(error),
            "timestamp": time.time(),
            "severity": (
                "critical"
                if not isinstance(error, (RateLimitError, TemporaryAPIError))
                else "warning"
            ),
        }

        logger.error(f"ALERT: {title}", extra={"alert_data": alert_data})

        # Future integration points:
        # - Send to Azure Monitor
        # - Send to Slack webhook
        # - Send email via SendGrid
        # - Create incident in PagerDuty
