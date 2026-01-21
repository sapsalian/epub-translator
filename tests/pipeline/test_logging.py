"""Tests for logging configuration."""

import logging
import tempfile
from pathlib import Path

import pytest

from src.pipeline.logging import setup_logging, get_logger


class TestSetupLogging:
    """Tests for setup_logging()."""

    def teardown_method(self):
        """Clean up loggers after each test."""
        root_logger = logging.getLogger("src")
        root_logger.handlers.clear()
        root_logger.setLevel(logging.WARNING)

    def test_default_setup(self):
        """Default setup configures INFO level."""
        setup_logging()

        logger = logging.getLogger("src.pipeline.test")
        assert logger.getEffectiveLevel() == logging.INFO

    def test_custom_level(self):
        """Custom level is applied."""
        setup_logging(level="DEBUG")

        logger = logging.getLogger("src.pipeline.test")
        assert logger.getEffectiveLevel() == logging.DEBUG

    def test_file_logging(self):
        """Log file is created and written to."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            setup_logging(level="INFO", log_file=log_file)

            logger = logging.getLogger("src.pipeline.test")
            logger.info("Test message")

            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content

    def test_file_logging_creates_parent_dirs(self):
        """Parent directories are created for log file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "subdir" / "nested" / "test.log"
            setup_logging(log_file=log_file)

            logger = logging.getLogger("src.pipeline.test")
            logger.info("Test")

            assert log_file.exists()

    def test_repeated_setup_clears_handlers(self):
        """Repeated setup doesn't create duplicate handlers."""
        setup_logging()
        setup_logging()
        setup_logging()

        root_logger = logging.getLogger("src")
        # Should have exactly 1 handler (console only)
        assert len(root_logger.handlers) == 1

    def test_log_format_includes_components(self):
        """Log format includes timestamp, level, name, message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            setup_logging(level="INFO", log_file=log_file)

            logger = logging.getLogger("src.pipeline.mymodule")
            logger.warning("Something happened")

            content = log_file.read_text()
            assert "WARNING" in content
            assert "src.pipeline.mymodule" in content
            assert "Something happened" in content


class TestGetLogger:
    """Tests for get_logger()."""

    def test_returns_logger(self):
        """Returns a logger instance."""
        logger = get_logger("src.pipeline.test")
        assert isinstance(logger, logging.Logger)

    def test_same_as_getLogger(self):
        """Returns same logger as logging.getLogger()."""
        logger1 = get_logger("src.pipeline.test")
        logger2 = logging.getLogger("src.pipeline.test")
        assert logger1 is logger2
