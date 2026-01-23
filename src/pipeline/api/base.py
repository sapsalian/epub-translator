"""
Base protocol for LLM API clients.

Defines the interface that all LLM client implementations must follow.
This enables easy swapping between different LLM providers (OpenAI, Anthropic, etc.).
"""

from dataclasses import dataclass
from typing import Protocol

from src.pipeline.models import Language, TermMapping, TextUnit


@dataclass
class ChunkExtraction:
    """Result of extracting summary and terms from a text chunk."""

    summary: str
    terms: list[TermMapping]


@dataclass
class MergedExtraction:
    """Result of merging multiple chunk extractions."""

    summary: str
    terms: list[TermMapping]


class PreprocessClient(Protocol):
    """
    Protocol for preprocessing API operations.

    Implementations handle chunk extraction and merging.
    """

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
        ...

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
        ...


class TranslationClient(Protocol):
    """
    Protocol for translation API operations.

    Implementations handle the actual text translation.
    """

    async def translate(
        self,
        text_units: list[TextUnit],
        source_language: Language,
        target_language: Language,
        term_dictionary: dict[str, str],
        context_summary: str,
    ) -> list[str]:
        """
        Translate text units.

        Args:
            text_units: Text units to translate (with tagged_text).
            source_language: Source language.
            target_language: Target language.
            term_dictionary: Term mappings to use (source -> target).
            context_summary: Summary for translation context.

        Returns:
            List of translated texts (preserving placeholder tags).
        """
        ...


class LLMClient(PreprocessClient, TranslationClient, Protocol):
    """
    Combined protocol for full LLM client capabilities.

    Implementations should provide both preprocessing and translation.
    """

    pass
