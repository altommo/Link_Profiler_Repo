"""
Logging Configuration - Centralized setup for application logging.
File: Link_Profiler/utils/logging_config.py
"""

import logging.config
import logging
import os
import json
from typing import Dict, Any

def setup_logging(config: Dict[str, Any]):
    """
    Sets up logging for the application using a dictionary configuration.
    
    Args:
        config: A dictionary containing the logging configuration.
                This typically comes from the config_loader.
    """
    try:
        logging.config.dictConfig(config)
        logging.info("Logging configured successfully.")
    except Exception as e:
        logging.basicConfig(level=logging.INFO) # Fallback to basic config
        logging.error(f"Failed to configure logging from dictionary: {e}", exc_info=True)
        logging.info("Using default basic logging configuration.")

def get_default_logging_config(log_level: str = "INFO") -> Dict[str, Any]:
    """
    Returns a default logging configuration dictionary.
    """
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
            "detailed": {
                "format": "%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": log_level
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "detailed",
                "filename": "link_profiler.log",
                "maxBytes": 10485760, # 10 MB
                "backupCount": 5,
                "level": log_level
            }
        },
        "loggers": {
            "Link_Profiler": { # Root logger for your application package
                "handlers": ["console", "file"],
                "level": log_level,
                "propagate": False
            },
            "uvicorn": { # Uvicorn access logs
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False
            },
            "uvicorn.access": { # Uvicorn access logs
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False
            },
            "sqlalchemy": { # SQLAlchemy logs
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False
            },
            "redis": { # Redis client logs
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False
            },
            "playwright": { # Playwright logs
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False
            },
            "pytrends": { # Pytrends logs
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False
            },
            "googleapiclient": { # Google API client logs
                "handlers": ["console"],
                "level": "WARNING",
                "propagate": False
            }
        },
        "root": { # Fallback for anything not caught by specific loggers
            "handlers": ["console"],
            "level": "WARNING"
        }
    }
