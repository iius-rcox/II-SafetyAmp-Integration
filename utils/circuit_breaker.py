import time
import requests
from circuitbreaker import circuit
from utils.logger import get_logger

logger = get_logger("circuit_breaker")

class RateLimitError(Exception):
    """Custom exception for rate limit errors"""
    pass

class TemporaryAPIError(Exception):
    """Custom exception for temporary API errors"""
    pass

@circuit(failure_threshold=5, recovery_timeout=300, expected_exception=requests.HTTPError)
def sync_with_circuit_breaker(sync_function):
    """Wrap sync operations with circuit breaker"""
    try:
        return sync_function()
    except requests.HTTPError as e:
        if e.response and e.response.status_code == 429:
            # Rate limit hit - wait and retry
            retry_after = int(e.response.headers.get('Retry-After', 60))
            logger.warning(f"Rate limit hit, backing off for {retry_after} seconds")
            time.sleep(retry_after)
            raise RateLimitError(f"Rate limit exceeded, retry after {retry_after}s")
        else:
            # Other HTTP error - fail fast
            logger.error(f"HTTP error: {e}")
            raise
    except Exception as e:
        logger.error(f"Unexpected error in sync operation: {e}")
        raise

class SmartRateLimiter:
    """Smart rate limiting based on API type and adaptive behavior"""
    
    def __init__(self, api_type):
        if api_type == "samsara":
            self.calls_per_second = 20  # Buffer below 25/sec limit
            self.burst_limit = 50       # Handle bursts
        elif api_type == "safetyamp":
            self.calls_per_second = 1   # Conservative 60/minute
            self.burst_limit = 5        # Small bursts
        
        self.adaptive = True  # Slow down on 429 errors
        self._current_limit = self.calls_per_second
        self._last_429_time = 0
        
    def status(self):
        """Return current rate limiter status"""
        return {
            "current_limit": self._current_limit,
            "base_limit": self.calls_per_second,
            "burst_limit": self.burst_limit,
            "adaptive": self.adaptive,
            "last_429": self._last_429_time
        }
    
    def on_429_error(self):
        """Called when a 429 error occurs to adapt the rate limit"""
        if self.adaptive:
            self._current_limit = max(1, self._current_limit * 0.5)
            self._last_429_time = time.time()
            logger.warning(f"Adapting rate limit to {self._current_limit} calls/second due to 429 error")
    
    def reset_if_recovered(self):
        """Reset rate limit if enough time has passed since last 429"""
        if time.time() - self._last_429_time > 300:  # 5 minutes
            self._current_limit = self.calls_per_second