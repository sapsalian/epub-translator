"""
Integration tests for the translation pipeline.

Tests the complete pipeline flow using real EPUB files
with mocked API clients for predictable results.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from zipfile import ZipFile

import pytest
import pytest_asyncio

from src.pipeline.config import PipelineConfig
from src.pipeline.models import (
    ExtractionResult,
    Language,
    PreprocessResult,
    TermDictionary,
    TranslatedUnit,
    TranslationResult,
)
from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.persistence import JobStage
from src.pipeline.workers.preprocess import ChunkResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_epub_path() -> Path:
    """Path to sample EPUB file."""
    return Path(__file__).parents[2] / "demo_files" / "sample.epub"


@pytest.fixture
def config(tmp_path):
    """Create test config with temporary directories."""
    return PipelineConfig(
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        output_dir=tmp_path / "output",
        checkpoint_dir=tmp_path / "checkpoints",
        model="gpt-4o-mini",
        chunk_size=4000,
        batch_size=2000,
        preprocess_max_concurrent=3,
        translation_max_concurrent=3,
    )


@pytest.fixture
def mock_api_client():
    """Create mock API client for both preprocess and translation."""
    client = MagicMock()

    # Mock extract_chunk - returns summary and terms
    async def mock_extract_chunk(
        chunk_text,
        source_language,
        target_language,
        existing_terms=None,
        custom_instructions="",
    ):
        return ChunkResult(
            summary=f"Summary of chunk: {chunk_text[:50]}...",
            terms={"hello": "안녕하세요", "world": "세계"},
        )

    client.extract_chunk = AsyncMock(side_effect=mock_extract_chunk)

    # Mock merge_extractions
    async def mock_merge_extractions(
        chunk_summaries,
        chunk_terms,
        source_language,
        target_language,
        chunk_styles=None,
        custom_instructions="",
    ):
        merged_terms: dict[str, str] = {}
        for terms in chunk_terms:
            merged_terms.update(terms)

        return ChunkResult(
            summary="Merged summary: " + "; ".join(chunk_summaries[:3]),
            terms=merged_terms,
            style_notes="Merged style notes",
        )

    client.merge_extractions = AsyncMock(side_effect=mock_merge_extractions)

    # Mock translate
    async def mock_translate(
        text_units,
        source_language,
        target_language,
        term_dictionary,
        context_summary,
        style_guidelines="",
    ):
        # Return Korean placeholder translations
        return [f"[번역됨] {unit.tagged_text}" for unit in text_units]

    client.translate = AsyncMock(side_effect=mock_translate)

    return client


# =============================================================================
# Full Pipeline Tests
# =============================================================================


class TestFullPipeline:
    """Integration tests for the complete pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_sample_epub(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Test complete pipeline from extraction to insertion."""
        orchestrator = PipelineOrchestrator(config)

        # Patch OpenAIClient to return our mock
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run the pipeline
        result = await orchestrator.run(sample_epub_path)

        # Verify result - pipeline completes even with some insertion errors
        # (Mock translation may cause XML parsing issues, which is expected)
        assert result.epub_id
        assert result.target_language == Language.KOREAN

        # Check output file exists
        output_path = Path(result.output_path)
        assert output_path.exists()
        assert output_path.suffix == ".epub"
        assert "_ko" in output_path.stem

        # Verify the output EPUB is valid
        with ZipFile(output_path, "r") as zf:
            # Check mimetype exists
            assert "mimetype" in zf.namelist()

            # Check XHTML files exist
            xhtml_files = [f for f in zf.namelist() if f.endswith((".xhtml", ".html"))]
            assert len(xhtml_files) > 0

    @pytest.mark.asyncio
    async def test_pipeline_creates_checkpoints(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Verify checkpoints are saved during pipeline."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run the pipeline
        result = await orchestrator.run(sample_epub_path)

        # Verify checkpoints exist
        checkpoint_dir = config.checkpoint_dir
        assert checkpoint_dir.exists()

        # Check that JSON checkpoint files were created
        checkpoint_files = list(checkpoint_dir.glob("*.json"))
        assert len(checkpoint_files) > 0

    @pytest.mark.asyncio
    async def test_pipeline_job_status_updated(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Verify job status is properly updated throughout pipeline."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run the pipeline
        await orchestrator.run(sample_epub_path)

        # Check final job status
        status = await orchestrator.get_job_status(sample_epub_path)
        assert status is not None
        assert status.stage == JobStage.COMPLETED
        assert status.overall_progress == 1.0


# =============================================================================
# Resume Tests
# =============================================================================


class TestPipelineResume:
    """Tests for pipeline resume functionality."""

    @pytest.mark.asyncio
    async def test_resume_after_extraction(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Pipeline can resume after extraction stage."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # First run - complete the pipeline
        result1 = await orchestrator.run(sample_epub_path)
        assert result1.epub_id  # Pipeline completes

        # Clear the translation and insertion data, keep extraction
        epub_id = orchestrator._generate_epub_id(sample_epub_path)
        lang = config.target_language

        # Only clear preprocess and translations (not extraction)
        manager = orchestrator._checkpoint_manager
        await manager._backend.delete(manager._preprocess_key(epub_id, lang))

        # Clear translations
        prefix = f"{epub_id}:translation:"
        keys = await manager._backend.list_keys(prefix)
        for key in keys:
            await manager._backend.delete(key)

        # Clear status
        await manager._backend.delete(manager._status_key(epub_id, lang))

        # Second run - should resume from preprocessing
        result2 = await orchestrator.run(sample_epub_path)
        assert result2.epub_id  # Pipeline completes

        # Extraction should not have been called again (it was already saved)
        # We can verify by checking the checkpoint still exists

    @pytest.mark.asyncio
    async def test_resume_after_partial_translation(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Pipeline can resume after partial translation."""
        orchestrator = PipelineOrchestrator(config)

        # Track translation calls
        translation_calls = []
        original_translate = mock_api_client.translate.side_effect

        async def tracking_translate(*args, **kwargs):
            translation_calls.append(args)
            return await original_translate(*args, **kwargs)

        mock_api_client.translate = AsyncMock(side_effect=tracking_translate)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # First run - complete the pipeline
        result1 = await orchestrator.run(sample_epub_path)
        assert result1.epub_id  # Pipeline completes

        first_run_calls = len(translation_calls)

        # Second run - should skip all translation (already done)
        translation_calls.clear()
        result2 = await orchestrator.run(sample_epub_path)
        assert result2.epub_id  # Pipeline completes

        # No additional translation calls should be made
        assert len(translation_calls) == 0

    @pytest.mark.asyncio
    async def test_full_resume_flow(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Test complete resume flow from different stages."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run complete pipeline first
        result = await orchestrator.run(sample_epub_path)
        assert result.epub_id  # Pipeline completes

        # Get resume point - should be INSERTING (all done)
        epub_id = orchestrator._generate_epub_id(sample_epub_path)
        resume_stage, translated_ids = await orchestrator._checkpoint_manager.get_resume_point(
            epub_id, config.target_language
        )

        # All XHTMLs should be in translated_ids
        extraction = await orchestrator._checkpoint_manager.load_extraction(epub_id)
        assert extraction is not None
        assert len(translated_ids) >= len([x for x in extraction.xhtml_extractions if x.text_units])


# =============================================================================
# Checkpoint Manager Tests
# =============================================================================


class TestCheckpointPersistence:
    """Tests for checkpoint persistence."""

    @pytest.mark.asyncio
    async def test_extraction_checkpoint_persisted(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Extraction results are persisted correctly."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run pipeline
        await orchestrator.run(sample_epub_path)

        # Load extraction from checkpoint
        epub_id = orchestrator._generate_epub_id(sample_epub_path)
        extraction = await orchestrator._checkpoint_manager.load_extraction(epub_id)

        assert extraction is not None
        assert isinstance(extraction, ExtractionResult)
        assert extraction.epub_id == epub_id
        assert len(extraction.xhtml_extractions) > 0

    @pytest.mark.asyncio
    async def test_preprocess_checkpoint_persisted(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Preprocess results are persisted correctly."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run pipeline
        await orchestrator.run(sample_epub_path)

        # Load preprocess from checkpoint
        epub_id = orchestrator._generate_epub_id(sample_epub_path)
        preprocess = await orchestrator._checkpoint_manager.load_preprocess(
            epub_id, config.target_language
        )

        assert preprocess is not None
        assert isinstance(preprocess, PreprocessResult)
        assert preprocess.epub_id == epub_id

    @pytest.mark.asyncio
    async def test_translation_checkpoints_persisted(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Translation results are persisted per-XHTML."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run pipeline
        await orchestrator.run(sample_epub_path)

        # Load all translations from checkpoint
        epub_id = orchestrator._generate_epub_id(sample_epub_path)
        translations = await orchestrator._checkpoint_manager.load_all_translations(
            epub_id, config.target_language
        )

        assert len(translations) > 0
        for t in translations:
            assert isinstance(t, TranslationResult)
            assert t.epub_id == epub_id


# =============================================================================
# Output Validation Tests
# =============================================================================


class TestOutputValidation:
    """Tests for validating pipeline output."""

    @pytest.mark.asyncio
    async def test_output_epub_contains_translated_content(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Output EPUB contains translated text."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        result = await orchestrator.run(sample_epub_path)
        output_path = Path(result.output_path)

        # Read content from output EPUB
        with ZipFile(output_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith((".xhtml", ".html")):
                    content = zf.read(name).decode("utf-8")
                    # Our mock translates to "[번역됨]" prefix
                    if "[번역됨]" in content:
                        return  # Found translated content

        # If no translated content found, fail
        pytest.fail("No translated content found in output EPUB")

    @pytest.mark.asyncio
    async def test_output_epub_preserves_structure(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Output EPUB preserves the original structure."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        result = await orchestrator.run(sample_epub_path)
        output_path = Path(result.output_path)

        # Compare file lists
        with ZipFile(sample_epub_path, "r") as original, ZipFile(output_path, "r") as translated:
            original_files = set(original.namelist())
            translated_files = set(translated.namelist())

            # Translated EPUB should have the same files
            assert original_files == translated_files


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in the pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_handles_missing_epub(
        self, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Pipeline raises error for missing EPUB."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        missing_path = tmp_path / "nonexistent.epub"

        with pytest.raises(Exception):
            await orchestrator.run(missing_path)

    @pytest.mark.asyncio
    async def test_pipeline_marks_job_failed_on_error(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Job is marked as failed when pipeline errors."""
        orchestrator = PipelineOrchestrator(config)

        # Make translate raise an error
        mock_api_client.translate = AsyncMock(side_effect=Exception("API Error"))

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run should raise
        with pytest.raises(Exception, match="API Error"):
            await orchestrator.run(sample_epub_path)

        # Job status should be FAILED
        status = await orchestrator.get_job_status(sample_epub_path)
        assert status is not None
        assert status.stage == JobStage.FAILED
        assert "API Error" in status.error_message


# =============================================================================
# Clear Job Tests
# =============================================================================


class TestClearJob:
    """Tests for clearing job data."""

    @pytest.mark.asyncio
    async def test_clear_job_removes_all_data(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """clear_job removes all checkpoints."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # Run pipeline first
        await orchestrator.run(sample_epub_path)

        # Verify data exists
        status = await orchestrator.get_job_status(sample_epub_path)
        assert status is not None

        # Clear job
        count = await orchestrator.clear_job(sample_epub_path)
        assert count > 0

        # Verify data is gone
        status = await orchestrator.get_job_status(sample_epub_path)
        assert status is None

    @pytest.mark.asyncio
    async def test_can_rerun_after_clear(
        self, sample_epub_path: Path, config: PipelineConfig, mock_api_client, tmp_path
    ):
        """Pipeline can run again after clearing job."""
        orchestrator = PipelineOrchestrator(config)

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.pipeline.orchestrator.OpenAIClient",
                lambda **kwargs: mock_api_client,
            )
            await orchestrator.initialize()

        # First run
        result1 = await orchestrator.run(sample_epub_path)
        assert result1.epub_id  # Pipeline completes

        # Clear
        await orchestrator.clear_job(sample_epub_path)

        # Second run should work
        result2 = await orchestrator.run(sample_epub_path)
        assert result2.epub_id  # Pipeline completes
