import logging.config
import logging.handlers
import sys
import os
from pathlib import Path

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    FORMATS = {
        logging.DEBUG: grey + "%(levelname)s: %(message)s" + reset,
        logging.INFO: green + "%(levelname)s: %(message)s" + reset,
        logging.WARNING: yellow + "%(levelname)s: %(message)s" + reset,
        logging.ERROR: red + "%(levelname)s: %(message)s" + reset,
        logging.CRITICAL: bold_red + "%(levelname)s: %(message)s" + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "colored": {
            "()": ColoredFormatter,
        },
        "file": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colored",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "formatter": "file",
            "filename": os.path.abspath("logs/app.log"),
            "when": "midnight",
            "interval": 1,
            "backupCount": 30,  # Keep logs for 30 days
            "encoding": "utf-8",
        }
    },
    "loggers": {
        # Third-party libraries that we want to suppress a bit
        "langchain_aws": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False
        },
        "boto3": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False
        },
        "botocore": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False
        }
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    }
}

def setup_logging():
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.config.dictConfig(LOGGING_CONFIG)

    # Test that logging is working
    logger = logging.getLogger(__name__)
    logger.info("Logging initialized successfully")
