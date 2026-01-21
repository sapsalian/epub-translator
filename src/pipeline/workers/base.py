"""
Abstract base classes for pipeline workers.

Workers are the processing units of the translation pipeline.
Each worker handles a specific stage: extraction, preprocessing, translation, or insertion.

Two types of workers:
- Worker: Synchronous, for CPU-bound tasks (extraction, insertion)
- AsyncWorker: Asynchronous, for IO-bound tasks (API calls, translation)

Usage:
    class MyWorker(Worker[InputModel, OutputModel]):
        def process(self, input_data: InputModel) -> OutputModel:
            # Processing logic
            return result

    class MyAsyncWorker(AsyncWorker[InputModel, OutputModel]):
        async def process(self, input_data: InputModel) -> OutputModel:
            # Async processing logic
            return result
"""

import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

# Type variables for input and output types
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")


# =============================================================================
# Synchronous Worker
# =============================================================================


class Worker(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for synchronous workers.

    Use for CPU-bound tasks like:
    - EPUB parsing and extraction
    - XML manipulation and insertion
    - Text processing

    Subclasses must implement the process() method.
    """

    def __init__(self) -> None:
        """Initialize worker with a logger."""
        self.logger = logging.getLogger(self.__class__.__module__)

    @abstractmethod
    def process(self, input_data: InputT) -> OutputT:
        """
        Process input data and return output.

        Args:
            input_data: The input data to process.

        Returns:
            Processed output data.

        Raises:
            WorkerError: If processing fails.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# =============================================================================
# Asynchronous Worker
# =============================================================================


class AsyncWorker(ABC, Generic[InputT, OutputT]):
    """
    Abstract base class for asynchronous workers.

    Use for IO-bound tasks like:
    - API calls (translation, summarization)
    - Database operations
    - Network requests

    Subclasses must implement the async process() method.
    """

    def __init__(self) -> None:
        """Initialize worker with a logger."""
        self.logger = logging.getLogger(self.__class__.__module__)

    @abstractmethod
    async def process(self, input_data: InputT) -> OutputT:
        """
        Process input data asynchronously and return output.

        Args:
            input_data: The input data to process.

        Returns:
            Processed output data.

        Raises:
            WorkerError: If processing fails.
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# =============================================================================
# Exceptions
# =============================================================================


class WorkerError(Exception):
    """Base exception for worker errors."""

    pass


class ExtractionError(WorkerError):
    """Error during extraction phase."""

    pass


class PreprocessError(WorkerError):
    """Error during preprocessing phase."""

    pass


class TranslationError(WorkerError):
    """Error during translation phase."""

    pass


class InsertionError(WorkerError):
    """Error during insertion phase."""

    pass
