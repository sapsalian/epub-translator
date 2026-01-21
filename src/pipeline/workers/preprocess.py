"""
Preprocess worker for the translation pipeline.

Generates term dictionary and XHTML summaries using API calls.
This prepares context for the translation phase.

Input: PreprocessInput (extraction_result, target_language)
Output: PreprocessResult

This is an IO-bound worker that:
1. Collects raw texts and term candidates from extraction result
2. Calls API to generate term dictionary (technical terms, proper nouns)
3. Calls API to generate per-XHTML summaries for translation context
"""

import logging
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.pipeline.models import (
    ExtractionResult,
    Language,
    PreprocessResult,
    TermCandidate,
    TermDictionary,
    TermMapping,
    XhtmlExtraction,
)

from .base import AsyncWorker, PreprocessError


logger = logging.getLogger(__name__)


# =============================================================================
# API Client Protocol
# =============================================================================


class PreprocessAPIClient(Protocol):
    """
    Protocol for preprocess API client.

    Implementations should handle:
    - Rate limiting and retries
    - Error handling and logging
    - Response parsing
    """

    async def generate_term_dictionary(
        self,
        raw_texts: list[str],
        term_candidates: list[TermCandidate],
        source_language: Language,
        target_language: Language,
    ) -> list[TermMapping]:
        """
        Generate term dictionary from text and candidate terms.

        Args:
            raw_texts: Raw text content from EPUB (chunked if needed).
            term_candidates: Frequency-based term candidates as hints.
            source_language: Source language.
            target_language: Target language.

        Returns:
            List of term mappings (source -> target).
        """
        ...

    async def generate_summary(
        self,
        raw_text: str,
        source_language: Language,
    ) -> str:
        """
        Generate summary for a single XHTML's content.

        Args:
            raw_text: Raw text content from the XHTML.
            source_language: Source language.

        Returns:
            Summary text for translation context.
        """
        ...


# =============================================================================
# Input Model
# =============================================================================


class PreprocessInput(BaseModel):
    """Input for PreprocessWorker."""

    extraction_result: ExtractionResult = Field(
        description="Result from ExtractionWorker"
    )
    target_language: Language = Field(description="Target language for translation")

    model_config = ConfigDict(arbitrary_types_allowed=True)


# =============================================================================
# PreprocessWorker
# =============================================================================


class PreprocessWorker(AsyncWorker[PreprocessInput, PreprocessResult]):
    """
    Generates term dictionary and summaries for translation context.

    Uses API calls to:
    1. Extract and translate technical terms and proper nouns
    2. Generate summaries for each XHTML to provide translation context
    """

    def __init__(self, api_client: PreprocessAPIClient) -> None:
        """
        Initialize PreprocessWorker.

        Args:
            api_client: API client for LLM calls.
        """
        super().__init__()
        self._api_client = api_client

    async def process(self, input_data: PreprocessInput) -> PreprocessResult:
        """
        Generate term dictionary and summaries.

        Args:
            input_data: Preprocess input with extraction result and target language.

        Returns:
            PreprocessResult with term dictionary and summaries.

        Raises:
            PreprocessError: If preprocessing fails.
        """
        extraction = input_data.extraction_result
        target_language = input_data.target_language

        self.logger.info(
            "Starting preprocessing for EPUB: %s (target: %s)",
            extraction.epub_id,
            target_language.value,
        )

        try:
            # Generate term dictionary
            term_dictionary = await self._generate_term_dictionary(
                extraction=extraction,
                target_language=target_language,
            )

            # Generate summaries for each XHTML
            summaries = await self._generate_summaries(extraction=extraction)

            result = PreprocessResult(
                epub_id=extraction.epub_id,
                term_dictionary=term_dictionary,
                summaries=summaries,
            )

            self.logger.info(
                "Preprocessing complete: %d terms, %d summaries",
                len(term_dictionary.mappings),
                len(summaries),
            )

            return result

        except PreprocessError:
            raise
        except Exception as e:
            self.logger.error("Preprocessing failed: %s", e)
            raise PreprocessError(f"Preprocessing failed: {e}") from e

    async def _generate_term_dictionary(
        self,
        extraction: ExtractionResult,
        target_language: Language,
    ) -> TermDictionary:
        """
        Generate term dictionary using API.

        Args:
            extraction: Extraction result with term candidates.
            target_language: Target language.

        Returns:
            TermDictionary with term mappings.
        """
        raw_texts = self._collect_raw_texts(extraction.xhtml_extractions)

        if not raw_texts and not extraction.term_candidates:
            self.logger.debug("No content for term dictionary generation")
            return TermDictionary(
                source_language=extraction.source_language,
                target_language=target_language,
                mappings=[],
            )

        mappings = await self._api_client.generate_term_dictionary(
            raw_texts=raw_texts,
            term_candidates=extraction.term_candidates,
            source_language=extraction.source_language,
            target_language=target_language,
        )

        return TermDictionary(
            source_language=extraction.source_language,
            target_language=target_language,
            mappings=mappings,
        )

    async def _generate_summaries(
        self,
        extraction: ExtractionResult,
    ) -> dict[str, str]:
        """
        Generate summaries for each XHTML.

        Args:
            extraction: Extraction result with XHTML data.

        Returns:
            Dictionary mapping xhtml_id to summary.
        """
        summaries: dict[str, str] = {}

        for xhtml in extraction.xhtml_extractions:
            if not xhtml.raw_text.strip():
                continue

            summary = await self._api_client.generate_summary(
                raw_text=xhtml.raw_text,
                source_language=extraction.source_language,
            )
            summaries[xhtml.xhtml_id] = summary

        return summaries

    def _collect_raw_texts(
        self,
        xhtml_extractions: list[XhtmlExtraction],
    ) -> list[str]:
        """
        Collect non-empty raw texts from XHTML extractions.

        Args:
            xhtml_extractions: List of XHTML extractions.

        Returns:
            List of non-empty raw text strings.
        """
        return [
            xhtml.raw_text
            for xhtml in xhtml_extractions
            if xhtml.raw_text.strip()
        ]
