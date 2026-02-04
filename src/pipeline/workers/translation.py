"""
Translation worker for the translation pipeline.

Translates text units using LLM API with term dictionary and context.

Input: TranslationInput (task, term_dictionary, context_summary)
Output: TranslationResult

This is an IO-bound async worker that:
1. Batches text units for efficient API calls
2. Applies term dictionary for consistent translations
3. Uses context summary for better translation quality
"""

import asyncio
import logging
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from src.pipeline.models import (
    Language,
    TermDict,
    TermDictionary,
    TextUnit,
    TranslatedUnit,
    TranslationResult,
    TranslationTask,
)

from .base import AsyncWorker, TranslationError


logger = logging.getLogger(__name__)


# Default batch size for translation API calls (characters)
DEFAULT_BATCH_SIZE = 4000

# Default maximum concurrent API calls
DEFAULT_MAX_CONCURRENT = 5

# Default maximum retries for empty translations
DEFAULT_MAX_EMPTY_RETRIES = 2


# =============================================================================
# API Client Protocol
# =============================================================================


class TranslationAPIClient(Protocol):
    """
    Protocol for translation API client.

    Implementations should handle:
    - Rate limiting and retries
    - Error handling and logging
    - Response parsing
    """

    async def translate(
        self,
        text_units: list[TextUnit],
        source_language: Language,
        target_language: Language,
        term_dictionary: TermDict,
        context_summary: str,
        style_guidelines: str = "",
    ) -> list[str]:
        """
        Translate text units.

        Args:
            text_units: Text units to translate (with tagged_text).
            source_language: Source language.
            target_language: Target language.
            term_dictionary: Term mappings (source -> target).
            context_summary: Summary for translation context.
            style_guidelines: Style guidelines for translation.

        Returns:
            List of translated texts in same order as text_units.
        """
        ...


# =============================================================================
# Input Model
# =============================================================================


class TranslationInput(BaseModel):
    """
    Input for TranslationWorker.

    Combines the translation task with necessary context that would
    normally be fetched from a database in a distributed setting.
    """

    task: TranslationTask = Field(description="Translation task with text units")
    source_language: Language = Field(description="Source language of the text")
    term_dictionary: TermDictionary = Field(
        description="Term dictionary for consistent translations"
    )
    context_summary: str = Field(
        default="", description="Summary of the content for translation context"
    )
    style_guidelines: str = Field(
        default="", description="Style guidelines for translation"
    )
    batch_size: int = Field(
        default=DEFAULT_BATCH_SIZE,
        description="Maximum characters per translation API call",
    )
    max_concurrent: int = Field(
        default=DEFAULT_MAX_CONCURRENT,
        description="Maximum concurrent API calls",
    )
    max_empty_retries: int = Field(
        default=DEFAULT_MAX_EMPTY_RETRIES,
        description="Maximum retries for empty translation results",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)


# =============================================================================
# TranslationWorker
# =============================================================================


class TranslationWorker(AsyncWorker[TranslationInput, TranslationResult]):
    """
    Translates text units using LLM API.

    Features:
    - Batches text units for efficient API usage
    - Applies term dictionary for consistency
    - Uses semaphore for concurrency control
    - Returns translated units with original unit_ids
    """

    def __init__(self, api_client: TranslationAPIClient) -> None:
        """
        Initialize TranslationWorker.

        Args:
            api_client: API client for translation calls.
        """
        super().__init__()
        self._api_client = api_client

    async def process(self, input_data: TranslationInput) -> TranslationResult:
        """
        Translate text units from the translation task.

        Args:
            input_data: Translation input with task, term dictionary, and context.

        Returns:
            TranslationResult with translated units.

        Raises:
            TranslationError: If translation fails.
        """
        task = input_data.task
        batch_size = input_data.batch_size
        max_concurrent = input_data.max_concurrent

        self.logger.info(
            "Starting translation for XHTML %s (target: %s, %d units, batch_size: %d)",
            task.xhtml_id,
            task.target_language.value,
            len(task.text_units),
            batch_size,
        )

        if not task.text_units:
            self.logger.info("No text units to translate")
            return TranslationResult(
                epub_id=task.epub_id,
                xhtml_id=task.xhtml_id,
                target_language=task.target_language,
                translated_units=[],
            )

        try:
            term_dict = input_data.term_dictionary.mappings

            # Create batches
            batches = self._create_batches(task.text_units, batch_size)

            # Translate batches with concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)
            translated_units = await self._translate_batches(
                batches=batches,
                source_language=input_data.source_language,
                target_language=task.target_language,
                term_dictionary=term_dict,
                context_summary=input_data.context_summary,
                style_guidelines=input_data.style_guidelines,
                semaphore=semaphore,
                max_empty_retries=input_data.max_empty_retries,
            )

            result = TranslationResult(
                epub_id=task.epub_id,
                xhtml_id=task.xhtml_id,
                target_language=task.target_language,
                translated_units=translated_units,
            )

            self.logger.info(
                "Translation complete: %d units translated",
                len(translated_units),
            )

            return result

        except TranslationError:
            raise
        except Exception as e:
            self.logger.error("Translation failed: %s", e)
            raise TranslationError(f"Translation failed: {e}") from e

    async def _translate_batches(
        self,
        batches: list[list[TextUnit]],
        source_language: Language,
        target_language: Language,
        term_dictionary: TermDict,
        context_summary: str,
        style_guidelines: str,
        semaphore: asyncio.Semaphore,
        max_empty_retries: int = DEFAULT_MAX_EMPTY_RETRIES,
    ) -> list[TranslatedUnit]:
        """
        Translate all batches with concurrency control.

        Args:
            batches: List of text unit batches.
            source_language: Source language.
            target_language: Target language.
            term_dictionary: Term mappings.
            context_summary: Content summary.
            style_guidelines: Style guidelines for translation.
            semaphore: Semaphore for concurrency control.
            max_empty_retries: Maximum retries for empty translations.

        Returns:
            List of all translated units in order.
        """
        tasks = [
            self._translate_batch_with_semaphore(
                batch=batch,
                batch_index=i,
                source_language=source_language,
                target_language=target_language,
                term_dictionary=term_dictionary,
                context_summary=context_summary,
                style_guidelines=style_guidelines,
                semaphore=semaphore,
                max_empty_retries=max_empty_retries,
            )
            for i, batch in enumerate(batches)
        ]

        batch_results = await asyncio.gather(*tasks)

        # Flatten results maintaining order
        all_units: list[TranslatedUnit] = []
        for batch_units in batch_results:
            all_units.extend(batch_units)

        return all_units

    async def _translate_batch_with_semaphore(
        self,
        batch: list[TextUnit],
        batch_index: int,
        source_language: Language,
        target_language: Language,
        term_dictionary: TermDict,
        context_summary: str,
        style_guidelines: str,
        semaphore: asyncio.Semaphore,
        max_empty_retries: int = DEFAULT_MAX_EMPTY_RETRIES,
    ) -> list[TranslatedUnit]:
        """
        Translate a single batch with semaphore for rate limiting.

        Retries empty translations up to max_empty_retries times.

        Args:
            batch: Text units to translate.
            batch_index: Index of this batch (for logging).
            source_language: Source language.
            target_language: Target language.
            term_dictionary: Term mappings.
            context_summary: Content summary.
            style_guidelines: Style guidelines for translation.
            semaphore: Semaphore for concurrency control.
            max_empty_retries: Maximum retries for empty translations.

        Returns:
            List of translated units for this batch.
        """
        async with semaphore:
            self.logger.debug(
                "Translating batch %d (%d units)", batch_index, len(batch)
            )

            # Initial translation
            translations = await self._api_client.translate(
                text_units=batch,
                source_language=source_language,
                target_language=target_language,
                term_dictionary=term_dictionary,
                context_summary=context_summary,
                style_guidelines=style_guidelines,
            )

            # Build result map (unit_id -> translation)
            result_map: dict[str, str] = {}
            for unit, translation in zip(batch, translations):
                result_map[unit.unit_id] = translation

            # Retry empty translations
            for retry in range(max_empty_retries):
                # Find units with empty translations
                empty_units = [
                    unit for unit in batch
                    if not result_map.get(unit.unit_id, "").strip()
                ]

                if not empty_units:
                    break

                self.logger.warning(
                    "Batch %d: %d empty translations, retry %d/%d",
                    batch_index,
                    len(empty_units),
                    retry + 1,
                    max_empty_retries,
                )

                # Retry only empty units
                retry_translations = await self._api_client.translate(
                    text_units=empty_units,
                    source_language=source_language,
                    target_language=target_language,
                    term_dictionary=term_dictionary,
                    context_summary=context_summary,
                    style_guidelines=style_guidelines,
                )

                # Update result map with retry results
                for unit, translation in zip(empty_units, retry_translations):
                    if translation.strip():
                        result_map[unit.unit_id] = translation

            # Log remaining empty translations
            remaining_empty = sum(
                1 for unit in batch if not result_map.get(unit.unit_id, "").strip()
            )
            if remaining_empty > 0:
                self.logger.warning(
                    "Batch %d: %d translations still empty after retries",
                    batch_index,
                    remaining_empty,
                )

            # Create TranslatedUnit objects in original order
            translated_units = [
                TranslatedUnit(
                    unit_id=unit.unit_id,
                    translated_text=result_map.get(unit.unit_id, ""),
                )
                for unit in batch
            ]

            return translated_units

    def _create_batches(
        self, text_units: list[TextUnit], batch_size: int
    ) -> list[list[TextUnit]]:
        """
        Split text units into batches by character count.

        Accumulates text units until adding the next would exceed batch_size
        characters. Each unit always gets included in some batch (a single
        unit larger than batch_size forms its own batch).

        Args:
            text_units: All text units to translate.
            batch_size: Maximum characters per batch.

        Returns:
            List of batches.
        """
        batches: list[list[TextUnit]] = []
        current_batch: list[TextUnit] = []
        current_size = 0

        for unit in text_units:
            unit_size = len(unit.tagged_text)

            if current_size + unit_size > batch_size and current_batch:
                batches.append(current_batch)
                current_batch = [unit]
                current_size = unit_size
            else:
                current_batch.append(unit)
                current_size += unit_size

        if current_batch:
            batches.append(current_batch)

        return batches
