"""Structured logging helper.

Usage:
    from src.utils.logging import get_logger
    log = get_logger(__name__)
    log.info("Fetched %d rows", n)
"""

from __future__ import annotations

import logging
import sys
import time

from src.utils.config import LOG_LEVEL


def get_logger(name: str) -> logging.Logger:
    """Return a logger with consistent formatting."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )
        logger.addHandler(handler)
        handler.formatter.converter = time.gmtime
    logger.propagate = False
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    return logger
