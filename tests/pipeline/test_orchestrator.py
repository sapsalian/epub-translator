"""Tests for PipelineOrchestrator."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.pipeline.config import PipelineConfig
from src.pipeline.models import (
    ExtractionResult,
    InsertionResult,
    Language,
    PreprocessResult,
    TermDictionary,
    TranslatedUnit,
    TranslationResult,
    XhtmlExtraction,
)
from src.pipeline.orchestrator import PipelineOrchestrator
from src.pipeline.persistence import JobStage


@pytest.fixture
def config(tmp_path):
    """Create a test config with temporary directories."""
    return PipelineConfig(
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        output_dir=tmp_path / "output",
        checkpoint_dir=tmp_path / "checkpoints",
    )


@pytest.fixture
def sample_extraction():
    """Sample ExtractionResult for testing."""
    return ExtractionResult(
        epub_id="test-epub",
        source_language=Language.ENGLISH,
        xhtml_extractions=[
            XhtmlExtraction(
                xhtml_id="xhtml001",
                xhtml_path="OEBPS/chapter1.xhtml",
                text_units=[],
                raw_text="Chapter 1",
            ),
        ],
    )


@pytest.fixture
def sample_preprocess():
    """Sample PreprocessResult for testing."""
    return PreprocessResult(
        epub_id="test-epub",
        term_dictionary=TermDictionary(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            mappings=[],
        ),
        summaries={},
        epub_summary="Test summary",
    )


@pytest.fixture
def sample_translation():
    """Sample TranslationResult for testing."""
    return TranslationResult(
        epub_id="test-epub",
        xhtml_id="xhtml001",
        target_language=Language.KOREAN,
        translated_units=[],
    )


@pytest.fixture
def sample_insertion():
    """Sample InsertionResult for testing."""
    return InsertionResult(
        epub_id="test-epub",
        target_language=Language.KOREAN,
        output_path="/tmp/test_ko.epub",
        success=True,
        errors=[],
    )


class TestPipelineOrchestratorInit:
    """Tests for orchestrator initialization."""

    def test_init(self, config):
        """Orchestrator can be initialized with config."""
        orchestrator = PipelineOrchestrator(config)
        assert orchestrator._config == config
        assert not orchestrator._initialized

    @pytest.mark.asyncio
    async def test_initialize(self, config):
        """initialize sets up backend services."""
        orchestrator = PipelineOrchestrator(config)

        with patch("src.pipeline.orchestrator.OpenAIClient"):
            await orchestrator.initialize()

        assert orchestrator._initialized
        assert orchestrator._api_client is not None
        assert orchestrator._checkpoint_manager is not None
        assert config.output_dir.exists()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, config):
        """initialize can be called multiple times safely."""
        orchestrator = PipelineOrchestrator(config)

        with patch("src.pipeline.orchestrator.OpenAIClient"):
            await orchestrator.initialize()
            await orchestrator.initialize()  # Should not raise

        assert orchestrator._initialized

    @pytest.mark.asyncio
    async def test_run_without_initialize_raises(self, config, tmp_path):
        """run raises if not initialized."""
        orchestrator = PipelineOrchestrator(config)
        epub_path = tmp_path / "test.epub"
        epub_path.touch()

        with pytest.raises(RuntimeError, match="not initialized"):
            await orchestrator.run(epub_path)


class TestEpubIdGeneration:
    """Tests for EPUB ID generation."""

    def test_generate_epub_id(self, config, tmp_path):
        """EPUB ID is generated from file name and size."""
        orchestrator = PipelineOrchestrator(config)

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(b"test content")

        epub_id = orchestrator._generate_epub_id(epub_path)
        assert isinstance(epub_id, str)
        assert len(epub_id) == 16  # SHA256 truncated to 16 chars

    def test_generate_epub_id_different_files(self, config, tmp_path):
        """Different files get different IDs."""
        orchestrator = PipelineOrchestrator(config)

        epub1 = tmp_path / "test1.epub"
        epub1.write_bytes(b"content1")

        epub2 = tmp_path / "test2.epub"
        epub2.write_bytes(b"content2")

        id1 = orchestrator._generate_epub_id(epub1)
        id2 = orchestrator._generate_epub_id(epub2)

        assert id1 != id2

    def test_generate_epub_id_same_file_same_id(self, config, tmp_path):
        """Same file generates same ID."""
        orchestrator = PipelineOrchestrator(config)

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(b"content")

        id1 = orchestrator._generate_epub_id(epub_path)
        id2 = orchestrator._generate_epub_id(epub_path)

        assert id1 == id2


class TestBatchProcessing:
    """Tests for batch processing."""

    @pytest.mark.asyncio
    async def test_run_batch_sequential(self, config, tmp_path):
        """run_batch processes EPUBs sequentially by default."""
        orchestrator = PipelineOrchestrator(config)

        # Create test EPUBs
        epub1 = tmp_path / "book1.epub"
        epub2 = tmp_path / "book2.epub"
        epub1.write_bytes(b"content1")
        epub2.write_bytes(b"content2")

        # Mock the run method
        mock_result = InsertionResult(
            epub_id="test",
            target_language=Language.KOREAN,
            output_path="/tmp/out.epub",
            success=True,
            errors=[],
        )

        with patch("src.pipeline.orchestrator.OpenAIClient"):
            await orchestrator.initialize()

        orchestrator.run = AsyncMock(return_value=mock_result)

        results = await orchestrator.run_batch([epub1, epub2])

        assert len(results) == 2
        assert orchestrator.run.call_count == 2

    @pytest.mark.asyncio
    async def test_run_batch_parallel(self, config, tmp_path):
        """run_batch can process EPUBs in parallel."""
        orchestrator = PipelineOrchestrator(config)

        epub1 = tmp_path / "book1.epub"
        epub2 = tmp_path / "book2.epub"
        epub1.write_bytes(b"content1")
        epub2.write_bytes(b"content2")

        mock_result = InsertionResult(
            epub_id="test",
            target_language=Language.KOREAN,
            output_path="/tmp/out.epub",
            success=True,
            errors=[],
        )

        with patch("src.pipeline.orchestrator.OpenAIClient"):
            await orchestrator.initialize()

        orchestrator.run = AsyncMock(return_value=mock_result)

        results = await orchestrator.run_batch([epub1, epub2], parallel=True)

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_run_batch_without_initialize_raises(self, config, tmp_path):
        """run_batch raises if not initialized."""
        orchestrator = PipelineOrchestrator(config)

        epub_path = tmp_path / "test.epub"
        epub_path.touch()

        with pytest.raises(RuntimeError, match="not initialized"):
            await orchestrator.run_batch([epub_path])


class TestJobManagement:
    """Tests for job status management."""

    @pytest.mark.asyncio
    async def test_get_job_status(self, config, tmp_path):
        """get_job_status returns job status."""
        orchestrator = PipelineOrchestrator(config)

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(b"content")

        with patch("src.pipeline.orchestrator.OpenAIClient"):
            await orchestrator.initialize()

        # No job exists yet
        status = await orchestrator.get_job_status(epub_path)
        assert status is None

    @pytest.mark.asyncio
    async def test_clear_job(self, config, tmp_path):
        """clear_job removes job data."""
        orchestrator = PipelineOrchestrator(config)

        epub_path = tmp_path / "test.epub"
        epub_path.write_bytes(b"content")

        with patch("src.pipeline.orchestrator.OpenAIClient"):
            await orchestrator.initialize()

        # Clear should work even if no job exists
        count = await orchestrator.clear_job(epub_path)
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_job_status_without_initialize_raises(self, config, tmp_path):
        """get_job_status raises if not initialized."""
        orchestrator = PipelineOrchestrator(config)

        epub_path = tmp_path / "test.epub"
        epub_path.touch()

        with pytest.raises(RuntimeError, match="not initialized"):
            await orchestrator.get_job_status(epub_path)


class TestStyleGuidelines:
    """Tests for style guideline composition."""

    def test_compose_style_guidelines(self, config):
        """Compose uses XHTML style, falls back to EPUB style, adds custom instructions."""
        config.custom_instructions = "Prefer concise sentences."
        orchestrator = PipelineOrchestrator(config)

        combined = orchestrator._compose_style_guidelines(
            xhtml_style="Use present tense.",
            epub_style="Third-person limited.",
            custom_instructions=config.custom_instructions,
        )

        assert "XHTML Style Notes" in combined
        assert "Custom Instructions" in combined
        assert "Use present tense." in combined
        assert "Prefer concise sentences." in combined

        combined_fallback = orchestrator._compose_style_guidelines(
            xhtml_style="",
            epub_style="Third-person limited.",
            custom_instructions="",
        )

        assert "EPUB Style Guide" in combined_fallback
        assert "Third-person limited." in combined_fallback
