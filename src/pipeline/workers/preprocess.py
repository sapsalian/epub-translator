"""
Preprocess worker for the translation pipeline.

Generates term dictionary and XHTML summaries using API calls.
This prepares context for the translation phase.

Input: PreprocessInput (extraction_result, target_language)
Output: PreprocessResult

Processing order:
1. XHTMLs are processed one at a time (sequential)
2. Within each XHTML, chunks are processed in parallel (semaphore-limited)
3. Chunk results are merged per-XHTML (summary + terms)
4. XHTML term results are merged into final EPUB term dictionary
5. Summaries are kept per-XHTML for translation context
"""

import asyncio
import logging
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.pipeline.models import (
    ExtractionResult,
    Language,
    PreprocessResult,
    TermDict,
    TermDictionary,
    XhtmlExtraction,
)

from .base import AsyncWorker, PreprocessError


logger = logging.getLogger(__name__)


# Default chunk size in characters
DEFAULT_CHUNK_SIZE = 4000

# Default maximum concurrent API calls
DEFAULT_MAX_CONCURRENT = 5


# =============================================================================
# Data Classes for Chunk Results
# =============================================================================


class ChunkResult:
    """Result from processing a single text chunk."""

    def __init__(self, summary: str, terms: TermDict, style_notes: str = "") -> None:
        self.summary = summary
        self.terms = terms
        self.style_notes = style_notes


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

    async def extract_chunk(
        self,
        chunk_text: str,
        source_language: Language,
        target_language: Language,
        existing_terms: TermDict | None = None,
        custom_instructions: str = "",
    ) -> ChunkResult:
        """
        Extract summary and terms from a text chunk.

        Args:
            chunk_text: Text chunk to analyze.
            source_language: Source language.
            target_language: Target language.
            existing_terms: Already extracted terms for consistency.
            custom_instructions: Custom style instructions to incorporate.

        Returns:
            ChunkResult with summary and terms.
        """
        ...

    async def merge_extractions(
        self,
        chunk_summaries: list[str],
        chunk_terms: list[TermDict],
        source_language: Language,
        target_language: Language,
        chunk_styles: list[str] | None = None,
        custom_instructions: str = "",
    ) -> ChunkResult:
        """
        Merge multiple chunk extractions into a unified result.

        Args:
            chunk_summaries: List of summaries from each chunk.
            chunk_terms: List of term dicts from each chunk (source -> target).
            source_language: Source language.
            target_language: Target language.
            chunk_styles: List of style notes from each chunk.
            custom_instructions: Custom style instructions to incorporate.

        Returns:
            ChunkResult with combined summary and merged terms.
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
    custom_instructions: str = Field(
        default="", description="Custom style instructions to incorporate"
    )
    chunk_size: int = Field(
        default=DEFAULT_CHUNK_SIZE,
        description="Maximum characters per chunk for API calls",
    )
    max_concurrent: int = Field(
        default=DEFAULT_MAX_CONCURRENT,
        description="Maximum concurrent API calls",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


# =============================================================================
# PreprocessWorker
# =============================================================================


class PreprocessWorker(AsyncWorker[PreprocessInput, PreprocessResult]):
    """
    Generates term dictionary and summaries for translation context.

    Uses chunked API calls to:
    1. Extract summary + terms from each text chunk
    2. Merge chunk results into per-XHTML summary + accumulated terms
    3. Final merge to create unified term dictionary
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

        Uses parallel processing:
        1. All XHTMLs processed in parallel
        2. Within each XHTML, all chunks processed in parallel
        3. XHTML term results merged into final EPUB term dictionary
        4. Summaries kept per-XHTML

        Args:
            input_data: Preprocess input with extraction result and target language.

        Returns:
            PreprocessResult with term dictionary and summaries.

        Raises:
            PreprocessError: If preprocessing fails.
        """
        extraction = input_data.extraction_result
        target_language = input_data.target_language
        custom_instructions = input_data.custom_instructions
        chunk_size = input_data.chunk_size

        max_concurrent = input_data.max_concurrent

        self.logger.info(
            "Starting preprocessing for EPUB: %s (target: %s, chunk_size: %d, max_concurrent=%d)",
            extraction.epub_id,
            target_language.value,
            chunk_size,
            max_concurrent,
        )

        try:
            # Filter XHTMLs with content
            xhtmls_with_content = [
                xhtml for xhtml in extraction.xhtml_extractions
                if xhtml.raw_text.strip()
            ]

            if not xhtmls_with_content:
                return PreprocessResult(
                    epub_id=extraction.epub_id,
                    term_dictionary=TermDictionary(
                        source_language=extraction.source_language,
                        target_language=target_language,
                        mappings={},
                    ),
                    summaries={},
                    epub_summary="",
                )

            # Process XHTMLs sequentially; chunks within each XHTML in parallel
            semaphore = asyncio.Semaphore(max_concurrent)
            total_xhtmls = len(xhtmls_with_content)
            xhtml_results = []
            for i, xhtml in enumerate(xhtmls_with_content, 1):
                result = await self._process_xhtml(
                    xhtml=xhtml,
                    source_language=extraction.source_language,
                    target_language=target_language,
                    chunk_size=chunk_size,
                    semaphore=semaphore,
                    custom_instructions=custom_instructions,
                    index=i,
                    total=total_xhtmls,
                )
                xhtml_results.append(result)

            # Collect results
            all_summaries: dict[str, str] = {}
            all_style_notes: dict[str, str] = {}
            all_xhtml_terms: list[TermDict] = []
            all_xhtml_summaries: list[str] = []

            for xhtml, (xhtml_summary, xhtml_terms, xhtml_style) in zip(
                xhtmls_with_content, xhtml_results
            ):
                all_summaries[xhtml.xhtml_id] = xhtml_summary
                if xhtml_style:
                    all_style_notes[xhtml.xhtml_id] = xhtml_style
                if xhtml_summary:
                    all_xhtml_summaries.append(xhtml_summary)
                if xhtml_terms:
                    all_xhtml_terms.append(xhtml_terms)

            # Merge all XHTML terms into final EPUB term dictionary
            epub_summary = ""
            epub_style = ""
            all_xhtml_styles = list(all_style_notes.values())
            if len(all_xhtml_terms) > 1:
                # Use merge API to deduplicate and resolve conflicts
                # Include summaries for better context during term conflict resolution
                merged = await self._api_client.merge_extractions(
                    chunk_summaries=all_xhtml_summaries,
                    chunk_terms=all_xhtml_terms,
                    source_language=extraction.source_language,
                    target_language=target_language,
                    chunk_styles=all_xhtml_styles,
                    custom_instructions=custom_instructions,
                )
                final_mappings = merged.terms
                epub_summary = merged.summary
                epub_style = merged.style_notes
            elif len(all_xhtml_terms) == 1:
                # Single XHTML - use directly
                final_mappings = all_xhtml_terms[0]
                # Use single XHTML summary as epub summary
                epub_summary = all_xhtml_summaries[0] if all_xhtml_summaries else ""
                # Use single XHTML style as epub style
                epub_style = next(iter(all_style_notes.values()), "")
            else:
                final_mappings = {}

            term_dictionary = TermDictionary(
                source_language=extraction.source_language,
                target_language=target_language,
                mappings=final_mappings,
            )

            result = PreprocessResult(
                epub_id=extraction.epub_id,
                term_dictionary=term_dictionary,
                summaries=all_summaries,
                epub_summary=epub_summary,
                style_notes=all_style_notes,
                epub_style=epub_style,
            )

            self.logger.info(
                "Preprocessing complete: %d terms, %d summaries",
                len(term_dictionary.mappings),
                len(all_summaries),
            )

            return result

        except PreprocessError:
            raise
        except Exception as e:
            self.logger.error("Preprocessing failed: %s", e)
            raise PreprocessError(f"Preprocessing failed: {e}") from e

    async def _process_xhtml(
        self,
        xhtml: XhtmlExtraction,
        source_language: Language,
        target_language: Language,
        chunk_size: int,
        semaphore: asyncio.Semaphore,
        custom_instructions: str,
        index: int,
        total: int,
    ) -> tuple[str, TermDict, str]:
        """
        Process a single XHTML file with parallel chunk processing.

        Chunks are dispatched in parallel (semaphore-limited), then results are merged.

        Args:
            xhtml: XHTML extraction data.
            source_language: Source language.
            target_language: Target language.
            chunk_size: Maximum chunk size.
            semaphore: Shared semaphore limiting concurrent API calls.
            custom_instructions: Custom style instructions.
            index: 1-based XHTML index for logging.
            total: Total XHTML count for logging.

        Returns:
            Tuple of (summary, terms_dict, style_notes).
        """
        chunks = self._split_into_chunks(xhtml.raw_text, chunk_size)
        self.logger.info(
            "Preprocess XHTML %d/%d: %s (chunks=%d)",
            index,
            total,
            xhtml.xhtml_id,
            len(chunks),
        )

        if not chunks:
            return "", {}, ""

        async def _extract(chunk: str) -> ChunkResult:
            async with semaphore:
                return await self._api_client.extract_chunk(
                    chunk_text=chunk,
                    source_language=source_language,
                    target_language=target_language,
                    existing_terms=None,
                    custom_instructions=custom_instructions,
                )

        chunk_results = await asyncio.gather(*(_extract(c) for c in chunks))

        # Collect chunk results
        chunk_summaries: list[str] = []
        chunk_terms: list[TermDict] = []
        chunk_styles: list[str] = []

        for result in chunk_results:
            if result.summary:
                chunk_summaries.append(result.summary)
            chunk_terms.append(result.terms)
            if result.style_notes:
                chunk_styles.append(result.style_notes)

        # Merge chunks for this XHTML if multiple
        if len(chunks) > 1:
            merged = await self._api_client.merge_extractions(
                chunk_summaries=chunk_summaries,
                chunk_terms=chunk_terms,
                source_language=source_language,
                target_language=target_language,
                chunk_styles=chunk_styles,
                custom_instructions=custom_instructions,
            )
            return merged.summary, merged.terms, merged.style_notes

        # Single chunk - return as-is
        summary = chunk_summaries[0] if chunk_summaries else ""
        terms = chunk_terms[0] if chunk_terms else {}
        style_notes = chunk_styles[0] if chunk_styles else ""

        return summary, terms, style_notes

    def _split_into_chunks(self, text: str, chunk_size: int) -> list[str]:
        """
        Split text into chunks of approximately chunk_size characters.

        Splits at line boundaries since raw_text uses single newlines
        between extracted elements.

        Args:
            text: Text to split.
            chunk_size: Target chunk size.

        Returns:
            List of text chunks.
        """
        if not text.strip():
            return []

        if len(text) <= chunk_size:
            return [text]

        chunks: list[str] = []
        lines = text.split("\n")

        current_chunk: list[str] = []
        current_size = 0

        for line in lines:
            line_size = len(line) + 1  # +1 for \n

            if current_size + line_size > chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks
