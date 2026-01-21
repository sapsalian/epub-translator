"""Tests for PreprocessWorker."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.pipeline.models import (
    ExtractionResult,
    Language,
    PreprocessResult,
    TermCandidate,
    TermMapping,
    TextLocation,
    TextUnit,
    XhtmlExtraction,
)
from src.pipeline.workers.base import PreprocessError
from src.pipeline.workers.preprocess import (
    PreprocessAPIClient,
    PreprocessInput,
    PreprocessWorker,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Create a mock API client."""
    client = AsyncMock(spec=PreprocessAPIClient)
    client.generate_term_dictionary.return_value = [
        TermMapping(source="hello", target="안녕하세요"),
        TermMapping(source="world", target="세계"),
    ]
    client.generate_summary.return_value = "This is a summary."
    return client


@pytest.fixture
def sample_extraction_result() -> ExtractionResult:
    """Create a sample extraction result."""
    return ExtractionResult(
        epub_id="test-epub-001",
        source_language=Language.ENGLISH,
        xhtml_extractions=[
            XhtmlExtraction(
                xhtml_id="xhtml-001",
                xhtml_path="OEBPS/chapter1.xhtml",
                text_units=[
                    TextUnit(
                        unit_id="unit-001",
                        location=TextLocation(
                            xhtml_path="OEBPS/chapter1.xhtml",
                            xpath="/html/body/p[1]",
                        ),
                        source_text="Hello world",
                        tagged_text="Hello world",
                        inner_tags=[],
                    ),
                ],
                raw_text="Hello world. This is chapter one.",
            ),
            XhtmlExtraction(
                xhtml_id="xhtml-002",
                xhtml_path="OEBPS/chapter2.xhtml",
                text_units=[
                    TextUnit(
                        unit_id="unit-002",
                        location=TextLocation(
                            xhtml_path="OEBPS/chapter2.xhtml",
                            xpath="/html/body/p[1]",
                        ),
                        source_text="Goodbye world",
                        tagged_text="Goodbye world",
                        inner_tags=[],
                    ),
                ],
                raw_text="Goodbye world. This is chapter two.",
            ),
        ],
        term_candidates=[
            TermCandidate(term="hello", frequency=5),
            TermCandidate(term="world", frequency=10),
        ],
    )


@pytest.fixture
def preprocess_input(sample_extraction_result: ExtractionResult) -> PreprocessInput:
    """Create preprocess input."""
    return PreprocessInput(
        extraction_result=sample_extraction_result,
        target_language=Language.KOREAN,
    )


@pytest.fixture
def worker(mock_api_client: AsyncMock) -> PreprocessWorker:
    """Create PreprocessWorker with mock client."""
    return PreprocessWorker(api_client=mock_api_client)


# =============================================================================
# Basic Tests
# =============================================================================


class TestPreprocessWorkerBasic:
    """Basic tests for PreprocessWorker."""

    def test_worker_has_logger(self, worker: PreprocessWorker):
        """Worker has logger attribute."""
        assert hasattr(worker, "logger")

    def test_worker_repr(self, worker: PreprocessWorker):
        """Worker has readable repr."""
        assert repr(worker) == "PreprocessWorker()"


class TestPreprocessInput:
    """Tests for PreprocessInput model."""

    def test_input_fields(self, sample_extraction_result: ExtractionResult):
        """Input has required fields."""
        input_data = PreprocessInput(
            extraction_result=sample_extraction_result,
            target_language=Language.KOREAN,
        )
        assert input_data.extraction_result.epub_id == "test-epub-001"
        assert input_data.target_language == Language.KOREAN


# =============================================================================
# Processing Tests
# =============================================================================


class TestPreprocessing:
    """Tests for preprocessing functionality."""

    def test_generates_preprocess_result(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
    ):
        """Processing produces PreprocessResult."""
        result = asyncio.run(worker.process(preprocess_input))

        assert isinstance(result, PreprocessResult)
        assert result.epub_id == "test-epub-001"

    def test_generates_term_dictionary(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
        mock_api_client: AsyncMock,
    ):
        """Processing generates term dictionary."""
        result = asyncio.run(worker.process(preprocess_input))

        assert result.term_dictionary.source_language == Language.ENGLISH
        assert result.term_dictionary.target_language == Language.KOREAN
        assert len(result.term_dictionary.mappings) == 2

        mock_api_client.generate_term_dictionary.assert_called_once()

    def test_generates_summaries(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
        mock_api_client: AsyncMock,
    ):
        """Processing generates summaries for each XHTML."""
        result = asyncio.run(worker.process(preprocess_input))

        assert len(result.summaries) == 2
        assert "xhtml-001" in result.summaries
        assert "xhtml-002" in result.summaries

        # Called once per XHTML with raw_text
        assert mock_api_client.generate_summary.call_count == 2

    def test_skips_empty_xhtml_for_summary(
        self,
        mock_api_client: AsyncMock,
    ):
        """Empty XHTML raw_text is skipped for summary generation."""
        extraction = ExtractionResult(
            epub_id="test",
            source_language=Language.ENGLISH,
            xhtml_extractions=[
                XhtmlExtraction(
                    xhtml_id="xhtml-001",
                    xhtml_path="chapter1.xhtml",
                    text_units=[],
                    raw_text="Some content",
                ),
                XhtmlExtraction(
                    xhtml_id="xhtml-002",
                    xhtml_path="chapter2.xhtml",
                    text_units=[],
                    raw_text="   ",  # Whitespace only
                ),
            ],
            term_candidates=[],
        )
        input_data = PreprocessInput(
            extraction_result=extraction,
            target_language=Language.KOREAN,
        )
        worker = PreprocessWorker(api_client=mock_api_client)

        result = asyncio.run(worker.process(input_data))

        # Only one summary generated (for non-empty xhtml)
        assert len(result.summaries) == 1
        assert "xhtml-001" in result.summaries
        assert mock_api_client.generate_summary.call_count == 1

    def test_empty_extraction_produces_empty_result(
        self,
        mock_api_client: AsyncMock,
    ):
        """Empty extraction produces empty term dictionary and summaries."""
        extraction = ExtractionResult(
            epub_id="empty-epub",
            source_language=Language.ENGLISH,
            xhtml_extractions=[],
            term_candidates=[],
        )
        input_data = PreprocessInput(
            extraction_result=extraction,
            target_language=Language.KOREAN,
        )
        worker = PreprocessWorker(api_client=mock_api_client)

        result = asyncio.run(worker.process(input_data))

        assert result.epub_id == "empty-epub"
        assert len(result.term_dictionary.mappings) == 0
        assert len(result.summaries) == 0

        # API not called for empty content
        mock_api_client.generate_term_dictionary.assert_not_called()
        mock_api_client.generate_summary.assert_not_called()


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_api_error_raises_preprocess_error(
        self,
        preprocess_input: PreprocessInput,
    ):
        """API errors are wrapped in PreprocessError."""
        failing_client = AsyncMock(spec=PreprocessAPIClient)
        failing_client.generate_term_dictionary.side_effect = Exception("API failed")

        worker = PreprocessWorker(api_client=failing_client)

        with pytest.raises(PreprocessError, match="API failed"):
            asyncio.run(worker.process(preprocess_input))

    def test_summary_api_error_raises_preprocess_error(
        self,
        preprocess_input: PreprocessInput,
        mock_api_client: AsyncMock,
    ):
        """Summary API errors are wrapped in PreprocessError."""
        mock_api_client.generate_summary.side_effect = Exception("Summary failed")

        worker = PreprocessWorker(api_client=mock_api_client)

        with pytest.raises(PreprocessError, match="Summary failed"):
            asyncio.run(worker.process(preprocess_input))


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for result serialization."""

    def test_result_to_json(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
    ):
        """PreprocessResult can be serialized to JSON."""
        result = asyncio.run(worker.process(preprocess_input))

        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert "test-epub-001" in json_str

    def test_result_from_json(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
    ):
        """PreprocessResult can be deserialized from JSON."""
        result = asyncio.run(worker.process(preprocess_input))

        json_str = result.to_json()
        restored = PreprocessResult.from_json(json_str)

        assert restored.epub_id == result.epub_id
        assert len(restored.term_dictionary.mappings) == len(
            result.term_dictionary.mappings
        )
        assert restored.summaries == result.summaries
