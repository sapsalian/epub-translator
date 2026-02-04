"""Tests for PipelineConfig."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.pipeline.config import PipelineConfig, ENV_PREFIX
from src.pipeline.models import Language


class TestPipelineConfig:
    """Tests for PipelineConfig."""

    def test_required_languages(self):
        """Languages are required fields."""
        config = PipelineConfig(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
        )
        assert config.source_language == Language.ENGLISH
        assert config.target_language == Language.KOREAN

    def test_default_values(self):
        """Default values are set correctly."""
        config = PipelineConfig(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
        )
        assert config.model == "gpt-4.1-mini"
        assert config.chunk_size == 4000
        assert config.batch_size == 4000
        assert config.preprocess_max_concurrent == 20
        assert config.translation_max_concurrent == 20
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.output_dir == Path("./output")
        assert config.checkpoint_dir == Path("./checkpoints")

    def test_custom_values(self):
        """Custom values can be provided."""
        config = PipelineConfig(
            source_language=Language.ENGLISH,
            target_language=Language.JAPANESE,
            model="gpt-4o",
            chunk_size=8000,
            batch_size=50,
            preprocess_max_concurrent=15,
            translation_max_concurrent=10,
            output_dir=Path("/custom/output"),
        )
        assert config.model == "gpt-4o"
        assert config.chunk_size == 8000
        assert config.batch_size == 50
        assert config.preprocess_max_concurrent == 15
        assert config.translation_max_concurrent == 10
        assert config.output_dir == Path("/custom/output")

    def test_get_retry_config(self):
        """get_retry_config returns RetryConfig with correct values."""
        config = PipelineConfig(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            max_retries=5,
            base_delay=2.0,
        )
        retry_config = config.get_retry_config()
        assert retry_config.max_retries == 5
        assert retry_config.base_delay == 2.0


class TestPipelineConfigFromEnv:
    """Tests for environment variable overrides."""

    def test_from_env_with_no_env_vars(self):
        """from_env works without any env vars set."""
        with patch.dict(os.environ, {}, clear=True):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
            assert config.model == "gpt-4.1-mini"
            assert config.preprocess_max_concurrent == 20
            assert config.translation_max_concurrent == 20

    def test_from_env_model_override(self):
        """PIPELINE_MODEL overrides model."""
        with patch.dict(os.environ, {f"{ENV_PREFIX}MODEL": "gpt-4o"}):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
            assert config.model == "gpt-4o"

    def test_from_env_integer_overrides(self):
        """Integer fields can be overridden via env vars."""
        env = {
            f"{ENV_PREFIX}CHUNK_SIZE": "8000",
            f"{ENV_PREFIX}BATCH_SIZE": "50",
            f"{ENV_PREFIX}PREPROCESS_MAX_CONCURRENT": "20",
            f"{ENV_PREFIX}TRANSLATION_MAX_CONCURRENT": "15",
            f"{ENV_PREFIX}MAX_RETRIES": "5",
        }
        with patch.dict(os.environ, env):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
            assert config.chunk_size == 8000
            assert config.batch_size == 50
            assert config.preprocess_max_concurrent == 20
            assert config.translation_max_concurrent == 15
            assert config.max_retries == 5

    def test_from_env_float_override(self):
        """Float fields can be overridden via env vars."""
        with patch.dict(os.environ, {f"{ENV_PREFIX}BASE_DELAY": "2.5"}):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
            assert config.base_delay == 2.5

    def test_from_env_path_overrides(self):
        """Path fields can be overridden via env vars."""
        env = {
            f"{ENV_PREFIX}OUTPUT_DIR": "/custom/output",
            f"{ENV_PREFIX}CHECKPOINT_DIR": "/custom/checkpoints",
        }
        with patch.dict(os.environ, env):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
            assert config.output_dir == Path("/custom/output")
            assert config.checkpoint_dir == Path("/custom/checkpoints")

    def test_from_env_invalid_integer_ignored(self):
        """Invalid integer env vars are ignored."""
        with patch.dict(os.environ, {f"{ENV_PREFIX}TRANSLATION_MAX_CONCURRENT": "not_a_number"}):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
            # Should use default value
            assert config.translation_max_concurrent == 20

    def test_from_env_kwargs_override_env(self):
        """Explicit kwargs take precedence over env vars."""
        with patch.dict(os.environ, {f"{ENV_PREFIX}TRANSLATION_MAX_CONCURRENT": "20"}):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                translation_max_concurrent=30,  # Explicit override
            )
            assert config.translation_max_concurrent == 30


class TestCustomInstructions:
    """Tests for custom_instructions field."""

    def test_default_empty(self):
        """custom_instructions defaults to empty string."""
        config = PipelineConfig(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
        )
        assert config.custom_instructions == ""

    def test_custom_value(self):
        """custom_instructions can be set explicitly."""
        config = PipelineConfig(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            custom_instructions="Prefer concise sentences.",
        )
        assert config.custom_instructions == "Prefer concise sentences."

    def test_env_override(self):
        """PIPELINE_CUSTOM_INSTRUCTIONS overrides custom_instructions."""
        with patch.dict(
            os.environ,
            {f"{ENV_PREFIX}CUSTOM_INSTRUCTIONS": "Use formal register."},
        ):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
            assert config.custom_instructions == "Use formal register."

    def test_kwargs_override_env(self):
        """Explicit kwarg takes precedence over env var."""
        with patch.dict(
            os.environ,
            {f"{ENV_PREFIX}CUSTOM_INSTRUCTIONS": "From env."},
        ):
            config = PipelineConfig.from_env(
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                custom_instructions="From kwarg.",
            )
            assert config.custom_instructions == "From kwarg."
