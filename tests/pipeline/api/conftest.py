"""Shared fixtures for API tests."""

import os
from pathlib import Path

import pytest

from src.pipeline.api.openai_client import OpenAIClient
from src.pipeline.api.retry import RetryConfig


def _load_env() -> None:
    """Load .env file into os.environ (no python-dotenv dependency)."""
    env_path = Path(__file__).parents[3] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env()

_has_api_key = bool(os.environ.get("OPENAI_API_KEY"))


live = pytest.mark.live
skip_without_key = pytest.mark.skipif(
    not _has_api_key, reason="OPENAI_API_KEY not set"
)


@pytest.fixture
def live_client():
    """Real OpenAI client using gpt-4.1-nano for minimal cost."""
    return OpenAIClient(
        model="gpt-4.1-nano",
        retry_config=RetryConfig(max_retries=0),
    )
