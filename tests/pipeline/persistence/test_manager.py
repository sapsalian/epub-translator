"""Tests for CheckpointManager."""

import pytest
import pytest_asyncio
import tempfile

from src.pipeline.models import (
    ExtractionResult,
    Language,
    PreprocessResult,
    TermDictionary,
    TranslationResult,
    TranslatedUnit,
    XhtmlExtraction,
)
from src.pipeline.persistence import (
    CheckpointManager,
    FilePersistenceBackend,
    JobStage,
)


@pytest_asyncio.fixture
async def manager():
    """Create a CheckpointManager with temporary file backend."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = FilePersistenceBackend(tmpdir)
        await backend.initialize()
        yield CheckpointManager(backend)


@pytest.fixture
def sample_extraction():
    """Sample ExtractionResult for testing."""
    return ExtractionResult(
        epub_id="test-epub-123",
        source_language=Language.ENGLISH,
        xhtml_extractions=[
            XhtmlExtraction(
                xhtml_id="xhtml001",
                xhtml_path="OEBPS/chapter1.xhtml",
                text_units=[],
                raw_text="Chapter 1 content",
            ),
            XhtmlExtraction(
                xhtml_id="xhtml002",
                xhtml_path="OEBPS/chapter2.xhtml",
                text_units=[],
                raw_text="Chapter 2 content",
            ),
        ],
    )


@pytest.fixture
def sample_preprocess():
    """Sample PreprocessResult for testing."""
    return PreprocessResult(
        epub_id="test-epub-123",
        term_dictionary=TermDictionary(
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            mappings=[],
        ),
        summaries={"xhtml001": "Chapter 1 summary"},
        epub_summary="Overall summary",
    )


@pytest.fixture
def sample_translation():
    """Sample TranslationResult for testing."""
    return TranslationResult(
        epub_id="test-epub-123",
        xhtml_id="xhtml001",
        target_language=Language.KOREAN,
        translated_units=[
            TranslatedUnit(unit_id="unit001", translated_text="번역된 텍스트"),
        ],
    )


class TestExtractionCheckpoint:
    """Tests for extraction checkpoint operations."""

    @pytest.mark.asyncio
    async def test_save_and_load_extraction(
        self, manager: CheckpointManager, sample_extraction: ExtractionResult
    ):
        """Extraction result can be saved and loaded."""
        await manager.save_extraction(sample_extraction)
        loaded = await manager.load_extraction(sample_extraction.epub_id)

        assert loaded is not None
        assert loaded.epub_id == sample_extraction.epub_id
        assert loaded.source_language == sample_extraction.source_language
        assert len(loaded.xhtml_extractions) == 2

    @pytest.mark.asyncio
    async def test_load_nonexistent_extraction(self, manager: CheckpointManager):
        """Loading nonexistent extraction returns None."""
        loaded = await manager.load_extraction("nonexistent")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_has_extraction(
        self, manager: CheckpointManager, sample_extraction: ExtractionResult
    ):
        """has_extraction returns correct values."""
        assert await manager.has_extraction(sample_extraction.epub_id) is False
        await manager.save_extraction(sample_extraction)
        assert await manager.has_extraction(sample_extraction.epub_id) is True


class TestPreprocessCheckpoint:
    """Tests for preprocess checkpoint operations."""

    @pytest.mark.asyncio
    async def test_save_and_load_preprocess(
        self, manager: CheckpointManager, sample_preprocess: PreprocessResult
    ):
        """Preprocess result can be saved and loaded."""
        lang = Language.KOREAN
        await manager.save_preprocess(sample_preprocess, lang)
        loaded = await manager.load_preprocess(sample_preprocess.epub_id, lang)

        assert loaded is not None
        assert loaded.epub_id == sample_preprocess.epub_id
        assert loaded.epub_summary == "Overall summary"

    @pytest.mark.asyncio
    async def test_preprocess_per_language(
        self, manager: CheckpointManager, sample_preprocess: PreprocessResult
    ):
        """Preprocess results are stored per language."""
        await manager.save_preprocess(sample_preprocess, Language.KOREAN)

        # Different language returns None
        loaded_ja = await manager.load_preprocess(
            sample_preprocess.epub_id, Language.JAPANESE
        )
        assert loaded_ja is None

        # Same language works
        loaded_ko = await manager.load_preprocess(
            sample_preprocess.epub_id, Language.KOREAN
        )
        assert loaded_ko is not None


class TestTranslationCheckpoint:
    """Tests for translation checkpoint operations."""

    @pytest.mark.asyncio
    async def test_save_and_load_translation(
        self, manager: CheckpointManager, sample_translation: TranslationResult
    ):
        """Translation result can be saved and loaded."""
        await manager.save_translation(sample_translation)
        loaded = await manager.load_translation(
            sample_translation.epub_id,
            sample_translation.xhtml_id,
            sample_translation.target_language,
        )

        assert loaded is not None
        assert loaded.xhtml_id == sample_translation.xhtml_id
        assert len(loaded.translated_units) == 1

    @pytest.mark.asyncio
    async def test_get_translated_xhtml_ids(self, manager: CheckpointManager):
        """get_translated_xhtml_ids returns correct IDs."""
        epub_id = "test-epub"
        lang = Language.KOREAN

        # Save multiple translations
        for xhtml_id in ["xhtml001", "xhtml002", "xhtml003"]:
            result = TranslationResult(
                epub_id=epub_id,
                xhtml_id=xhtml_id,
                target_language=lang,
                translated_units=[],
            )
            await manager.save_translation(result)

        ids = await manager.get_translated_xhtml_ids(epub_id, lang)
        assert ids == {"xhtml001", "xhtml002", "xhtml003"}

    @pytest.mark.asyncio
    async def test_load_all_translations(self, manager: CheckpointManager):
        """load_all_translations returns all translations for epub and language."""
        epub_id = "test-epub"
        lang = Language.KOREAN

        # Save multiple translations
        for xhtml_id in ["xhtml001", "xhtml002"]:
            result = TranslationResult(
                epub_id=epub_id,
                xhtml_id=xhtml_id,
                target_language=lang,
                translated_units=[],
            )
            await manager.save_translation(result)

        # Also save for different language
        result_ja = TranslationResult(
            epub_id=epub_id,
            xhtml_id="xhtml001",
            target_language=Language.JAPANESE,
            translated_units=[],
        )
        await manager.save_translation(result_ja)

        # Load Korean translations
        results = await manager.load_all_translations(epub_id, lang)
        assert len(results) == 2
        xhtml_ids = {r.xhtml_id for r in results}
        assert xhtml_ids == {"xhtml001", "xhtml002"}


class TestJobStatus:
    """Tests for job status operations."""

    @pytest.mark.asyncio
    async def test_create_job(self, manager: CheckpointManager):
        """create_job creates and returns job status."""
        status = await manager.create_job("test-epub", Language.KOREAN, total_xhtmls=5)

        assert status.epub_id == "test-epub"
        assert status.stage == JobStage.PENDING
        assert status.extracting.total == 5

    @pytest.mark.asyncio
    async def test_update_job_stage(self, manager: CheckpointManager):
        """update_job_stage updates stage and progress."""
        await manager.create_job("test-epub", Language.KOREAN)

        updated = await manager.update_job_stage(
            "test-epub",
            Language.KOREAN,
            JobStage.TRANSLATING,
            total=10,
            completed=3,
        )

        assert updated is not None
        assert updated.stage == JobStage.TRANSLATING
        assert updated.translating.total == 10
        assert updated.translating.completed == 3

    @pytest.mark.asyncio
    async def test_increment_job_progress(self, manager: CheckpointManager):
        """increment_job_progress increases completed count."""
        await manager.create_job("test-epub", Language.KOREAN)
        await manager.update_job_stage(
            "test-epub", Language.KOREAN, JobStage.TRANSLATING, total=10
        )

        await manager.increment_job_progress(
            "test-epub", Language.KOREAN, JobStage.TRANSLATING, count=2
        )
        await manager.increment_job_progress(
            "test-epub", Language.KOREAN, JobStage.TRANSLATING, count=1
        )

        status = await manager.get_job_status("test-epub", Language.KOREAN)
        assert status is not None
        assert status.translating.completed == 3

    @pytest.mark.asyncio
    async def test_mark_job_failed(self, manager: CheckpointManager):
        """mark_job_failed sets error state."""
        await manager.create_job("test-epub", Language.KOREAN)

        updated = await manager.mark_job_failed(
            "test-epub", Language.KOREAN, "API error"
        )

        assert updated is not None
        assert updated.stage == JobStage.FAILED
        assert updated.error_message == "API error"

    @pytest.mark.asyncio
    async def test_mark_job_completed(self, manager: CheckpointManager):
        """mark_job_completed sets completed state."""
        await manager.create_job("test-epub", Language.KOREAN)

        updated = await manager.mark_job_completed("test-epub", Language.KOREAN)

        assert updated is not None
        assert updated.stage == JobStage.COMPLETED


class TestCleanup:
    """Tests for cleanup operations."""

    @pytest.mark.asyncio
    async def test_clear_job_all_languages(
        self,
        manager: CheckpointManager,
        sample_extraction: ExtractionResult,
        sample_preprocess: PreprocessResult,
    ):
        """clear_job with no language clears everything."""
        epub_id = sample_extraction.epub_id

        await manager.save_extraction(sample_extraction)
        await manager.save_preprocess(sample_preprocess, Language.KOREAN)
        await manager.create_job(epub_id, Language.KOREAN)

        count = await manager.clear_job(epub_id)
        assert count >= 3

        assert await manager.has_extraction(epub_id) is False
        assert await manager.get_job_status(epub_id, Language.KOREAN) is None

    @pytest.mark.asyncio
    async def test_clear_job_single_language(
        self,
        manager: CheckpointManager,
        sample_extraction: ExtractionResult,
        sample_preprocess: PreprocessResult,
    ):
        """clear_job with language clears only that language."""
        epub_id = sample_extraction.epub_id

        await manager.save_extraction(sample_extraction)
        await manager.save_preprocess(sample_preprocess, Language.KOREAN)
        await manager.create_job(epub_id, Language.KOREAN)

        count = await manager.clear_job(epub_id, Language.KOREAN)
        assert count >= 2

        # Extraction still exists (not language-specific)
        assert await manager.has_extraction(epub_id) is True
        # Korean data gone
        assert await manager.get_job_status(epub_id, Language.KOREAN) is None


class TestResumeSupport:
    """Tests for resume functionality."""

    @pytest.mark.asyncio
    async def test_get_resume_point_no_data(self, manager: CheckpointManager):
        """Resume point is EXTRACTING when no data exists."""
        stage, ids = await manager.get_resume_point("test-epub", Language.KOREAN)
        assert stage == JobStage.EXTRACTING
        assert ids == set()

    @pytest.mark.asyncio
    async def test_get_resume_point_after_extraction(
        self, manager: CheckpointManager, sample_extraction: ExtractionResult
    ):
        """Resume point is PREPROCESSING after extraction."""
        await manager.save_extraction(sample_extraction)

        stage, ids = await manager.get_resume_point(
            sample_extraction.epub_id, Language.KOREAN
        )
        assert stage == JobStage.PREPROCESSING
        assert ids == set()

    @pytest.mark.asyncio
    async def test_get_resume_point_partial_translation(
        self,
        manager: CheckpointManager,
        sample_extraction: ExtractionResult,
        sample_preprocess: PreprocessResult,
    ):
        """Resume point shows partial translation progress."""
        epub_id = sample_extraction.epub_id
        lang = Language.KOREAN

        await manager.save_extraction(sample_extraction)
        await manager.save_preprocess(sample_preprocess, lang)

        # Save one translation
        tr = TranslationResult(
            epub_id=epub_id,
            xhtml_id="xhtml001",
            target_language=lang,
            translated_units=[],
        )
        await manager.save_translation(tr)

        stage, ids = await manager.get_resume_point(epub_id, lang)
        assert stage == JobStage.TRANSLATING
        assert ids == {"xhtml001"}

    @pytest.mark.asyncio
    async def test_get_resume_point_all_translated(
        self,
        manager: CheckpointManager,
        sample_extraction: ExtractionResult,
        sample_preprocess: PreprocessResult,
    ):
        """Resume point is INSERTING when all translated."""
        epub_id = sample_extraction.epub_id
        lang = Language.KOREAN

        await manager.save_extraction(sample_extraction)
        await manager.save_preprocess(sample_preprocess, lang)

        # Save all translations
        for xhtml in sample_extraction.xhtml_extractions:
            tr = TranslationResult(
                epub_id=epub_id,
                xhtml_id=xhtml.xhtml_id,
                target_language=lang,
                translated_units=[],
            )
            await manager.save_translation(tr)

        stage, ids = await manager.get_resume_point(epub_id, lang)
        assert stage == JobStage.INSERTING
        assert len(ids) == 2
