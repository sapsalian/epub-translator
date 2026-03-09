"""
High-level checkpoint manager for the translation pipeline.

Provides typed methods for saving and loading pipeline data,
abstracting away the key management and serialization details.
"""

import asyncio
import json
import logging
from datetime import datetime

from ..models import (
    ExtractionResult,
    Language,
    PreprocessResult,
    TranslationResult,
)
from .base import PersistenceBackend
from .models import JobStage, JobStatus, StageProgress

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Manages checkpoints for translation jobs.

    Provides high-level operations for saving and loading pipeline data,
    with proper key management and job status tracking.

    Key patterns:
        - {epub_id}:extraction -> ExtractionResult
        - {epub_id}:preprocess:{lang} -> PreprocessResult
        - {epub_id}:glossary_edit:{lang} -> edited term dictionary
        - {epub_id}:translation:{xhtml_id}:{lang} -> TranslationResult
        - {epub_id}:status:{lang} -> JobStatus
    """

    def __init__(self, backend: PersistenceBackend) -> None:
        """
        Initialize the checkpoint manager.

        Args:
            backend: The persistence backend to use for storage.
        """
        self._backend = backend
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create a lock for the given key."""
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    # =========================================================================
    # Key Generation
    # =========================================================================

    @staticmethod
    def _extraction_key(epub_id: str) -> str:
        """Key for extraction result."""
        return f"{epub_id}:extraction"

    @staticmethod
    def _preprocess_key(epub_id: str, lang: Language | str) -> str:
        """Key for preprocess result."""
        lang_code = lang.value if isinstance(lang, Language) else lang
        return f"{epub_id}:preprocess:{lang_code}"

    @staticmethod
    def _translation_key(epub_id: str, xhtml_id: str, lang: Language | str) -> str:
        """Key for translation result."""
        lang_code = lang.value if isinstance(lang, Language) else lang
        return f"{epub_id}:translation:{xhtml_id}:{lang_code}"

    @staticmethod
    def _glossary_edit_key(epub_id: str, lang: Language | str) -> str:
        """Key for user-edited glossary."""
        lang_code = lang.value if isinstance(lang, Language) else lang
        return f"{epub_id}:glossary_edit:{lang_code}"

    @staticmethod
    def _status_key(epub_id: str, lang: Language | str) -> str:
        """Key for job status."""
        lang_code = lang.value if isinstance(lang, Language) else lang
        return f"{epub_id}:status:{lang_code}"

    # =========================================================================
    # Extraction
    # =========================================================================

    async def save_extraction(self, result: ExtractionResult) -> None:
        """
        Save extraction result.

        Args:
            result: The extraction result to save.
        """
        key = self._extraction_key(result.epub_id)
        await self._backend.save(key, result.to_json())
        logger.info("Saved extraction result for epub_id=%s", result.epub_id)

    async def load_extraction(self, epub_id: str) -> ExtractionResult | None:
        """
        Load extraction result.

        Args:
            epub_id: The EPUB identifier.

        Returns:
            ExtractionResult if found, None otherwise.
        """
        key = self._extraction_key(epub_id)
        data = await self._backend.load(key)
        if data is None:
            return None
        return ExtractionResult.from_json(data)

    async def has_extraction(self, epub_id: str) -> bool:
        """Check if extraction result exists."""
        key = self._extraction_key(epub_id)
        return await self._backend.exists(key)

    # =========================================================================
    # Preprocessing
    # =========================================================================

    async def save_preprocess(
        self, result: PreprocessResult, lang: Language | str
    ) -> None:
        """
        Save preprocess result.

        Args:
            result: The preprocess result to save.
            lang: Target language.
        """
        key = self._preprocess_key(result.epub_id, lang)
        await self._backend.save(key, result.to_json())
        logger.info(
            "Saved preprocess result for epub_id=%s, lang=%s",
            result.epub_id,
            lang,
        )

    async def load_preprocess(
        self, epub_id: str, lang: Language | str
    ) -> PreprocessResult | None:
        """
        Load preprocess result.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.

        Returns:
            PreprocessResult if found, None otherwise.
        """
        key = self._preprocess_key(epub_id, lang)
        data = await self._backend.load(key)
        if data is None:
            return None
        return PreprocessResult.from_json(data)

    async def has_preprocess(self, epub_id: str, lang: Language | str) -> bool:
        """Check if preprocess result exists."""
        key = self._preprocess_key(epub_id, lang)
        return await self._backend.exists(key)

    async def save_glossary_edit(
        self,
        epub_id: str,
        lang: Language | str,
        mappings: dict[str, str],
    ) -> None:
        """Save user-edited glossary mappings."""
        key = self._glossary_edit_key(epub_id, lang)
        payload = json.dumps({"mappings": mappings}, ensure_ascii=False, indent=2)
        await self._backend.save(key, payload)

    async def load_glossary_edit(
        self,
        epub_id: str,
        lang: Language | str,
    ) -> dict[str, str] | None:
        """Load user-edited glossary mappings."""
        key = self._glossary_edit_key(epub_id, lang)
        data = await self._backend.load(key)
        if data is None:
            return None
        parsed = json.loads(data)
        mappings = parsed.get("mappings", {})
        return mappings if isinstance(mappings, dict) else {}

    # =========================================================================
    # Translation
    # =========================================================================

    async def save_translation(self, result: TranslationResult) -> None:
        """
        Save translation result for a single XHTML.

        Args:
            result: The translation result to save.
        """
        key = self._translation_key(
            result.epub_id, result.xhtml_id, result.target_language
        )
        await self._backend.save(key, result.to_json())
        logger.debug(
            "Saved translation result for epub_id=%s, xhtml_id=%s, lang=%s",
            result.epub_id,
            result.xhtml_id,
            result.target_language,
        )

    async def load_translation(
        self, epub_id: str, xhtml_id: str, lang: Language | str
    ) -> TranslationResult | None:
        """
        Load translation result for a single XHTML.

        Args:
            epub_id: The EPUB identifier.
            xhtml_id: The XHTML identifier.
            lang: Target language.

        Returns:
            TranslationResult if found, None otherwise.
        """
        key = self._translation_key(epub_id, xhtml_id, lang)
        data = await self._backend.load(key)
        if data is None:
            return None
        return TranslationResult.from_json(data)

    async def get_translated_xhtml_ids(
        self, epub_id: str, lang: Language | str
    ) -> set[str]:
        """
        Get IDs of all translated XHTMLs for an EPUB and language.

        Useful for resume functionality to know which XHTMLs are already done.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.

        Returns:
            Set of xhtml_ids that have been translated.
        """
        lang_code = lang.value if isinstance(lang, Language) else lang
        prefix = f"{epub_id}:translation:"

        keys = await self._backend.list_keys(prefix)
        xhtml_ids: set[str] = set()

        for key in keys:
            # Key format: {epub_id}:translation:{xhtml_id}:{lang}
            parts = key.split(":")
            if len(parts) >= 4 and parts[3] == lang_code:
                xhtml_ids.add(parts[2])

        return xhtml_ids

    async def load_all_translations(
        self, epub_id: str, lang: Language | str
    ) -> list[TranslationResult]:
        """
        Load all translation results for an EPUB and language.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.

        Returns:
            List of all TranslationResult for the EPUB.
        """
        lang_code = lang.value if isinstance(lang, Language) else lang
        prefix = f"{epub_id}:translation:"

        keys = await self._backend.list_keys(prefix)
        results: list[TranslationResult] = []

        for key in keys:
            # Filter by language (key format: {epub_id}:translation:{xhtml_id}:{lang})
            parts = key.split(":")
            if len(parts) >= 4 and parts[3] == lang_code:
                data = await self._backend.load(key)
                if data:
                    results.append(TranslationResult.from_json(data))

        return results

    # =========================================================================
    # Job Status
    # =========================================================================

    async def get_job_status(
        self, epub_id: str, lang: Language | str
    ) -> JobStatus | None:
        """
        Get current job status.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.

        Returns:
            JobStatus if found, None otherwise.
        """
        key = self._status_key(epub_id, lang)
        data = await self._backend.load(key)
        if data is None:
            return None
        return JobStatus.from_json(data)

    async def save_job_status(self, status: JobStatus) -> None:
        """
        Save job status.

        Args:
            status: The job status to save.
        """
        key = self._status_key(status.epub_id, status.target_language)
        await self._backend.save(key, status.to_json())

    async def create_job(
        self,
        epub_id: str,
        lang: Language | str,
        total_xhtmls: int = 0,
    ) -> JobStatus:
        """
        Create a new job status.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.
            total_xhtmls: Total number of XHTMLs (for progress tracking).

        Returns:
            Newly created JobStatus.
        """
        lang_code = lang.value if isinstance(lang, Language) else lang
        status = JobStatus(
            epub_id=epub_id,
            target_language=lang_code,
            stage=JobStage.PENDING,
            extracting=StageProgress(total=total_xhtmls),
            translating=StageProgress(total=total_xhtmls),
            inserting=StageProgress(total=total_xhtmls),
            started_at=datetime.now(),
            updated_at=datetime.now(),
        )
        await self.save_job_status(status)
        logger.info("Created job for epub_id=%s, lang=%s", epub_id, lang)
        return status

    async def update_job_stage(
        self,
        epub_id: str,
        lang: Language | str,
        stage: JobStage,
        total: int | None = None,
        completed: int | None = None,
    ) -> JobStatus | None:
        """
        Update job stage and optionally progress.

        Thread-safe: uses asyncio.Lock to ensure atomicity.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.
            stage: New stage.
            total: Total items for the stage (optional).
            completed: Completed items for the stage (optional).

        Returns:
            Updated JobStatus, or None if job not found.
        """
        key = self._status_key(epub_id, lang)
        async with self._get_lock(key):
            status = await self.get_job_status(epub_id, lang)
            if status is None:
                logger.warning(
                    "Job not found for epub_id=%s, lang=%s", epub_id, lang
                )
                return None

            status = status.update_stage(stage, total, completed)
            await self.save_job_status(status)
            return status

    async def increment_job_progress(
        self,
        epub_id: str,
        lang: Language | str,
        stage: JobStage,
        count: int = 1,
    ) -> JobStatus | None:
        """
        Increment progress for a stage.

        Thread-safe: uses asyncio.Lock to ensure atomicity when
        multiple coroutines call this method concurrently.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.
            stage: Stage to update.
            count: Amount to increment.

        Returns:
            Updated JobStatus, or None if job not found.
        """
        key = self._status_key(epub_id, lang)
        async with self._get_lock(key):
            status = await self.get_job_status(epub_id, lang)
            if status is None:
                return None

            status = status.increment_progress(stage, count)
            await self.save_job_status(status)
            return status

    async def mark_job_failed(
        self, epub_id: str, lang: Language | str, error_message: str
    ) -> JobStatus | None:
        """
        Mark job as failed.

        Thread-safe: uses asyncio.Lock to ensure atomicity.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.
            error_message: Error description.

        Returns:
            Updated JobStatus, or None if job not found.
        """
        key = self._status_key(epub_id, lang)
        async with self._get_lock(key):
            status = await self.get_job_status(epub_id, lang)
            if status is None:
                return None

            status = status.mark_failed(error_message)
            await self.save_job_status(status)
            logger.error(
                "Job failed for epub_id=%s, lang=%s: %s",
                epub_id,
                lang,
                error_message,
            )
            return status

    async def mark_job_completed(
        self, epub_id: str, lang: Language | str
    ) -> JobStatus | None:
        """
        Mark job as completed.

        Thread-safe: uses asyncio.Lock to ensure atomicity.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.

        Returns:
            Updated JobStatus, or None if job not found.
        """
        key = self._status_key(epub_id, lang)
        async with self._get_lock(key):
            status = await self.get_job_status(epub_id, lang)
            if status is None:
                return None

            status = status.mark_completed()
            await self.save_job_status(status)
            logger.info("Job completed for epub_id=%s, lang=%s", epub_id, lang)
            return status

    # =========================================================================
    # Cleanup
    # =========================================================================

    async def clear_job(self, epub_id: str, lang: Language | str | None = None) -> int:
        """
        Clear all data for a job.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language (if None, clears all languages).

        Returns:
            Number of keys deleted.
        """
        if lang is None:
            # Clear everything for this epub
            return await self._backend.clear_prefix(f"{epub_id}:")
        else:
            # Clear language-specific data
            lang_code = lang.value if isinstance(lang, Language) else lang
            count = 0

            # Clear preprocess
            key = self._preprocess_key(epub_id, lang)
            if await self._backend.exists(key):
                await self._backend.delete(key)
                count += 1

            # Clear translations
            prefix = f"{epub_id}:translation:"
            keys = await self._backend.list_keys(prefix)
            for key in keys:
                parts = key.split(":")
                if len(parts) >= 4 and parts[3] == lang_code:
                    await self._backend.delete(key)
                    count += 1

            # Clear edited glossary
            key = self._glossary_edit_key(epub_id, lang)
            if await self._backend.exists(key):
                await self._backend.delete(key)
                count += 1

            # Clear status
            key = self._status_key(epub_id, lang)
            if await self._backend.exists(key):
                await self._backend.delete(key)
                count += 1

            logger.info(
                "Cleared %d keys for epub_id=%s, lang=%s",
                count,
                epub_id,
                lang,
            )
            return count

    # =========================================================================
    # Resume Support
    # =========================================================================

    async def get_resume_point(
        self, epub_id: str, lang: Language | str
    ) -> tuple[JobStage, set[str]]:
        """
        Determine where to resume a job.

        Args:
            epub_id: The EPUB identifier.
            lang: Target language.

        Returns:
            Tuple of (stage_to_resume_from, completed_xhtml_ids).
            If no checkpoints exist, returns (PENDING, empty set).
        """
        # Check what checkpoints exist
        has_extraction = await self.has_extraction(epub_id)
        has_preprocess = await self.has_preprocess(epub_id, lang)
        translated_ids = await self.get_translated_xhtml_ids(epub_id, lang)

        if not has_extraction:
            return (JobStage.EXTRACTING, set())

        if not has_preprocess:
            return (JobStage.PREPROCESSING, set())

        # Load extraction to get total XHTML count
        extraction = await self.load_extraction(epub_id)
        if extraction is None:
            return (JobStage.EXTRACTING, set())

        total_xhtmls = len(extraction.xhtml_extractions)

        if len(translated_ids) < total_xhtmls:
            # Not all XHTMLs translated - resume translation
            return (JobStage.TRANSLATING, translated_ids)

        # All translated - proceed to insertion
        return (JobStage.INSERTING, translated_ids)
