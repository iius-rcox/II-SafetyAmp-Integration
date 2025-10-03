import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from config import settings

# Get absolute project root (where .env lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for extra_key in ("sync_type", "session_id", "operation", "entity_type", "error_type", "metrics", "duration_seconds"):
            if hasattr(record, extra_key):
                payload[extra_key] = getattr(record, extra_key)
        return json.dumps(payload, separators=(",", ":"))


def get_logger(name: str) -> logging.Logger:
    log_file = PROJECT_ROOT / "output" / "logs" / "safetyamp_sync.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Prevent re-adding handlers

    logger.setLevel(settings.LOG_LEVEL.upper())

    text_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    json_formatter = _JsonFormatter()

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(text_formatter if not settings.STRUCTURED_LOGGING_ENABLED else json_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(text_formatter if not settings.STRUCTURED_LOGGING_ENABLED else json_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger