"""
OpenAI API client implementation.

Provides LLMClient implementation using OpenAI's API with structured outputs.
"""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI, APIError, RateLimitError as OpenAIRateLimitError

from src.pipeline.models import Language, TermMapping, TextUnit

from .base import ChunkExtraction, MergedExtraction
from .prompts import (
    CHUNK_EXTRACTION_SYSTEM_PROMPT,
    META_MERGE_SYSTEM_PROMPT,
    TRANSLATION_SYSTEM_PROMPT,
    build_chunk_extraction_user_prompt,
    build_meta_merge_user_prompt,
    build_translation_user_prompt,
)
from .retry import (
    RateLimitError,
    RetryConfig,
    TransientAPIError,
    with_retry,
)

logger = logging.getLogger(__name__)


class OpenAIClient:
    """
    OpenAI API client for preprocessing and translation.

    Uses structured outputs for reliable JSON parsing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        retry_config: RetryConfig | None = None,
    ) -> None:
        """
        Initialize OpenAI client.

        Args:
            api_key: OpenAI API key. If not provided, uses OPENAI_API_KEY env var.
            model: Model to use for API calls.
            retry_config: Retry configuration for transient failures.
        """
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key is required. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        self._client = AsyncOpenAI(api_key=self._api_key)
        self._model = model
        self._retry_config = retry_config or RetryConfig()

    async def extract_chunk(
        self,
        chunk_text: str,
        source_language: Language,
        target_language: Language,
        existing_terms: dict[str, str] | None = None,
    ) -> ChunkExtraction:
        """
        Extract summary and terms from a text chunk.

        Args:
            chunk_text: Text chunk to analyze.
            source_language: Source language.
            target_language: Target language.
            existing_terms: Already extracted terms for consistency.

        Returns:
            ChunkExtraction with summary and terms.
        """
        if not chunk_text.strip():
            return ChunkExtraction(summary="", terms=[])

        user_prompt = build_chunk_extraction_user_prompt(
            chunk_text=chunk_text,
            source_language=source_language,
            target_language=target_language,
            existing_terms=existing_terms,
        )

        response = await self._call_api_with_json_response(
            system_prompt=CHUNK_EXTRACTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        return self._parse_chunk_extraction(response)

    async def merge_extractions(
        self,
        chunk_summaries: list[str],
        chunk_terms: list[list[dict[str, str]]],
        source_language: Language,
        target_language: Language,
    ) -> MergedExtraction:
        """
        Merge multiple chunk extractions into a unified result.

        Args:
            chunk_summaries: List of summaries from each chunk.
            chunk_terms: List of term lists from each chunk.
            source_language: Source language.
            target_language: Target language.

        Returns:
            MergedExtraction with combined summary and merged terms.
        """
        if not chunk_summaries:
            return MergedExtraction(summary="", terms=[])

        # If only one chunk, no need to merge
        if len(chunk_summaries) == 1:
            terms = [
                TermMapping(source=t["source"], target=t["target"])
                for t in chunk_terms[0]
                if "source" in t and "target" in t
            ]
            return MergedExtraction(summary=chunk_summaries[0], terms=terms)

        user_prompt = build_meta_merge_user_prompt(
            chunk_summaries=chunk_summaries,
            chunk_terms=chunk_terms,
            source_language=source_language,
            target_language=target_language,
        )

        response = await self._call_api_with_json_response(
            system_prompt=META_MERGE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        return self._parse_merged_extraction(response)

    async def translate(
        self,
        text_units: list[TextUnit],
        source_language: Language,
        target_language: Language,
        term_dictionary: dict[str, str],
        context_summary: str,
    ) -> list[str]:
        """Translate text units using OpenAI API."""
        if not text_units:
            return []

        unit_ids = [unit.unit_id for unit in text_units]
        texts = [unit.tagged_text for unit in text_units]
        user_prompt = build_translation_user_prompt(
            unit_ids=unit_ids,
            texts=texts,
            source_language=source_language,
            target_language=target_language,
            term_dictionary=term_dictionary,
            context_summary=context_summary,
        )

        response = await self._call_api_with_json_response(
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        return self._parse_translations(response, unit_ids=unit_ids)

    async def _call_api_with_json_response(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> Any:
        """
        Make an API call expecting JSON response.

        Uses response_format for structured output when available.

        Args:
            system_prompt: System prompt.
            user_prompt: User prompt.

        Returns:
            Parsed JSON response.
        """

        @with_retry(
            config=self._retry_config,
            retryable_exceptions=(RateLimitError, TransientAPIError),
        )
        async def _make_request() -> Any:
            try:
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or "{}"
                return json.loads(content)
            except OpenAIRateLimitError as e:
                raise RateLimitError(str(e)) from e
            except APIError as e:
                if e.status_code and e.status_code >= 500:
                    raise TransientAPIError(str(e)) from e
                raise
            except json.JSONDecodeError as e:
                logger.error("Failed to parse JSON response: %s", e)
                raise

        return await _make_request()

    def _parse_chunk_extraction(self, response: Any) -> ChunkExtraction:
        """
        Parse chunk extraction response.

        Args:
            response: Parsed JSON response.

        Returns:
            ChunkExtraction with summary and terms.
        """
        if not isinstance(response, dict):
            logger.warning("Unexpected response format for chunk extraction: %s", type(response))
            return ChunkExtraction(summary="", terms=[])

        summary = str(response.get("summary", ""))
        terms_data = response.get("terms", [])

        terms = []
        if isinstance(terms_data, list):
            for item in terms_data:
                if isinstance(item, dict) and "source" in item and "target" in item:
                    terms.append(
                        TermMapping(source=item["source"], target=item["target"])
                    )

        return ChunkExtraction(summary=summary, terms=terms)

    def _parse_merged_extraction(self, response: Any) -> MergedExtraction:
        """
        Parse merged extraction response.

        Args:
            response: Parsed JSON response.

        Returns:
            MergedExtraction with combined summary and terms.
        """
        if not isinstance(response, dict):
            logger.warning("Unexpected response format for merged extraction: %s", type(response))
            return MergedExtraction(summary="", terms=[])

        summary = str(response.get("summary", ""))
        terms_data = response.get("terms", [])

        terms = []
        if isinstance(terms_data, list):
            for item in terms_data:
                if isinstance(item, dict) and "source" in item and "target" in item:
                    terms.append(
                        TermMapping(source=item["source"], target=item["target"])
                    )

        return MergedExtraction(summary=summary, terms=terms)

    def _parse_translations(
        self,
        response: Any,
        unit_ids: list[str],
    ) -> list[str]:
        """
        Parse translations from API response.

        Args:
            response: Parsed JSON response (dict mapping unit_id -> translation).
            unit_ids: Expected unit IDs in order.

        Returns:
            List of translated strings in the same order as unit_ids.
        """
        # Handle dict format (ID-based)
        if isinstance(response, dict):
            # Check for wrapped format {"translations": {...}}
            if "translations" in response and isinstance(response["translations"], dict):
                response = response["translations"]

            translations = []
            missing_ids = []
            for unit_id in unit_ids:
                if unit_id in response:
                    translations.append(str(response[unit_id]))
                else:
                    translations.append("")
                    missing_ids.append(unit_id)

            if missing_ids:
                logger.warning(
                    "Missing translations for unit IDs: %s",
                    missing_ids,
                )

            return translations

        # Handle legacy list format (for backwards compatibility)
        if isinstance(response, list):
            logger.warning("Received list format instead of ID-based dict")
            translations = response
            if len(translations) != len(unit_ids):
                logger.warning(
                    "Translation count mismatch: expected %d, got %d",
                    len(unit_ids),
                    len(translations),
                )
                if len(translations) < len(unit_ids):
                    translations.extend([""] * (len(unit_ids) - len(translations)))
                else:
                    translations = translations[:len(unit_ids)]
            return [str(t) for t in translations]

        logger.warning("Unexpected response format for translations: %s", type(response))
        return [""] * len(unit_ids)
