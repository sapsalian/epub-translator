"""
Pipeline configuration.

Provides centralized configuration for the translation pipeline
with .env file and environment variable override support.
"""

import os
from pathlib import Path

from pydantic import BaseModel, Field

from .models import Language


# Environment variable prefix
ENV_PREFIX = "PIPELINE_"

# Project root (.env location)
_PROJECT_ROOT = Path(__file__).parents[2]


def _load_env_file(env_path: Path | None = None) -> None:
    """
    Load .env file into os.environ.

    Only sets variables not already present in os.environ
    (existing env vars take precedence).

    Args:
        env_path: Path to .env file. Defaults to project root .env.
    """
    path = env_path or (_PROJECT_ROOT / ".env")
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


class PipelineConfig(BaseModel):
    """
    Configuration for the translation pipeline.

    All settings can be overridden via .env file or environment variables
    with the PIPELINE_ prefix (e.g., PIPELINE_MODEL=gpt-4o).

    Priority (highest to lowest):
    1. kwargs passed to from_env()
    2. Shell environment variables
    3. .env file values
    4. Default values

    Example:
        # Minimal: reads languages and settings from .env
        config = PipelineConfig.from_env()

        # Override specific settings
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
    custom_instructions: str = Field(
        default="",
        description="Custom translation instructions appended to style guidelines",
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
        source_language: Language | None = None,
        target_language: Language | None = None,
        **kwargs,
    ) -> "PipelineConfig":
        """
        Create config from .env file and environment variables.

        Loads .env file first, then reads PIPELINE_ prefixed env vars.

        Environment variables:
        - PIPELINE_SOURCE_LANGUAGE: Source language code (e.g., en, ko, ja)
        - PIPELINE_TARGET_LANGUAGE: Target language code
        - PIPELINE_MODEL: API model name
        - PIPELINE_CHUNK_SIZE: Preprocessing chunk size
        - PIPELINE_BATCH_SIZE: Translation batch size
        - PIPELINE_PREPROCESS_MAX_CONCURRENT: Max concurrent preprocessing calls
        - PIPELINE_TRANSLATION_MAX_CONCURRENT: Max concurrent translation calls
        - PIPELINE_MAX_RETRIES: Max retry attempts
        - PIPELINE_BASE_DELAY: Base delay for retries
        - PIPELINE_OUTPUT_DIR: Output directory path
        - PIPELINE_CHECKPOINT_DIR: Checkpoint directory path
        - PIPELINE_CUSTOM_INSTRUCTIONS: Custom translation instructions

        Args:
            source_language: Source language. If None, reads from env.
            target_language: Target language. If None, reads from env.
            **kwargs: Additional config overrides (highest priority).

        Returns:
            PipelineConfig with env var overrides applied.

        Raises:
            ValueError: If source_language or target_language not provided
                and not found in environment.
        """
        _load_env_file()

        env_overrides = cls._get_env_overrides()

        # kwargs take precedence over env vars
        final_kwargs = {**env_overrides, **kwargs}

        # Languages: param > kwargs > env
        if source_language is not None:
            final_kwargs["source_language"] = source_language
        if target_language is not None:
            final_kwargs["target_language"] = target_language

        return cls(**final_kwargs)

    @classmethod
    def _get_env_overrides(cls) -> dict:
        """
        Read configuration overrides from environment variables.

        Returns:
            Dict of field name -> value for any set env vars.
        """
        overrides = {}

        # Language fields
        if source_lang := os.environ.get(f"{ENV_PREFIX}SOURCE_LANGUAGE"):
            overrides["source_language"] = Language(source_lang)
        if target_lang := os.environ.get(f"{ENV_PREFIX}TARGET_LANGUAGE"):
            overrides["target_language"] = Language(target_lang)

        # String fields
        if model := os.environ.get(f"{ENV_PREFIX}MODEL"):
            overrides["model"] = model
        if custom_instructions := os.environ.get(f"{ENV_PREFIX}CUSTOM_INSTRUCTIONS"):
            overrides["custom_instructions"] = custom_instructions

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
