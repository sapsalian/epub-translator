"""
Retry utilities with exponential backoff.

Provides decorators and utilities for handling transient API failures
with configurable retry behavior.
"""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ) -> None:
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts.
            base_delay: Initial delay in seconds.
            max_delay: Maximum delay in seconds.
            exponential_base: Base for exponential backoff.
            jitter: Whether to add random jitter to delays.
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for a given attempt number.

        Args:
            attempt: Current attempt number (0-indexed).

        Returns:
            Delay in seconds.
        """
        delay = self.base_delay * (self.exponential_base**attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            delay = delay * (0.5 + random.random())

        return delay


class RetryableError(Exception):
    """Base exception for errors that should trigger a retry."""

    pass


class RateLimitError(RetryableError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message: str = "", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class TransientAPIError(RetryableError):
    """Raised for transient API errors (5xx, timeouts, etc.)."""

    pass


def with_retry(
    config: RetryConfig | None = None,
    retryable_exceptions: tuple[type[Exception], ...] = (RetryableError,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration. Uses defaults if not provided.
        retryable_exceptions: Exception types that should trigger a retry.

    Returns:
        Decorated function with retry logic.

    Example:
        @with_retry(RetryConfig(max_retries=3))
        async def call_api():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception: Exception | None = None
            error_retries = 0

            while True:
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    is_rate_limit = isinstance(e, RateLimitError)

                    if not is_rate_limit:
                        error_retries += 1
                        if error_retries > config.max_retries:
                            logger.error(
                                "All %d attempts failed. Last error: %s",
                                error_retries,
                                str(e),
                            )
                            break

                    if is_rate_limit and e.retry_after is not None:
                        delay = e.retry_after + random.uniform(0.5, 2.0)
                        delay = min(delay, config.max_delay)
                    else:
                        delay = config.calculate_delay(error_retries)

                    logger.warning(
                        "%s: %s. Retrying in %.2fs...",
                        "Rate limited"
                        if is_rate_limit
                        else f"Attempt {error_retries}/{config.max_retries}",
                        str(e),
                        delay,
                    )
                    await asyncio.sleep(delay)

            raise last_exception  # type: ignore[misc]

        return wrapper

    return decorator
