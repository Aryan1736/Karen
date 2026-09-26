"""
Karen's Ear — Logging Configuration
Configures application-wide logging levels and formatting from LOG_LEVEL setting.
"""
from __future__ import annotations

import logging
from typing import Optional

from .config import settings


def configure_logging(level: Optional[str] = None) -> None:
    """
    Configure application logging based on LOG_LEVEL setting.
    Ensures root and 'karen' namespace loggers adhere to the specified level.
    Preserves diagnostic clarity and request tracing without exposing secrets.
    """
    log_level_str = level or settings.LOG_LEVEL
    numeric_level = getattr(logging, log_level_str.upper(), logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    )
    logging.getLogger("karen").setLevel(numeric_level)
