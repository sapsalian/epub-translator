"""
OpenAI API client implementation.

Provides LLMClient implementation using OpenAI's Responses API with structured outputs.
"""

import logging
import os
from typing import TypeVar

from openai import AsyncOpenAI, APIError, RateLimitError as OpenAIRateLimitError
from pydantic import BaseModel

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
from .schemas import ChunkExtractionOutput, MergeOutput, TranslationOutput

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


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

        self._client = AsyncOpenAI(api_key=self._api_key)
        self._model = model
        self._retry_config = retry_config or RetryConfig()

    async def extract_chunk(
        self,
        chunk_text: str,
        source_language: Language,
        target_language: Language,
        existing_terms: TermDict | None = None,
    ) -> ChunkExtraction:
        """Extract summary and terms from a text chunk."""
        if not chunk_text.strip():
            return ChunkExtraction(summary="", terms={})

        input_text = build_chunk_extraction_input(
            chunk_text=chunk_text,
            source_language=source_language,
            target_language=target_language,
            existing_terms=existing_terms,
        )

        result = await self._call_structured(
            instructions=CHUNK_EXTRACTION,
            input_text=input_text,
            output_type=ChunkExtractionOutput,
        )

        return ChunkExtraction(
            summary=result.summary,
            terms=result.terms,
        )

    async def merge_extractions(
        self,
        chunk_summaries: list[str],
        chunk_terms: list[TermDict],
        source_language: Language,
        target_language: Language,
    ) -> MergedExtraction:
        """Merge multiple chunk extractions into a unified result."""
        if not chunk_summaries:
            return MergedExtraction(summary="", terms={})

        if len(chunk_summaries) == 1:
            return MergedExtraction(
                summary=chunk_summaries[0],
                terms=chunk_terms[0],
            )

        input_text = build_meta_merge_input(
            chunk_summaries=chunk_summaries,
            chunk_terms=chunk_terms,
            source_language=source_language,
            target_language=target_language,
        )

        result = await self._call_structured(
            instructions=META_MERGE,
            input_text=input_text,
            output_type=MergeOutput,
        )

        return MergedExtraction(
            summary=result.summary,
            terms=result.terms,
        )

    async def translate(
        self,
        text_units: list[TextUnit],
        source_language: Language,
        target_language: Language,
        term_dictionary: TermDict,
        context_summary: str,
    ) -> list[str]:
        """Translate text units using OpenAI Responses API."""
        if not text_units:
            return []

        unit_ids = [unit.unit_id for unit in text_units]
        texts = [unit.tagged_text for unit in text_units]

        input_text = build_translation_input(
            unit_ids=unit_ids,
            texts=texts,
            source_language=source_language,
            target_language=target_language,
            term_dictionary=term_dictionary,
            context_summary=context_summary,
        )

        result = await self._call_structured(
            instructions=TRANSLATION,
            input_text=input_text,
            output_type=TranslationOutput,
        )

        translations = []
        missing_ids = []
        for unit_id in unit_ids:
            if unit_id in result.translations:
                translations.append(result.translations[unit_id])
            else:
                translations.append("")
                missing_ids.append(unit_id)

        if missing_ids:
            logger.warning("Missing translations for unit IDs: %s", missing_ids)

        return translations

    async def _call_structured(
        self,
        instructions: str,
        input_text: str,
        output_type: type[T],
    ) -> T:
        """
        Make a structured API call using OpenAI Responses API.

        Args:
            instructions: Static instructions (cached by API).
            input_text: Dynamic input data.
            output_type: Pydantic model class for structured output.

        Returns:
            Parsed Pydantic model instance.
        """

        @with_retry(
            config=self._retry_config,
            retryable_exceptions=(RateLimitError, TransientAPIError),
        )
        async def _make_request() -> T:
            try:
                response = await self._client.responses.parse(
                    model=self._model,
                    instructions=instructions,
                    input=input_text,
                    text_format=output_type,
                )
                if response.output_parsed is None:
                    raise ValueError("Structured output parsing returned None")
                return response.output_parsed
            except OpenAIRateLimitError as e:
                raise RateLimitError(str(e)) from e
            except APIError as e:
                if e.status_code and e.status_code >= 500:
                    raise TransientAPIError(str(e)) from e
                raise

        return await _make_request()