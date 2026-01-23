"""API clients for LLM interactions."""

from .base import (
    ChunkExtraction,
    LLMClient,
    MergedExtraction,
    PreprocessClient,
    TranslationClient,
)
from .openai_client import OpenAIClient
from .retry import (
    RateLimitError,
    RetryableError,
    RetryConfig,
    TransientAPIError,
    with_retry,
)

__all__ = [
    # Protocols
    "LLMClient",
    "PreprocessClient",
    "TranslationClient",
    # Data classes
    "ChunkExtraction",
    "MergedExtraction",
    # Implementations
    "OpenAIClient",
    # Retry utilities
    "RetryConfig",
    "RetryableError",
    "RateLimitError",
    "TransientAPIError",
    "with_retry",
]
