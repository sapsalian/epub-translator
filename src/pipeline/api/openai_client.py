"""
OpenAI API client implementation.

Provides LLMClient implementation using OpenAI's Responses API with structured outputs.
"""

import json
import logging
import os
import re

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError as OpenAIRateLimitError,
)

from src.pipeline.models import Language, TermDict, TextUnit

from .base import ChunkExtraction, MergedExtraction
from .inputs import (
    build_chunk_extraction_input,
    build_meta_merge_input,
    build_translation_input,
)
from .instructions import CHUNK_EXTRACTION, META_MERGE, TRANSLATION
from .retry import (
    RateLimitError,
    RetryConfig,
    TransientAPIError,
    with_retry,
)
from .schemas import CHUNK_EXTRACTION_SCHEMA, MERGE_SCHEMA, TRANSLATION_SCHEMA

logger = logging.getLogger(__name__)

_RETRY_AFTER_PATTERN = re.compile(r"try again in (\d+\.?\d*)\s*(ms|s)\b")
_RESET_TIME_PATTERN = re.compile(r"(?:(\d+)m)?(\d+(?:\.\d+)?)?s?$")

_EXTENDED_CACHE_MODELS = frozenset({
    "gpt-4.1",
    "gpt-5", "gpt-5-codex",
    "gpt-5.1", "gpt-5.1-codex", "gpt-5.1-codex-mini",
    "gpt-5.1-codex-max", "gpt-5.1-chat-latest",
    "gpt-5.2",
})


def _parse_reset_time(value: str) -> float | None:
    """Parse OpenAI rate limit reset time format (e.g., '6m0s', '1s', '500ms')."""
    if value.endswith("ms"):
        try:
            return float(value[:-2]) / 1000.0
        except ValueError:
            return None

    match = _RESET_TIME_PATTERN.fullmatch(value)
    if not match:
        return None

    minutes = int(match.group(1)) if match.group(1) else 0
    seconds = float(match.group(2)) if match.group(2) else 0.0
    return minutes * 60 + seconds


def _parse_retry_after(error: OpenAIRateLimitError) -> float | None:
    """Extract retry-after seconds from a rate limit error.

    Priority: retry-after header → error message → x-ratelimit-reset-tokens.
    """
    if hasattr(error, "response") and error.response is not None:
        headers = error.response.headers

        retry_after = headers.get("retry-after")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass

    match = _RETRY_AFTER_PATTERN.search(str(error))
    if match:
        value = float(match.group(1))
        if match.group(2) == "ms":
            value /= 1000.0
        return value

    if hasattr(error, "response") and error.response is not None:
        reset_tokens = error.response.headers.get("x-ratelimit-reset-tokens")
        if reset_tokens:
            return _parse_reset_time(reset_tokens)

    return None


class OpenAIClient:
    """
    OpenAI API client for preprocessing and translation.

    Uses Responses API with structured outputs for reliable parsing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        retry_config: RetryConfig | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key is required. "
                "Set OPENAI_API_KEY environment variable or pass api_key parameter."
            )

        self._client = AsyncOpenAI(api_key=self._api_key, max_retries=0)
        self._model = model
        self._retry_config = retry_config or RetryConfig()

    async def extract_chunk(
        self,
        chunk_text: str,
        source_language: Language,
        target_language: Language,
        existing_terms: TermDict | None = None,
        custom_instructions: str = "",
    ) -> ChunkExtraction:
        """Extract summary and terms from a text chunk."""
        if not chunk_text.strip():
            return ChunkExtraction(summary="", terms={})

        logger.info(
            "LLM extract_chunk (chars=%d, existing_terms=%d, custom=%s)",
            len(chunk_text),
            len(existing_terms or {}),
            bool(custom_instructions),
        )

        input_text = build_chunk_extraction_input(
            chunk_text=chunk_text,
            source_language=source_language,
            target_language=target_language,
            existing_terms=existing_terms,
            custom_instructions=custom_instructions,
        )

        cache_key = f"extract:{source_language.value}:{target_language.value}"
        result = await self._call_structured(
            instructions=CHUNK_EXTRACTION,
            input_text=input_text,
            schema=CHUNK_EXTRACTION_SCHEMA,
            cache_key=cache_key,
        )

        terms = {e["source"]: e["target"] for e in result.get("terms", [])}

        return ChunkExtraction(
            summary=result["summary"],
            terms=terms,
            style_notes=result.get("style_notes", ""),
        )

    async def merge_extractions(
        self,
        chunk_summaries: list[str],
        chunk_terms: list[TermDict],
        source_language: Language,
        target_language: Language,
        chunk_styles: list[str] | None = None,
        custom_instructions: str = "",
    ) -> MergedExtraction:
        """Merge multiple chunk extractions into a unified result."""
        if not chunk_summaries:
            return MergedExtraction(summary="", terms={})

        if len(chunk_summaries) == 1:
            return MergedExtraction(
                summary=chunk_summaries[0],
                terms=chunk_terms[0],
                style_notes=(chunk_styles[0] if chunk_styles else ""),
            )

        logger.info(
            "LLM merge_extractions (chunks=%d, term_sets=%d, styles=%d, custom=%s)",
            len(chunk_summaries),
            len(chunk_terms),
            len(chunk_styles or []),
            bool(custom_instructions),
        )

        input_text = build_meta_merge_input(
            chunk_summaries=chunk_summaries,
            chunk_terms=chunk_terms,
            source_language=source_language,
            target_language=target_language,
            chunk_styles=chunk_styles,
            custom_instructions=custom_instructions,
        )

        cache_key = f"merge:{source_language.value}:{target_language.value}"
        result = await self._call_structured(
            instructions=META_MERGE,
            input_text=input_text,
            schema=MERGE_SCHEMA,
            cache_key=cache_key,
        )

        terms = {e["source"]: e["target"] for e in result.get("terms", [])}

        return MergedExtraction(
            summary=result["summary"],
            terms=terms,
            style_notes=result.get("style_notes", ""),
        )

    async def translate(
        self,
        text_units: list[TextUnit],
        source_language: Language,
        target_language: Language,
        term_dictionary: TermDict,
        context_summary: str,
        style_guidelines: str = "",
    ) -> list[str]:
        """Translate text units using OpenAI Responses API."""
        if not text_units:
            return []

        # Use short sequential indices (u1, u2, ...) instead of hex hashes when
        # talking to the LLM. Complex hex IDs cause frequent copy errors in LLM
        # responses; simple short indices are reproduced reliably.
        index_ids = [f"u{i}" for i in range(1, len(text_units) + 1)]
        index_to_unit_id = {idx: unit.unit_id for idx, unit in zip(index_ids, text_units)}
        texts = [unit.tagged_text for unit in text_units]
        total_chars = sum(len(text) for text in texts)

        logger.info(
            "LLM translate (units=%d, chars=%d, terms=%d, style=%s, context=%s)",
            len(text_units),
            total_chars,
            len(term_dictionary),
            bool(style_guidelines),
            bool(context_summary),
        )

        input_text = build_translation_input(
            unit_ids=index_ids,
            texts=texts,
            source_language=source_language,
            target_language=target_language,
            term_dictionary=term_dictionary,
            context_summary=context_summary,
            style_guidelines=style_guidelines,
        )

        cache_key = f"translate:{source_language.value}:{target_language.value}"
        result = await self._call_structured(
            instructions=TRANSLATION,
            input_text=input_text,
            schema=TRANSLATION_SCHEMA,
            cache_key=cache_key,
        )

        # Map sequential indices back to original unit_ids
        index_translations_map = {
            e["unit_id"]: e["text"] for e in result.get("translations", [])
        }
        translations = []
        missing_ids = []
        for idx, unit in zip(index_ids, text_units):
            translation = index_translations_map.get(idx, "")
            translations.append(translation)
            if not translation:
                missing_ids.append(unit.unit_id)

        if missing_ids:
            logger.warning("Missing translations for unit IDs: %s", missing_ids)

        return translations

    async def _call_structured(
        self,
        instructions: str,
        input_text: str,
        schema: dict,
        cache_key: str = "",
    ) -> dict:
        """
        Make a structured API call using OpenAI Responses API.

        Args:
            instructions: Static instructions (cached by API).
            input_text: Dynamic input data.
            schema: JSON schema dict for structured output format.
            cache_key: Prompt cache key for grouping similar requests.

        Returns:
            Parsed JSON response as dict.
        """

        @with_retry(
            config=self._retry_config,
            retryable_exceptions=(RateLimitError, TransientAPIError),
        )
        async def _make_request() -> dict:
            try:
                kwargs: dict = {
                    "model": self._model,
                    "instructions": instructions,
                    "input": input_text,
                    "text": {"format": schema},
                }
                if self._model in _EXTENDED_CACHE_MODELS:
                    kwargs["prompt_cache_retention"] = "24h"
                if cache_key:
                    kwargs["prompt_cache_key"] = cache_key
                response = await self._client.responses.create(**kwargs)
                return json.loads(response.output_text)
            except OpenAIRateLimitError as e:
                raise RateLimitError(
                    str(e), retry_after=_parse_retry_after(e)
                ) from e
            except (APIConnectionError, APITimeoutError) as e:
                raise TransientAPIError(str(e)) from e
            except APIError as e:
                if e.status_code and e.status_code >= 500:
                    raise TransientAPIError(str(e)) from e
                raise

        return await _make_request()
