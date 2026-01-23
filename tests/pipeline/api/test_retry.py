"""Tests for retry utilities."""

import asyncio

import pytest

from src.pipeline.api.retry import (
    RateLimitError,
    RetryableError,
    RetryConfig,
    TransientAPIError,
    with_retry,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_config(self):
        """Default config has sensible values."""
        config = RetryConfig()

        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True

    def test_custom_config(self):
        """Custom config values are stored."""
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=3.0,
            jitter=False,
        )

        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_calculate_delay_exponential(self):
        """Delay increases exponentially."""
        config = RetryConfig(base_delay=1.0, exponential_base=2.0, jitter=False)

        assert config.calculate_delay(0) == 1.0
        assert config.calculate_delay(1) == 2.0
        assert config.calculate_delay(2) == 4.0
        assert config.calculate_delay(3) == 8.0

    def test_calculate_delay_max_cap(self):
        """Delay is capped at max_delay."""
        config = RetryConfig(base_delay=1.0, max_delay=5.0, jitter=False)

        assert config.calculate_delay(10) == 5.0

    def test_calculate_delay_with_jitter(self):
        """Jitter adds randomness to delay."""
        config = RetryConfig(base_delay=1.0, jitter=True)

        delays = [config.calculate_delay(0) for _ in range(10)]

        # All delays should be different (with high probability)
        assert len(set(delays)) > 1
        # All delays should be in range [0.5, 1.5] for attempt 0
        assert all(0.5 <= d <= 1.5 for d in delays)


class TestRetryableErrors:
    """Tests for retryable error classes."""

    def test_retryable_error_hierarchy(self):
        """Error classes have correct hierarchy."""
        assert issubclass(RateLimitError, RetryableError)
        assert issubclass(TransientAPIError, RetryableError)
        assert issubclass(RetryableError, Exception)


class TestWithRetry:
    """Tests for with_retry decorator."""

    def test_success_no_retry(self):
        """Successful call doesn't retry."""
        call_count = 0

        @with_retry()
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = asyncio.run(success_func())

        assert result == "success"
        assert call_count == 1

    def test_retry_on_retryable_error(self):
        """Retries on RetryableError."""
        call_count = 0
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)

        @with_retry(config)
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("temporary failure")
            return "success"

        result = asyncio.run(fail_then_succeed())

        assert result == "success"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Raises after max retries exceeded."""
        call_count = 0
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)

        @with_retry(config)
        async def always_fail():
            nonlocal call_count
            call_count += 1
            raise RetryableError("always fails")

        with pytest.raises(RetryableError, match="always fails"):
            asyncio.run(always_fail())

        assert call_count == 3  # 1 initial + 2 retries

    def test_no_retry_on_non_retryable_error(self):
        """Doesn't retry on non-retryable errors."""
        call_count = 0
        config = RetryConfig(max_retries=2, base_delay=0.01)

        @with_retry(config)
        async def raise_value_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("not retryable")

        with pytest.raises(ValueError, match="not retryable"):
            asyncio.run(raise_value_error())

        assert call_count == 1  # No retries

    def test_custom_retryable_exceptions(self):
        """Custom retryable exceptions are honored."""
        call_count = 0
        config = RetryConfig(max_retries=2, base_delay=0.01, jitter=False)

        @with_retry(config, retryable_exceptions=(ValueError,))
        async def raise_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("retry this")
            return "success"

        result = asyncio.run(raise_value_error())

        assert result == "success"
        assert call_count == 2

    def test_rate_limit_error_is_retried(self):
        """RateLimitError triggers retry."""
        call_count = 0
        config = RetryConfig(max_retries=1, base_delay=0.01, jitter=False)

        @with_retry(config)
        async def rate_limited():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("rate limited")
            return "success"

        result = asyncio.run(rate_limited())

        assert result == "success"
        assert call_count == 2

    def test_transient_api_error_is_retried(self):
        """TransientAPIError triggers retry."""
        call_count = 0
        config = RetryConfig(max_retries=1, base_delay=0.01, jitter=False)

        @with_retry(config)
        async def transient_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise TransientAPIError("server error")
            return "success"

        result = asyncio.run(transient_error())

        assert result == "success"
        assert call_count == 2
