"""
Pipeline configuration.

Provides centralized configuration for the translation pipeline
with environment variable override support.
"""

import os
from pathlib import Path

from pydantic import BaseModel, Field

from .models import Language


# Environment variable prefix
ENV_PREFIX = "PIPELINE_"


class PipelineConfig(BaseModel):
    """
    Configuration for the translation pipeline.

    All settings can be overridden via environment variables with
    the PIPELINE_ prefix (e.g., PIPELINE_MAX_CONCURRENT=10).

    Example:
        # From code
        config = PipelineConfig(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
        )

        # With env var overrides
        # PIPELINE_MAX_CONCURRENT=20 PIPELINE_MODEL=gpt-4o python main.py
        config = PipelineConfig.from_env(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
        )
    """

    # Required: Languages
    source_language: Language = Field(description="Source language of the EPUB")
    target_language: Language = Field(description="Target language for translation")

    # API settings
    model: str = Field(
        default="gpt-4.1-mini",
        description="OpenAI model to use for API calls",
    )

    # Preprocessing settings
    chunk_size: int = Field(
        default=4000,
        description="Maximum characters per chunk for preprocessing API calls",
    )

    # Translation settings
    batch_size: int = Field(
        default=4000,
        description="Maximum characters per translation API call",
    )

    # Concurrency settings
    preprocess_max_concurrent: int = Field(
        default=20,
        description="Maximum concurrent API calls for preprocessing",
    )
    translation_max_concurrent: int = Field(
        default=20,
        description="Maximum concurrent API calls for translation",
    )

    # Retry settings
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for API calls",
    )
    base_delay: float = Field(
        default=1.0,
        description="Base delay in seconds for exponential backoff",
    )

    # Paths
    output_dir: Path = Field(
        default=Path("./output"),
        description="Directory for translated EPUB output",
    )
    checkpoint_dir: Path = Field(
        default=Path("./checkpoints"),
        description="Directory for checkpoint files",
    )

    @classmethod
    def from_env(
        cls,
        source_language: Language,
        target_language: Language,
        **kwargs,
    ) -> "PipelineConfig":
        """
        Create config with environment variable overrides.

        Environment variables use PIPELINE_ prefix:
        - PIPELINE_MODEL: API model name
        - PIPELINE_CHUNK_SIZE: Preprocessing chunk size
        - PIPELINE_BATCH_SIZE: Translation batch size
        - PIPELINE_PREPROCESS_MAX_CONCURRENT: Max concurrent API calls for preprocessing
        - PIPELINE_TRANSLATION_MAX_CONCURRENT: Max concurrent API calls for translation
        - PIPELINE_MAX_RETRIES: Max retry attempts
        - PIPELINE_BASE_DELAY: Base delay for retries
        - PIPELINE_OUTPUT_DIR: Output directory path
        - PIPELINE_CHECKPOINT_DIR: Checkpoint directory path

        Args:
            source_language: Source language (required).
            target_language: Target language (required).
            **kwargs: Additional config overrides.

        Returns:
            PipelineConfig with env var overrides applied.
        """
        env_overrides = cls._get_env_overrides()

        # kwargs take precedence over env vars
        final_kwargs = {
            "source_language": source_language,
            "target_language": target_language,
            **env_overrides,
            **kwargs,
        }

        return cls(**final_kwargs)

    @classmethod
    def _get_env_overrides(cls) -> dict:
        """
        Read configuration overrides from environment variables.

        Returns:
            Dict of field name -> value for any set env vars.
        """
        overrides = {}

        # String fields
        if model := os.environ.get(f"{ENV_PREFIX}MODEL"):
            overrides["model"] = model

        # Integer fields
        int_fields = [
            "chunk_size",
            "batch_size",
            "preprocess_max_concurrent",
            "translation_max_concurrent",
            "max_retries",
        ]
        for field in int_fields:
            env_key = f"{ENV_PREFIX}{field.upper()}"
            if value := os.environ.get(env_key):
                try:
                    overrides[field] = int(value)
                except ValueError:
                    pass  # Ignore invalid values

        # Float fields
        if base_delay := os.environ.get(f"{ENV_PREFIX}BASE_DELAY"):
            try:
                overrides["base_delay"] = float(base_delay)
            except ValueError:
                pass

        # Path fields
        if output_dir := os.environ.get(f"{ENV_PREFIX}OUTPUT_DIR"):
            overrides["output_dir"] = Path(output_dir)

        if checkpoint_dir := os.environ.get(f"{ENV_PREFIX}CHECKPOINT_DIR"):
            overrides["checkpoint_dir"] = Path(checkpoint_dir)

        return overrides

    def get_retry_config(self):
        """
        Create RetryConfig from pipeline config.

        Returns:
            RetryConfig instance.
        """
        from .api.retry import RetryConfig

        return RetryConfig(
            max_retries=self.max_retries,
            base_delay=self.base_delay,
        )
