# Implementation Plan: SafetyAmp Integration System

## Phase 1: Critical Infrastructure (Week 1)

### 1.1 Create Dockerfile
```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose health check port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["python", "main.py"]
```

### 1.2 Implement Health Check Endpoints
```python
# main.py (Updated)
from flask import Flask, jsonify
from sync.sync_departments import DepartmentSyncer
from sync.sync_jobs import JobSyncer
from sync.sync_employees import EmployeeSyncer
from sync.sync_titles import TitleSyncer
import signal
import sys
import threading
import time

app = Flask(__name__)

# Global health status
health_status = {
    'healthy': True,
    'ready': False,
    'last_sync': None,
    'errors': []
}

@app.route('/health')
def health():
    """Liveness probe endpoint"""
    if health_status['healthy']:
        return jsonify({'status': 'healthy', 'timestamp': time.time()}), 200
    else:
        return jsonify({'status': 'unhealthy', 'errors': health_status['errors']}), 503

@app.route('/ready')
def ready():
    """Readiness probe endpoint"""
    if health_status['ready']:
        return jsonify({'status': 'ready', 'timestamp': time.time()}), 200
    else:
        return jsonify({'status': 'not ready'}), 503

@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    # Basic metrics - expand as needed
    return jsonify({
        'sync_operations_total': 0,
        'sync_errors_total': 0,
        'last_sync_duration_seconds': 0
    })

def run_sync_worker():
    """Background sync worker"""
    while health_status['healthy']:
        try:
            # Run sync operations
            ee_syncer = EmployeeSyncer()
            ee_syncer.sync()
            
            health_status['last_sync'] = time.time()
            health_status['ready'] = True
            
            # Sleep for sync interval
            time.sleep(3600)  # 1 hour
            
        except Exception as e:
            health_status['errors'].append(str(e))
            health_status['healthy'] = False
            break

def signal_handler(signum, frame):
    """Graceful shutdown handler"""
    print(f"Received signal {signum}, shutting down gracefully...")
    health_status['healthy'] = False
    sys.exit(0)

if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start sync worker in background
    sync_thread = threading.Thread(target=run_sync_worker, daemon=True)
    sync_thread.start()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=8080)
```

### 1.3 Update Requirements.txt
```txt
# requirements.txt (Updated)
# Core dependencies
requests>=2.31.0
python-dotenv>=1.0.0
Flask>=2.3.0
gunicorn>=21.0.0

# Database connectivity
pyodbc>=4.0.39

# Microsoft Graph API
msal>=1.24.0

# Rate limiting
ratelimit>=2.2.1

# Azure integration
azure-identity>=1.15.0
azure-keyvault-secrets>=4.7.0
azure-storage-blob>=12.19.0

# Redis for caching
redis>=5.0.0

# Monitoring
prometheus-client>=0.17.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0

# Development and linting
black>=23.0.0
flake8>=6.0.0
mypy>=1.5.0
```

## Phase 2: Security & Configuration (Week 2)

### 2.1 Azure Key Vault Integration
```python
# config/azure_key_vault.py
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import os

class AzureKeyVault:
    def __init__(self, vault_url=None):
        self.vault_url = vault_url or os.getenv('AZURE_KEY_VAULT_URL')
        if self.vault_url:
            self.credential = DefaultAzureCredential()
            self.client = SecretClient(vault_url=self.vault_url, credential=self.credential)
        else:
            self.client = None
    
    def get_secret(self, secret_name, default=None):
        """Get secret from Azure Key Vault or environment variable"""
        if self.client:
            try:
                return self.client.get_secret(secret_name).value
            except Exception:
                return os.getenv(secret_name, default)
        else:
            return os.getenv(secret_name, default)

# Update config/settings.py
from .azure_key_vault import AzureKeyVault

key_vault = AzureKeyVault()

# Update secret loading
SAFETYAMP_TOKEN = key_vault.get_secret("SAFETYAMP_TOKEN")
SAMSARA_API_KEY = key_vault.get_secret("SAMSARA_API_KEY")
MS_GRAPH_CLIENT_SECRET = key_vault.get_secret("MS_GRAPH_CLIENT_SECRET")
```

### 2.2 Redis Cache Implementation
```python
# utils/redis_cache_manager.py
import redis
import json
import time
from datetime import datetime, timedelta
from utils.logger import get_logger

logger = get_logger("redis_cache")

class RedisCacheManager:
    def __init__(self, host=None, port=6379, db=0):
        self.host = host or os.getenv('REDIS_HOST', 'localhost')
        self.port = port or int(os.getenv('REDIS_PORT', 6379))
        self.db = db
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish Redis connection"""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self.client.ping()
            logger.info(f"Connected to Redis at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None
    
    def get_cached_data(self, cache_name, fetch_function, max_age_hours=1, force_refresh=False):
        """Get cached data from Redis"""
        if not self.client:
            # Fallback to fetch function if Redis unavailable
            return fetch_function()
        
        cache_key = f"safetyamp:{cache_name}"
        
        try:
            if not force_refresh:
                # Try to get from cache
                cached_data = self.client.get(cache_key)
                if cached_data:
                    data = json.loads(cached_data)
                    logger.info(f"Using cached data for {cache_name}")
                    return data
            
            # Fetch fresh data
            logger.info(f"Fetching fresh data for {cache_name}")
            data = fetch_function()
            
            if data is not None:
                # Cache the data
                self.client.setex(
                    cache_key,
                    timedelta(hours=max_age_hours),
                    json.dumps(data, default=str)
                )
                logger.info(f"Cached {cache_name} with {len(data)} items")
            
            return data
            
        except Exception as e:
            logger.error(f"Redis cache error for {cache_name}: {e}")
            # Fallback to fetch function
            return fetch_function()
    
    def clear_cache(self, cache_name=None):
        """Clear cache entries"""
        if not self.client:
            return
        
        try:
            if cache_name:
                pattern = f"safetyamp:{cache_name}"
            else:
                pattern = "safetyamp:*"
            
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
```

### 2.3 Updated Kubernetes Secrets
```yaml
# k8s/safety-amp/safety-amp-deployment.yaml (Updated)
apiVersion: v1
kind: Secret
metadata:
  name: safety-amp-secrets
  namespace: safety-amp
type: Opaque
stringData:
  # These will be populated from Azure Key Vault
  AZURE_KEY_VAULT_URL: "https://your-keyvault.vault.azure.net/"
  REDIS_HOST: "redis-service"
  REDIS_PORT: "6379"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: safety-amp-config
  namespace: safety-amp
data:
  LOG_LEVEL: "INFO"
  ENVIRONMENT: "production"
  SYNC_INTERVAL: "3600"
  CACHE_TTL_HOURS: "1"
  API_RATE_LIMIT_CALLS: "60"
  API_RATE_LIMIT_PERIOD: "61"
  MAX_RETRY_ATTEMPTS: "3"
  RETRY_DELAY_SECONDS: "30"
```

## Phase 3: Error Handling & Resilience (Week 3)

### 3.1 Improved Error Handling
```python
# utils/exceptions.py
class SafetyAmpError(Exception):
    """Base exception for SafetyAmp integration"""
    pass

class APIError(SafetyAmpError):
    """API-related errors"""
    def __init__(self, message, status_code=None, response_text=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text

class CacheError(SafetyAmpError):
    """Cache-related errors"""
    pass

class DatabaseError(SafetyAmpError):
    """Database-related errors"""
    pass

# Updated error handling in services/safetyamp_api.py
def _handle_response(self, response, method: str, url: str):
    try:
        response.raise_for_status()
        data = response.json().get("data", [])
        logger.debug(f"{method} {url} succeeded")
        return data
    except requests.HTTPError as http_err:
        error_msg = f"{method} {url} HTTP error: {http_err}"
        if response.text:
            error_msg += f" - Response: {response.text}"
        logger.error(error_msg)
        raise APIError(error_msg, status_code=http_err.response.status_code, response_text=response.text)
    except ValueError as parse_err:
        error_msg = f"{method} {url} parse error: {parse_err}"
        logger.error(error_msg)
        raise APIError(error_msg)
    except Exception as err:
        error_msg = f"{method} {url} unexpected error: {err}"
        logger.error(error_msg)
        raise APIError(error_msg)
```

### 3.2 Circuit Breaker Implementation
```python
# utils/circuit_breaker.py
import time
from enum import Enum
from utils.logger import get_logger

logger = get_logger("circuit_breaker")

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=60, expected_exception=Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
```

## Phase 4: Monitoring & Observability (Week 4)

### 4.1 Prometheus Metrics
```python
# utils/metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
import time

# Metrics
sync_operations_total = Counter('sync_operations_total', 'Total sync operations', ['operation', 'status'])
sync_duration_seconds = Histogram('sync_duration_seconds', 'Sync operation duration', ['operation'])
api_requests_total = Counter('api_requests_total', 'Total API requests', ['service', 'endpoint', 'status'])
cache_hits_total = Counter('cache_hits_total', 'Total cache hits', ['cache_name'])
cache_misses_total = Counter('cache_misses_total', 'Total cache misses', ['cache_name'])

# Gauges
active_syncs = Gauge('active_syncs', 'Number of active sync operations')
last_sync_timestamp = Gauge('last_sync_timestamp', 'Timestamp of last successful sync')

class MetricsMiddleware:
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        start_time = time.time()
        
        def custom_start_response(status, headers, exc_info=None):
            duration = time.time() - start_time
            api_requests_total.labels(
                service='safetyamp',
                endpoint=environ.get('PATH_INFO', ''),
                status=status.split()[0]
            ).inc()
            return start_response(status, headers, exc_info)
        
        return self.app(environ, custom_start_response)

# Add to main.py
@app.route('/metrics')
def metrics():
    return generate_latest()
```

### 4.2 Structured Logging
```python
# utils/logger.py (Updated)
import logging
import json
import sys
from datetime import datetime

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        return json.dumps(log_entry)

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Console handler with structured logging
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredFormatter())
    logger.addHandler(console_handler)
    
    return logger
```

## Phase 5: Performance & Optimization (Week 5)

### 5.1 Connection Pooling
```python
# utils/connection_pool.py
import pyodbc
from contextlib import contextmanager
from utils.logger import get_logger

logger = get_logger("connection_pool")

class DatabaseConnectionPool:
    def __init__(self, connection_string, max_connections=10):
        self.connection_string = connection_string
        self.max_connections = max_connections
        self._pool = []
        self._lock = threading.Lock()
    
    @contextmanager
    def get_connection(self):
        connection = None
        try:
            with self._lock:
                if self._pool:
                    connection = self._pool.pop()
                else:
                    connection = pyodbc.connect(self.connection_string)
            
            yield connection
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            raise
        finally:
            if connection:
                try:
                    with self._lock:
                        if len(self._pool) < self.max_connections:
                            self._pool.append(connection)
                        else:
                            connection.close()
                except Exception:
                    connection.close()
```

### 5.2 Async Processing
```python
# sync/async_sync_manager.py
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from utils.logger import get_logger

logger = get_logger("async_sync")

class AsyncSyncManager:
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def sync_all(self):
        """Run all sync operations concurrently"""
        tasks = [
            self.sync_employees(),
            self.sync_vehicles(),
            self.sync_titles(),
            self.sync_jobs()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Sync operation {i} failed: {result}")
        
        return results
    
    async def sync_employees(self):
        """Async employee sync"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._sync_employees_sync)
    
    def _sync_employees_sync(self):
        """Synchronous employee sync"""
        syncer = EmployeeSyncer()
        return syncer.sync()
```

## Implementation Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Infrastructure | Dockerfile, Health Checks, Basic App Server |
| 2 | Security | Azure Key Vault, Redis Cache, Updated K8s Configs |
| 3 | Resilience | Error Handling, Circuit Breakers, Graceful Shutdown |
| 4 | Observability | Prometheus Metrics, Structured Logging, Monitoring |
| 5 | Performance | Connection Pooling, Async Processing, Optimization |

## Testing Strategy

1. **Unit Tests**: Test individual components
2. **Integration Tests**: Test API interactions
3. **End-to-End Tests**: Test complete sync workflows
4. **Load Tests**: Test performance under load
5. **Chaos Tests**: Test resilience to failures

## Deployment Strategy

1. **Blue-Green Deployment**: Zero-downtime deployments
2. **Canary Releases**: Gradual rollout with monitoring
3. **Rollback Plan**: Quick rollback to previous version
4. **Health Checks**: Automated health monitoring
5. **Alerting**: Proactive issue detection 