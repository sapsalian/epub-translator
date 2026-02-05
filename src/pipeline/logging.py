"""
Logging configuration for the translation pipeline.

Usage:
    # At application entry point (once)
    from src.pipeline.logging import setup_logging
    setup_logging(level="INFO", log_file="translation.log")

    # In each module (no change needed)
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Processing...")
"""

import logging
import sys
from pathlib import Path


# =============================================================================
# Constants
# =============================================================================

DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# =============================================================================
# Setup Function
# =============================================================================

def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
    format_string: str = DEFAULT_FORMAT,
    date_format: str = DEFAULT_DATE_FORMAT,
) -> None:
    """
    Configure logging for the entire application.

    Call this once at the application entry point.
    Each module uses `logging.getLogger(__name__)` as usual.

    Args:
        level: Log level ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        log_file: Optional file path for log output. If None, logs to stderr only.
        format_string: Log message format.
        date_format: Timestamp format.

    Example:
        >>> setup_logging(level="DEBUG", log_file="app.log")
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create formatter
    formatter = logging.Formatter(format_string, datefmt=date_format)

    # Get root logger for our package
    root_logger = logging.getLogger("src")
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates on repeated calls
    root_logger.handlers.clear()

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(file_path, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    # Prevent propagation to root logger (avoids duplicate logs)
    root_logger.propagate = False

    # Silence noisy third-party loggers by default
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.

    This is a convenience wrapper around logging.getLogger().
    Modules can use either this or logging.getLogger(__name__) directly.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
