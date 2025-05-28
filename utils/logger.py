import logging
from pathlib import Path
from config import settings

# Get absolute project root (where .env lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

def get_logger(name: str) -> logging.Logger:
    log_file = PROJECT_ROOT / "output" / "logs" / "safetyamp_sync.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger  # Prevent re-adding handlers

    logger.setLevel(settings.LOG_LEVEL.upper())

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger