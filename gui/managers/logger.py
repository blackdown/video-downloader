"""
Logging configuration for the GUI.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logging(log_file: str = "video_dl_gui.log") -> logging.Logger:
    """
    Set up logging to both file and a list buffer for GUI display.

    Returns the configured logger.
    """
    logger = logging.getLogger("video_dl_gui")
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    logger.handlers.clear()

    # File handler - detailed logging
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Console handler for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter("%(levelname)s: %(message)s")
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # Log startup
    logger.info(f"=== Video Downloader GUI started at {datetime.now().isoformat()} ===")

    return logger


# Global logger instance
_logger = None


def get_logger() -> logging.Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger
