"""Tests for TranslationWorker."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.pipeline.models import (
    Language,
    TermDictionary,
    TextLocation,
    TextUnit,
    TranslatedUnit,
    TranslationResult,
    TranslationTask,
)
from src.pipeline.workers.base import TranslationError
from src.pipeline.workers.translation import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_CONCURRENT,
    TranslationAPIClient,
    TranslationInput,
    TranslationWorker,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_api_client() -> AsyncMock:
    """Create a mock API client."""
    client = AsyncMock(spec=TranslationAPIClient)
    # Default: return translations matching input order
    client.translate.side_effect = lambda text_units, **kwargs: [
        f"translated_{unit.unit_id}" for unit in text_units
    ]
    return client


@pytest.fixture
def sample_text_units() -> list[TextUnit]:
    """Create sample text units."""
    return [
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
        TextUnit(
            unit_id="unit-002",
            location=TextLocation(
                xhtml_path="OEBPS/chapter1.xhtml",
                xpath="/html/body/p[2]",
            ),
            source_text="Goodbye world",
            tagged_text="Goodbye world",
            inner_tags=[],
        ),
    ]


@pytest.fixture
def sample_task(sample_text_units: list[TextUnit]) -> TranslationTask:
    """Create a sample translation task."""
    return TranslationTask(
        epub_id="test-epub-001",
        xhtml_id="xhtml-001",
        target_language=Language.KOREAN,
        text_units=sample_text_units,
    )


@pytest.fixture
def sample_term_dictionary() -> TermDictionary:
    """Create a sample term dictionary."""
    return TermDictionary(
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        mappings={"hello": "안녕하세요", "world": "세계"},
    )


@pytest.fixture
def translation_input(
    sample_task: TranslationTask,
    sample_term_dictionary: TermDictionary,
) -> TranslationInput:
    """Create translation input."""
    return TranslationInput(
        task=sample_task,
        source_language=Language.ENGLISH,
        term_dictionary=sample_term_dictionary,
        context_summary="A greeting and farewell.",
    )


@pytest.fixture
def worker(mock_api_client: AsyncMock) -> TranslationWorker:
    """Create TranslationWorker with mock client."""
    return TranslationWorker(api_client=mock_api_client)


# =============================================================================
# Basic Tests
# =============================================================================


class TestTranslationWorkerBasic:
    """Basic tests for TranslationWorker."""

    def test_worker_has_logger(self, worker: TranslationWorker):
        """Worker has logger attribute."""
        assert hasattr(worker, "logger")

    def test_worker_repr(self, worker: TranslationWorker):
        """Worker has readable repr."""
        assert repr(worker) == "TranslationWorker()"


class TestTranslationInput:
    """Tests for TranslationInput model."""

    def test_input_fields(
        self,
        sample_task: TranslationTask,
        sample_term_dictionary: TermDictionary,
    ):
        """Input has required fields."""
        input_data = TranslationInput(
            task=sample_task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
            context_summary="Test summary",
        )
        assert input_data.task.epub_id == "test-epub-001"
        assert input_data.source_language == Language.ENGLISH
        assert len(input_data.term_dictionary.mappings) == 2

    def test_default_batch_size(
        self,
        sample_task: TranslationTask,
        sample_term_dictionary: TermDictionary,
    ):
        """Default batch size is set."""
        input_data = TranslationInput(
            task=sample_task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
        )
        assert input_data.batch_size == DEFAULT_BATCH_SIZE

    def test_default_max_concurrent(
        self,
        sample_task: TranslationTask,
        sample_term_dictionary: TermDictionary,
    ):
        """Default max concurrent is set."""
        input_data = TranslationInput(
            task=sample_task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
        )
        assert input_data.max_concurrent == DEFAULT_MAX_CONCURRENT

    def test_custom_batch_size(
        self,
        sample_task: TranslationTask,
        sample_term_dictionary: TermDictionary,
    ):
        """Custom batch size can be specified."""
        input_data = TranslationInput(
            task=sample_task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
            batch_size=10,
        )
        assert input_data.batch_size == 10


# =============================================================================
# Translation Tests
# =============================================================================


class TestTranslation:
    """Tests for translation functionality."""

    def test_generates_translation_result(
        self,
        worker: TranslationWorker,
        translation_input: TranslationInput,
    ):
        """Processing produces TranslationResult."""
        result = asyncio.run(worker.process(translation_input))

        assert isinstance(result, TranslationResult)
        assert result.epub_id == "test-epub-001"
        assert result.xhtml_id == "xhtml-001"
        assert result.target_language == Language.KOREAN

    def test_translates_all_units(
        self,
        worker: TranslationWorker,
        translation_input: TranslationInput,
    ):
        """All text units are translated."""
        result = asyncio.run(worker.process(translation_input))

        assert len(result.translated_units) == 2
        unit_ids = [u.unit_id for u in result.translated_units]
        assert "unit-001" in unit_ids
        assert "unit-002" in unit_ids

    def test_preserves_unit_order(
        self,
        worker: TranslationWorker,
        translation_input: TranslationInput,
    ):
        """Translated units maintain original order."""
        result = asyncio.run(worker.process(translation_input))

        assert result.translated_units[0].unit_id == "unit-001"
        assert result.translated_units[1].unit_id == "unit-002"

    def test_calls_api_with_correct_parameters(
        self,
        worker: TranslationWorker,
        translation_input: TranslationInput,
        mock_api_client: AsyncMock,
    ):
        """API is called with correct parameters."""
        asyncio.run(worker.process(translation_input))

        mock_api_client.translate.assert_called()
        call_kwargs = mock_api_client.translate.call_args.kwargs

        assert call_kwargs["source_language"] == Language.ENGLISH
        assert call_kwargs["target_language"] == Language.KOREAN
        assert "hello" in call_kwargs["term_dictionary"]
        assert call_kwargs["context_summary"] == "A greeting and farewell."

    def test_empty_task_returns_empty_result(
        self,
        mock_api_client: AsyncMock,
        sample_term_dictionary: TermDictionary,
    ):
        """Empty task produces empty result."""
        empty_task = TranslationTask(
            epub_id="test",
            xhtml_id="xhtml-001",
            target_language=Language.KOREAN,
            text_units=[],
        )
        input_data = TranslationInput(
            task=empty_task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
        )
        worker = TranslationWorker(api_client=mock_api_client)

        result = asyncio.run(worker.process(input_data))

        assert result.epub_id == "test"
        assert len(result.translated_units) == 0
        mock_api_client.translate.assert_not_called()


# =============================================================================
# Batching Tests
# =============================================================================


class TestBatching:
    """Tests for batching functionality."""

    def test_creates_correct_batches(self, worker: TranslationWorker):
        """Batches are created correctly."""
        units = [
            TextUnit(
                unit_id=f"unit-{i:03d}",
                location=TextLocation(xhtml_path="test.xhtml", xpath=f"/p[{i}]"),
                source_text=f"Text {i}",
                tagged_text=f"Text {i}",
                inner_tags=[],
            )
            for i in range(5)
        ]

        batches = worker._create_batches(units, batch_size=2)

        assert len(batches) == 3
        assert len(batches[0]) == 2
        assert len(batches[1]) == 2
        assert len(batches[2]) == 1

    def test_single_batch_for_small_input(
        self,
        worker: TranslationWorker,
        translation_input: TranslationInput,
        mock_api_client: AsyncMock,
    ):
        """Small input results in single API call."""
        asyncio.run(worker.process(translation_input))

        # 2 units with default batch_size=20 should be single call
        assert mock_api_client.translate.call_count == 1

    def test_multiple_batches_for_large_input(
        self,
        mock_api_client: AsyncMock,
        sample_term_dictionary: TermDictionary,
    ):
        """Large input is split into multiple batches."""
        # Create 25 text units
        units = [
            TextUnit(
                unit_id=f"unit-{i:03d}",
                location=TextLocation(xhtml_path="test.xhtml", xpath=f"/p[{i}]"),
                source_text=f"Text {i}",
                tagged_text=f"Text {i}",
                inner_tags=[],
            )
            for i in range(25)
        ]

        task = TranslationTask(
            epub_id="test",
            xhtml_id="xhtml-001",
            target_language=Language.KOREAN,
            text_units=units,
        )
        input_data = TranslationInput(
            task=task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
            batch_size=10,  # Force 3 batches
        )
        worker = TranslationWorker(api_client=mock_api_client)

        result = asyncio.run(worker.process(input_data))

        # 25 units / 10 batch_size = 3 batches
        assert mock_api_client.translate.call_count == 3
        assert len(result.translated_units) == 25


# =============================================================================
# Concurrency Tests
# =============================================================================


class TestConcurrency:
    """Tests for concurrency control."""

    def test_respects_max_concurrent(
        self,
        sample_term_dictionary: TermDictionary,
    ):
        """Concurrent calls are limited by max_concurrent."""
        concurrent_count = 0
        max_observed = 0

        async def mock_translate(*args, **kwargs):
            nonlocal concurrent_count, max_observed
            concurrent_count += 1
            max_observed = max(max_observed, concurrent_count)
            await asyncio.sleep(0.01)  # Simulate API latency
            concurrent_count -= 1
            text_units = kwargs.get("text_units", args[0] if args else [])
            return [f"translated_{u.unit_id}" for u in text_units]

        mock_client = AsyncMock(spec=TranslationAPIClient)
        mock_client.translate.side_effect = mock_translate

        # Create 20 units with batch_size=2 (10 batches) and max_concurrent=3
        units = [
            TextUnit(
                unit_id=f"unit-{i:03d}",
                location=TextLocation(xhtml_path="test.xhtml", xpath=f"/p[{i}]"),
                source_text=f"Text {i}",
                tagged_text=f"Text {i}",
                inner_tags=[],
            )
            for i in range(20)
        ]

        task = TranslationTask(
            epub_id="test",
            xhtml_id="xhtml-001",
            target_language=Language.KOREAN,
            text_units=units,
        )
        input_data = TranslationInput(
            task=task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
            batch_size=2,
            max_concurrent=3,
        )
        worker = TranslationWorker(api_client=mock_client)

        asyncio.run(worker.process(input_data))

        # Should never exceed max_concurrent
        assert max_observed <= 3


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    def test_api_error_raises_translation_error(
        self,
        translation_input: TranslationInput,
    ):
        """API errors are wrapped in TranslationError."""
        failing_client = AsyncMock(spec=TranslationAPIClient)
        failing_client.translate.side_effect = Exception("API failed")

        worker = TranslationWorker(api_client=failing_client)

        with pytest.raises(TranslationError, match="API failed"):
            asyncio.run(worker.process(translation_input))

    def test_partial_failure_raises_error(
        self,
        sample_term_dictionary: TermDictionary,
    ):
        """Partial batch failure raises error."""
        call_count = 0

        async def fail_on_second(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise Exception("Second batch failed")
            text_units = kwargs.get("text_units", args[0] if args else [])
            return [f"translated_{u.unit_id}" for u in text_units]

        mock_client = AsyncMock(spec=TranslationAPIClient)
        mock_client.translate.side_effect = fail_on_second

        units = [
            TextUnit(
                unit_id=f"unit-{i:03d}",
                location=TextLocation(xhtml_path="test.xhtml", xpath=f"/p[{i}]"),
                source_text=f"Text {i}",
                tagged_text=f"Text {i}",
                inner_tags=[],
            )
            for i in range(10)
        ]

        task = TranslationTask(
            epub_id="test",
            xhtml_id="xhtml-001",
            target_language=Language.KOREAN,
            text_units=units,
        )
        input_data = TranslationInput(
            task=task,
            source_language=Language.ENGLISH,
            term_dictionary=sample_term_dictionary,
            batch_size=3,
        )
        worker = TranslationWorker(api_client=mock_client)

        with pytest.raises(TranslationError, match="Second batch failed"):
            asyncio.run(worker.process(input_data))


# =============================================================================
# Serialization Tests
# =============================================================================


class TestSerialization:
    """Tests for result serialization."""

    def test_result_to_json(
        self,
        worker: TranslationWorker,
        translation_input: TranslationInput,
    ):
        """TranslationResult can be serialized to JSON."""
        result = asyncio.run(worker.process(translation_input))

        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert "test-epub-001" in json_str
        assert "xhtml-001" in json_str

    def test_result_from_json(
        self,
        worker: TranslationWorker,
        translation_input: TranslationInput,
    ):
        """TranslationResult can be deserialized from JSON."""
        result = asyncio.run(worker.process(translation_input))

        json_str = result.to_json()
        restored = TranslationResult.from_json(json_str)

        assert restored.epub_id == result.epub_id
        assert restored.xhtml_id == result.xhtml_id
        assert len(restored.translated_units) == len(result.translated_units)
