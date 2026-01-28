"""
Pipeline orchestrator.

Coordinates the translation pipeline stages with checkpoint support
for resumable processing.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

from .api.openai_client import OpenAIClient
from .config import PipelineConfig
from .models import (
    ExtractionResult,
    InsertionResult,
    Language,
    PreprocessResult,
    TranslationResult,
    TranslationTask,
)
from .persistence import CheckpointManager, FilePersistenceBackend, JobStage
from .workers.extraction import ExtractionInput, ExtractionWorker
from .workers.insertion import InsertionInput, InsertionWorker
from .workers.preprocess import PreprocessInput, PreprocessWorker
from .workers.translation import TranslationInput, TranslationWorker


logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the translation pipeline.

    Manages the four stages of translation:
    1. Extraction: Parse EPUB and extract translatable text
    2. Preprocessing: Generate term dictionary and summaries
    3. Translation: Translate text units using LLM API
    4. Insertion: Create translated EPUB

    Supports resumable processing through checkpoints.
    """

    def __init__(self, config: PipelineConfig) -> None:
        """
        Initialize the orchestrator.

        Args:
            config: Pipeline configuration.
        """
        self._config = config
        self._api_client: OpenAIClient | None = None
        self._checkpoint_manager: CheckpointManager | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """
        Initialize backend services.

        Must be called before running the pipeline.
        """
        if self._initialized:
            return

        # Initialize API client
        self._api_client = OpenAIClient(
            model=self._config.model,
            retry_config=self._config.get_retry_config(),
        )

        # Initialize checkpoint manager
        backend = FilePersistenceBackend(str(self._config.checkpoint_dir))
        await backend.initialize()
        self._checkpoint_manager = CheckpointManager(backend)

        # Ensure output directory exists
        self._config.output_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        logger.info(
            "Orchestrator initialized (model=%s, checkpoint_dir=%s)",
            self._config.model,
            self._config.checkpoint_dir,
        )

    async def run(self, epub_path: Path) -> InsertionResult:
        """
        Run the complete translation pipeline for a single EPUB.

        Supports resuming from checkpoints if a previous run was interrupted.

        Args:
            epub_path: Path to the EPUB file.

        Returns:
            InsertionResult with the translated EPUB path.

        Raises:
            RuntimeError: If orchestrator not initialized.
            Exception: If any pipeline stage fails.
        """
        if not self._initialized:
            raise RuntimeError("Orchestrator not initialized. Call initialize() first.")

        epub_id = self._generate_epub_id(epub_path)
        lang = self._config.target_language

        logger.info(
            "Starting pipeline for %s -> %s (epub_id=%s)",
            epub_path.name,
            lang.value,
            epub_id,
        )

        try:
            # Check resume point
            resume_stage, translated_xhtml_ids = await self._checkpoint_manager.get_resume_point(
                epub_id, lang
            )

            logger.info("Resume point: stage=%s, translated=%d XHTMLs", resume_stage.value, len(translated_xhtml_ids))

            # Create or update job
            extraction_result = await self._checkpoint_manager.load_extraction(epub_id)
            total_xhtmls = len(extraction_result.xhtml_extractions) if extraction_result else 0

            existing_job = await self._checkpoint_manager.get_job_status(epub_id, lang)
            if existing_job is None:
                await self._checkpoint_manager.create_job(epub_id, lang, total_xhtmls)

            # Stage 1: Extraction
            if resume_stage == JobStage.EXTRACTING:
                extraction_result = await self._run_extraction(epub_id, epub_path)
                total_xhtmls = len(extraction_result.xhtml_extractions)
                # Update job with actual XHTML count
                await self._checkpoint_manager.update_job_stage(
                    epub_id, lang, JobStage.EXTRACTING,
                    total=total_xhtmls, completed=total_xhtmls
                )

            # Stage 2: Preprocessing
            if resume_stage in (JobStage.EXTRACTING, JobStage.PREPROCESSING):
                if extraction_result is None:
                    extraction_result = await self._checkpoint_manager.load_extraction(epub_id)

                await self._run_preprocessing(epub_id, extraction_result)
                await self._checkpoint_manager.update_job_stage(
                    epub_id, lang, JobStage.PREPROCESSING, completed=1, total=1
                )

            # Stage 3: Translation
            if resume_stage in (JobStage.EXTRACTING, JobStage.PREPROCESSING, JobStage.TRANSLATING):
                if extraction_result is None:
                    extraction_result = await self._checkpoint_manager.load_extraction(epub_id)

                preprocess_result = await self._checkpoint_manager.load_preprocess(epub_id, lang)

                await self._run_translation(
                    epub_id=epub_id,
                    extraction_result=extraction_result,
                    preprocess_result=preprocess_result,
                    already_translated=translated_xhtml_ids,
                )

            # Stage 4: Insertion
            if extraction_result is None:
                extraction_result = await self._checkpoint_manager.load_extraction(epub_id)

            translation_results = await self._checkpoint_manager.load_all_translations(epub_id, lang)

            result = await self._run_insertion(
                epub_id=epub_id,
                epub_path=epub_path,
                extraction_result=extraction_result,
                translation_results=translation_results,
            )

            # Mark job as completed
            await self._checkpoint_manager.mark_job_completed(epub_id, lang)

            logger.info("Pipeline completed: %s", result.output_path)
            return result

        except Exception as e:
            logger.error("Pipeline failed for %s: %s", epub_path.name, e)
            await self._checkpoint_manager.mark_job_failed(epub_id, lang, str(e))
            raise

    async def run_batch(
        self,
        epub_paths: list[Path],
        parallel: bool = False,
    ) -> list[InsertionResult]:
        """
        Run pipeline for multiple EPUBs.

        Args:
            epub_paths: List of EPUB file paths.
            parallel: If True, process EPUBs in parallel. Default is sequential.

        Returns:
            List of InsertionResult for each EPUB.
        """
        if not self._initialized:
            raise RuntimeError("Orchestrator not initialized. Call initialize() first.")

        if parallel:
            tasks = [self.run(path) for path in epub_paths]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for path in epub_paths:
                result = await self.run(path)
                results.append(result)
            return results

    async def _run_extraction(
        self,
        epub_id: str,
        epub_path: Path,
    ) -> ExtractionResult:
        """Run extraction stage."""
        logger.info("Running extraction for %s", epub_path.name)

        await self._checkpoint_manager.update_job_stage(
            epub_id, self._config.target_language, JobStage.EXTRACTING
        )

        worker = ExtractionWorker()
        extraction_input = ExtractionInput(
            epub_id=epub_id,
            epub_path=epub_path,
            source_language=self._config.source_language,
        )

        result = worker.process(extraction_input)

        # Save checkpoint
        await self._checkpoint_manager.save_extraction(result)

        logger.info(
            "Extraction complete: %d XHTMLs, %d text units",
            len(result.xhtml_extractions),
            sum(len(x.text_units) for x in result.xhtml_extractions),
        )

        return result

    async def _run_preprocessing(
        self,
        epub_id: str,
        extraction_result: ExtractionResult,
    ) -> PreprocessResult:
        """Run preprocessing stage."""
        logger.info("Running preprocessing for %s", epub_id)

        await self._checkpoint_manager.update_job_stage(
            epub_id, self._config.target_language, JobStage.PREPROCESSING
        )

        worker = PreprocessWorker(self._api_client)
        preprocess_input = PreprocessInput(
            extraction_result=extraction_result,
            target_language=self._config.target_language,
            chunk_size=self._config.chunk_size,
        )

        result = await worker.process(preprocess_input)

        # Save checkpoint
        await self._checkpoint_manager.save_preprocess(result, self._config.target_language)

        logger.info(
            "Preprocessing complete: %d terms, %d summaries",
            len(result.term_dictionary.mappings),
            len(result.summaries),
        )

        return result

    async def _run_translation(
        self,
        epub_id: str,
        extraction_result: ExtractionResult,
        preprocess_result: PreprocessResult,
        already_translated: set[str],
    ) -> list[TranslationResult]:
        """
        Run translation stage.

        Supports resuming from partial translation.
        """
        logger.info("Running translation for %s", epub_id)

        lang = self._config.target_language

        # Filter out already translated XHTMLs
        xhtmls_to_translate = [
            xhtml for xhtml in extraction_result.xhtml_extractions
            if xhtml.xhtml_id not in already_translated
        ]

        total = len(extraction_result.xhtml_extractions)
        completed = len(already_translated)

        await self._checkpoint_manager.update_job_stage(
            epub_id, lang, JobStage.TRANSLATING, total=total, completed=completed
        )

        if not xhtmls_to_translate:
            logger.info("All XHTMLs already translated")
            return await self._checkpoint_manager.load_all_translations(epub_id, lang)

        logger.info(
            "Translating %d XHTMLs (%d already done)",
            len(xhtmls_to_translate),
            len(already_translated),
        )

        worker = TranslationWorker(self._api_client)
        results: list[TranslationResult] = []

        for xhtml in xhtmls_to_translate:
            # Skip XHTMLs with no text units
            if not xhtml.text_units:
                continue

            # Get summary for this XHTML
            xhtml_summary = preprocess_result.summaries.get(xhtml.xhtml_id, "")
            context_summary = xhtml_summary or preprocess_result.epub_summary

            task = TranslationTask(
                epub_id=epub_id,
                xhtml_id=xhtml.xhtml_id,
                target_language=lang,
                text_units=xhtml.text_units,
            )

            translation_input = TranslationInput(
                task=task,
                source_language=self._config.source_language,
                term_dictionary=preprocess_result.term_dictionary,
                context_summary=context_summary,
                batch_size=self._config.batch_size,
                max_concurrent=self._config.max_concurrent,
            )

            result = await worker.process(translation_input)
            results.append(result)

            # Save checkpoint after each XHTML
            await self._checkpoint_manager.save_translation(result)

            # Update progress
            await self._checkpoint_manager.increment_job_progress(
                epub_id, lang, JobStage.TRANSLATING
            )

            logger.debug("Translated XHTML %s: %d units", xhtml.xhtml_id, len(result.translated_units))

        logger.info("Translation complete: %d XHTMLs translated", len(results))

        return results

    async def _run_insertion(
        self,
        epub_id: str,
        epub_path: Path,
        extraction_result: ExtractionResult,
        translation_results: list[TranslationResult],
    ) -> InsertionResult:
        """Run insertion stage."""
        logger.info("Running insertion for %s", epub_id)

        lang = self._config.target_language

        await self._checkpoint_manager.update_job_stage(
            epub_id, lang, JobStage.INSERTING, total=1, completed=0
        )

        worker = InsertionWorker()
        insertion_input = InsertionInput(
            epub_id=epub_id,
            epub_path=epub_path,
            target_language=lang,
            extraction_result=extraction_result,
            translation_results=translation_results,
            output_dir=self._config.output_dir,
        )

        result = worker.process(insertion_input)

        await self._checkpoint_manager.update_job_stage(
            epub_id, lang, JobStage.INSERTING, completed=1
        )

        logger.info("Insertion complete: %s (success=%s)", result.output_path, result.success)

        return result

    def _generate_epub_id(self, epub_path: Path) -> str:
        """
        Generate unique ID for an EPUB file.

        Uses file name and size for identification.
        """
        stat = epub_path.stat()
        combined = f"{epub_path.name}:{stat.st_size}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    async def get_job_status(self, epub_path: Path):
        """
        Get current job status for an EPUB.

        Args:
            epub_path: Path to the EPUB file.

        Returns:
            JobStatus if exists, None otherwise.
        """
        if not self._initialized:
            raise RuntimeError("Orchestrator not initialized. Call initialize() first.")

        epub_id = self._generate_epub_id(epub_path)
        return await self._checkpoint_manager.get_job_status(
            epub_id, self._config.target_language
        )

    async def clear_job(self, epub_path: Path) -> int:
        """
        Clear all checkpoints for an EPUB.

        Args:
            epub_path: Path to the EPUB file.

        Returns:
            Number of keys deleted.
        """
        if not self._initialized:
            raise RuntimeError("Orchestrator not initialized. Call initialize() first.")

        epub_id = self._generate_epub_id(epub_path)
        return await self._checkpoint_manager.clear_job(
            epub_id, self._config.target_language
        )
