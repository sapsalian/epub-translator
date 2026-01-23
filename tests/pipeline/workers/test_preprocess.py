"""Tests for PreprocessWorker."""

import asyncio
from unittest.mock import AsyncMock, call

import pytest

from src.pipeline.models import (
    ExtractionResult,
    Language,
    PreprocessResult,
    TermMapping,
    TextLocation,
    TextUnit,
    XhtmlExtraction,
)
from src.pipeline.workers.base import PreprocessError
from src.pipeline.workers.preprocess import (
    ChunkResult,
    PreprocessAPIClient,
    PreprocessInput,
    PreprocessWorker,
    DEFAULT_CHUNK_SIZE,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Create a mock API client."""
    client = AsyncMock(spec=PreprocessAPIClient)
    client.extract_chunk.return_value = ChunkResult(
        summary="Chunk summary.",
        terms=[
            TermMapping(source="hello", target="안녕하세요"),
            TermMapping(source="world", target="세계"),
        ],
    )
    client.merge_extractions.return_value = ChunkResult(
        summary="Merged summary.",
        terms=[
            TermMapping(source="hello", target="안녕하세요"),
            TermMapping(source="world", target="세계"),
        ],
    )
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

    def test_default_chunk_size(self, sample_extraction_result: ExtractionResult):
        """Default chunk size is set."""
        input_data = PreprocessInput(
            extraction_result=sample_extraction_result,
            target_language=Language.KOREAN,
        )
        assert input_data.chunk_size == DEFAULT_CHUNK_SIZE

    def test_custom_chunk_size(self, sample_extraction_result: ExtractionResult):
        """Custom chunk size can be specified."""
        input_data = PreprocessInput(
            extraction_result=sample_extraction_result,
            target_language=Language.KOREAN,
            chunk_size=2000,
        )
        assert input_data.chunk_size == 2000


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
    ):
        """Processing generates term dictionary."""
        result = asyncio.run(worker.process(preprocess_input))

        assert result.term_dictionary.source_language == Language.ENGLISH
        assert result.term_dictionary.target_language == Language.KOREAN
        assert len(result.term_dictionary.mappings) == 2

    def test_generates_summaries(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
    ):
        """Processing generates summaries for each XHTML."""
        result = asyncio.run(worker.process(preprocess_input))

        assert len(result.summaries) == 2
        assert "xhtml-001" in result.summaries
        assert "xhtml-002" in result.summaries

    def test_generates_epub_summary_from_merge(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
    ):
        """Processing generates epub_summary from merged result."""
        result = asyncio.run(worker.process(preprocess_input))

        # epub_summary comes from merge_extractions result
        assert result.epub_summary == "Merged summary."

    def test_epub_summary_uses_xhtml_summary_for_single_xhtml(
        self,
        mock_api_client: AsyncMock,
    ):
        """Single XHTML uses its summary as epub_summary."""
        extraction = ExtractionResult(
            epub_id="single",
            source_language=Language.ENGLISH,
            xhtml_extractions=[
                XhtmlExtraction(
                    xhtml_id="xhtml-001",
                    xhtml_path="chapter1.xhtml",
                    text_units=[],
                    raw_text="Some content here.",
                ),
            ],
        )
        input_data = PreprocessInput(
            extraction_result=extraction,
            target_language=Language.KOREAN,
        )
        worker = PreprocessWorker(api_client=mock_api_client)

        result = asyncio.run(worker.process(input_data))

        # Single XHTML uses chunk summary as epub_summary
        assert result.epub_summary == "Chunk summary."

    def test_merge_receives_summaries_for_context(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
        mock_api_client: AsyncMock,
    ):
        """merge_extractions receives XHTML summaries for term conflict resolution."""
        asyncio.run(worker.process(preprocess_input))

        # Verify merge was called with summaries
        call_kwargs = mock_api_client.merge_extractions.call_args.kwargs
        assert "chunk_summaries" in call_kwargs
        assert len(call_kwargs["chunk_summaries"]) == 2  # Two XHTML summaries

    def test_calls_extract_chunk_for_each_xhtml(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
        mock_api_client: AsyncMock,
    ):
        """extract_chunk is called for each XHTML's raw_text."""
        asyncio.run(worker.process(preprocess_input))

        # Two XHTMLs with small text, each should result in one extract_chunk call
        assert mock_api_client.extract_chunk.call_count == 2

    def test_calls_merge_extractions_for_multiple_xhtml(
        self,
        worker: PreprocessWorker,
        preprocess_input: PreprocessInput,
        mock_api_client: AsyncMock,
    ):
        """merge_extractions is called when there are multiple XHTMLs."""
        asyncio.run(worker.process(preprocess_input))

        # Final merge for 2 XHTMLs
        assert mock_api_client.merge_extractions.call_count == 1

    def test_skips_empty_xhtml(
        self,
        mock_api_client: AsyncMock,
    ):
        """Empty XHTML raw_text is skipped."""
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
        # Only one extract_chunk call (for non-empty xhtml)
        assert mock_api_client.extract_chunk.call_count == 1
        # No merge needed for single XHTML
        mock_api_client.merge_extractions.assert_not_called()

    def test_empty_extraction_produces_empty_result(
        self,
        mock_api_client: AsyncMock,
    ):
        """Empty extraction produces empty term dictionary and summaries."""
        extraction = ExtractionResult(
            epub_id="empty-epub",
            source_language=Language.ENGLISH,
            xhtml_extractions=[],
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
        mock_api_client.extract_chunk.assert_not_called()
        mock_api_client.merge_extractions.assert_not_called()

    def test_single_xhtml_no_final_merge(
        self,
        mock_api_client: AsyncMock,
    ):
        """Single XHTML doesn't trigger final merge."""
        extraction = ExtractionResult(
            epub_id="single",
            source_language=Language.ENGLISH,
            xhtml_extractions=[
                XhtmlExtraction(
                    xhtml_id="xhtml-001",
                    xhtml_path="chapter1.xhtml",
                    text_units=[],
                    raw_text="Some content here.",
                ),
            ],
        )
        input_data = PreprocessInput(
            extraction_result=extraction,
            target_language=Language.KOREAN,
        )
        worker = PreprocessWorker(api_client=mock_api_client)

        result = asyncio.run(worker.process(input_data))

        assert len(result.summaries) == 1
        mock_api_client.extract_chunk.assert_called_once()
        mock_api_client.merge_extractions.assert_not_called()


# =============================================================================
# Chunking Tests
# =============================================================================


class TestChunking:
    """Tests for text chunking functionality."""

    def test_split_into_chunks_small_text(self, worker: PreprocessWorker):
        """Small text returns single chunk."""
        text = "Hello world."
        chunks = worker._split_into_chunks(text, chunk_size=1000)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_split_into_chunks_large_text(self, worker: PreprocessWorker):
        """Large text is split into multiple chunks."""
        # Create text larger than chunk_size
        paragraphs = ["Paragraph " + str(i) + "." * 100 for i in range(10)]
        text = "\n\n".join(paragraphs)

        chunks = worker._split_into_chunks(text, chunk_size=300)

        assert len(chunks) > 1
        # Each chunk should be approximately chunk_size or less
        for chunk in chunks:
            assert len(chunk) <= 500  # Some margin for paragraph boundaries

    def test_split_into_chunks_respects_paragraph_boundaries(
        self, worker: PreprocessWorker
    ):
        """Chunks respect paragraph boundaries."""
        text = "Para 1.\n\nPara 2.\n\nPara 3."
        chunks = worker._split_into_chunks(text, chunk_size=20)

        # Should split at paragraph boundaries
        for chunk in chunks:
            # Chunks shouldn't have partial paragraphs (split mid-sentence)
            assert chunk.startswith("Para")

    def test_split_into_chunks_empty_text(self, worker: PreprocessWorker):
        """Empty text returns empty list."""
        chunks = worker._split_into_chunks("", chunk_size=1000)
        assert chunks == []

        chunks = worker._split_into_chunks("   ", chunk_size=1000)
        assert chunks == []

    def test_chunking_triggers_multiple_api_calls(
        self,
        mock_api_client: AsyncMock,
    ):
        """Large XHTML text triggers multiple extract_chunk calls."""
        # Create large text that will be split
        large_text = "\n\n".join(["Paragraph " + str(i) + "." * 500 for i in range(10)])

        extraction = ExtractionResult(
            epub_id="large",
            source_language=Language.ENGLISH,
            xhtml_extractions=[
                XhtmlExtraction(
                    xhtml_id="xhtml-001",
                    xhtml_path="chapter1.xhtml",
                    text_units=[],
                    raw_text=large_text,
                ),
            ],
        )
        input_data = PreprocessInput(
            extraction_result=extraction,
            target_language=Language.KOREAN,
            chunk_size=1000,  # Small chunk size to force multiple chunks
        )
        worker = PreprocessWorker(api_client=mock_api_client)

        asyncio.run(worker.process(input_data))

        # Multiple chunks should trigger multiple extract_chunk calls
        assert mock_api_client.extract_chunk.call_count > 1
        # And a merge for the XHTML's chunks
        assert mock_api_client.merge_extractions.call_count >= 1


# =============================================================================
# Term Accumulation Tests
# =============================================================================


class TestTermAccumulation:
    """Tests for term accumulation across chunks."""

    def test_terms_accumulate_in_result(
        self,
    ):
        """Terms from all XHTMLs are accumulated in the final result."""
        # Create mock that returns different terms for each XHTML
        call_count = 0

        async def mock_extract_chunk(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return ChunkResult(
                    summary="First summary.",
                    terms=[TermMapping(source="hello", target="안녕")],
                )
            else:
                return ChunkResult(
                    summary="Second summary.",
                    terms=[TermMapping(source="world", target="세계")],
                )

        mock_client = AsyncMock(spec=PreprocessAPIClient)
        mock_client.extract_chunk.side_effect = mock_extract_chunk
        mock_client.merge_extractions.return_value = ChunkResult(
            summary="Merged summary.",
            terms=[
                TermMapping(source="hello", target="안녕"),
                TermMapping(source="world", target="세계"),
            ],
        )

        extraction = ExtractionResult(
            epub_id="test",
            source_language=Language.ENGLISH,
            xhtml_extractions=[
                XhtmlExtraction(
                    xhtml_id="xhtml-001",
                    xhtml_path="chapter1.xhtml",
                    text_units=[],
                    raw_text="First chapter content.",
                ),
                XhtmlExtraction(
                    xhtml_id="xhtml-002",
                    xhtml_path="chapter2.xhtml",
                    text_units=[],
                    raw_text="Second chapter content.",
                ),
            ],
        )
        input_data = PreprocessInput(
            extraction_result=extraction,
            target_language=Language.KOREAN,
        )
        worker = PreprocessWorker(api_client=mock_client)

        result = asyncio.run(worker.process(input_data))

        # Both XHTMLs should have been processed
        assert mock_client.extract_chunk.call_count == 2
        # Final result should include terms from both XHTMLs (via merge)
        assert len(result.term_dictionary.mappings) == 2
        term_sources = [m.source for m in result.term_dictionary.mappings]
        assert "hello" in term_sources
        assert "world" in term_sources


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_extract_chunk_error_raises_preprocess_error(
        self,
        preprocess_input: PreprocessInput,
    ):
        """extract_chunk errors are wrapped in PreprocessError."""
        failing_client = AsyncMock(spec=PreprocessAPIClient)
        failing_client.extract_chunk.side_effect = Exception("API failed")

        worker = PreprocessWorker(api_client=failing_client)

        with pytest.raises(PreprocessError, match="API failed"):
            asyncio.run(worker.process(preprocess_input))

    def test_merge_error_raises_preprocess_error(
        self,
        preprocess_input: PreprocessInput,
        mock_api_client: AsyncMock,
    ):
        """merge_extractions errors are wrapped in PreprocessError."""
        mock_api_client.merge_extractions.side_effect = Exception("Merge failed")

        worker = PreprocessWorker(api_client=mock_api_client)

        with pytest.raises(PreprocessError, match="Merge failed"):
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
