"""Tests for worker base classes."""

import asyncio

import pytest

from src.pipeline.workers.base import (
    Worker,
    AsyncWorker,
    WorkerError,
    ExtractionError,
    PreprocessError,
    TranslationError,
    InsertionError,
)


# =============================================================================
# Concrete implementations for testing
# =============================================================================


class ConcreteWorker(Worker[str, int]):
    """Concrete worker for testing."""

    def process(self, input_data: str) -> int:
        return len(input_data)


class ConcreteAsyncWorker(AsyncWorker[str, int]):
    """Concrete async worker for testing."""

    async def process(self, input_data: str) -> int:
        return len(input_data)


class FailingWorker(Worker[str, int]):
    """Worker that always fails."""

    def process(self, input_data: str) -> int:
        raise WorkerError("Processing failed")


class FailingAsyncWorker(AsyncWorker[str, int]):
    """Async worker that always fails."""

    async def process(self, input_data: str) -> int:
        raise WorkerError("Processing failed")


# =============================================================================
# Tests
# =============================================================================


class TestWorker:
    """Tests for synchronous Worker."""

    def test_process(self):
        """Worker.process() works correctly."""
        worker = ConcreteWorker()
        result = worker.process("hello")
        assert result == 5

    def test_has_logger(self):
        """Worker has a logger attribute."""
        worker = ConcreteWorker()
        assert hasattr(worker, "logger")
        assert worker.logger.name == "tests.pipeline.workers.test_base"

    def test_repr(self):
        """Worker has a readable repr."""
        worker = ConcreteWorker()
        assert repr(worker) == "ConcreteWorker()"

    def test_error_propagation(self):
        """Errors from process() propagate correctly."""
        worker = FailingWorker()
        with pytest.raises(WorkerError, match="Processing failed"):
            worker.process("test")


class TestAsyncWorker:
    """Tests for asynchronous AsyncWorker."""

    def test_process(self):
        """AsyncWorker.process() works correctly."""
        worker = ConcreteAsyncWorker()
        result = asyncio.run(worker.process("hello world"))
        assert result == 11

    def test_has_logger(self):
        """AsyncWorker has a logger attribute."""
        worker = ConcreteAsyncWorker()
        assert hasattr(worker, "logger")
        assert worker.logger.name == "tests.pipeline.workers.test_base"

    def test_repr(self):
        """AsyncWorker has a readable repr."""
        worker = ConcreteAsyncWorker()
        assert repr(worker) == "ConcreteAsyncWorker()"

    def test_error_propagation(self):
        """Errors from async process() propagate correctly."""
        worker = FailingAsyncWorker()
        with pytest.raises(WorkerError, match="Processing failed"):
            asyncio.run(worker.process("test"))


class TestExceptions:
    """Tests for worker exceptions."""

    def test_worker_error_is_exception(self):
        """WorkerError is an Exception."""
        assert issubclass(WorkerError, Exception)

    def test_extraction_error_is_worker_error(self):
        """ExtractionError inherits from WorkerError."""
        assert issubclass(ExtractionError, WorkerError)

    def test_preprocess_error_is_worker_error(self):
        """PreprocessError inherits from WorkerError."""
        assert issubclass(PreprocessError, WorkerError)

    def test_translation_error_is_worker_error(self):
        """TranslationError inherits from WorkerError."""
        assert issubclass(TranslationError, WorkerError)

    def test_insertion_error_is_worker_error(self):
        """InsertionError inherits from WorkerError."""
        assert issubclass(InsertionError, WorkerError)

    def test_exceptions_can_have_messages(self):
        """All exceptions can carry error messages."""
        errors = [
            WorkerError("base error"),
            ExtractionError("extraction failed"),
            PreprocessError("preprocess failed"),
            TranslationError("translation failed"),
            InsertionError("insertion failed"),
        ]

        for error in errors:
            assert str(error) in [
                "base error",
                "extraction failed",
                "preprocess failed",
                "translation failed",
                "insertion failed",
            ]
