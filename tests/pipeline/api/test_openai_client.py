"""Tests for OpenAI client."""

import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.api.openai_client import OpenAIClient
from src.pipeline.api.retry import RetryConfig
from src.pipeline.models import Language, TextLocation, TextUnit


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    with patch("src.pipeline.api.openai_client.AsyncOpenAI") as mock:
        yield mock


@pytest.fixture
def client(mock_openai):
    """Create OpenAI client with mocked API."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        return OpenAIClient(retry_config=RetryConfig(max_retries=0))


@pytest.fixture
def sample_text_units():
    """Sample text units for translation."""
    return [
        TextUnit(
            unit_id="unit-001",
            location=TextLocation(xhtml_path="chapter1.xhtml", xpath="/html/body/p[1]"),
            source_text="Hello world",
            tagged_text="Hello {{1}}world{{/1}}",
            inner_tags=[],
        ),
        TextUnit(
            unit_id="unit-002",
            location=TextLocation(xhtml_path="chapter1.xhtml", xpath="/html/body/p[2]"),
            source_text="Goodbye",
            tagged_text="Goodbye",
            inner_tags=[],
        ),
    ]


def _mock_create_response(output_dict: dict) -> MagicMock:
    """Create a mock Responses API create response."""
    mock_response = MagicMock()
    mock_response.output_text = json.dumps(output_dict)
    return mock_response


# =============================================================================
# Initialization Tests
# =============================================================================


class TestOpenAIClientInit:
    """Tests for OpenAI client initialization."""

    def test_init_with_api_key(self, mock_openai):
        """Initialize with explicit API key."""
        client = OpenAIClient(api_key="explicit-key")

        mock_openai.assert_called_once_with(api_key="explicit-key")

    def test_init_with_env_var(self, mock_openai):
        """Initialize with environment variable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            client = OpenAIClient()

        mock_openai.assert_called_once_with(api_key="env-key")

    def test_init_without_key_raises(self, mock_openai):
        """Raises error if no API key provided."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove OPENAI_API_KEY if it exists
            os.environ.pop("OPENAI_API_KEY", None)

            with pytest.raises(ValueError, match="API key is required"):
                OpenAIClient()

    def test_init_with_custom_model(self, mock_openai):
        """Initialize with custom model."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            client = OpenAIClient(model="gpt-4-turbo")

        assert client._model == "gpt-4-turbo"


# =============================================================================
# Chunk Extraction Tests
# =============================================================================


class TestExtractChunk:
    """Tests for chunk extraction."""

    def test_empty_input_returns_empty(self, client):
        """Empty input returns empty result."""
        result = asyncio.run(
            client.extract_chunk(
                chunk_text="",
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.summary == ""
        assert result.terms == {}

    def test_parses_extraction_response(self, client, mock_openai):
        """Parses structured extraction response."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "summary": "A story about greeting.",
                "terms": [
                    {"source": "hello", "target": "안녕하세요"},
                    {"source": "world", "target": "세계"},
                ],
            })
        )

        result = asyncio.run(
            client.extract_chunk(
                chunk_text="Hello world! This is a test.",
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.summary == "A story about greeting."
        assert len(result.terms) == 2
        assert result.terms["hello"] == "안녕하세요"
        assert result.terms["world"] == "세계"

    def test_with_existing_terms(self, client, mock_openai):
        """Passes existing terms for consistency."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "summary": "Continuing the story.",
                "terms": [{"source": "new_term", "target": "새 용어"}],
            })
        )

        result = asyncio.run(
            client.extract_chunk(
                chunk_text="More text here.",
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                existing_terms={"hello": "안녕하세요"},
            )
        )

        assert result.summary == "Continuing the story."
        assert len(result.terms) == 1


# =============================================================================
# Merge Extractions Tests
# =============================================================================


class TestMergeExtractions:
    """Tests for merging chunk extractions."""

    def test_empty_input_returns_empty(self, client):
        """Empty input returns empty result."""
        result = asyncio.run(
            client.merge_extractions(
                chunk_summaries=[],
                chunk_terms=[],
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.summary == ""
        assert result.terms == {}

    def test_single_chunk_returns_as_is(self, client):
        """Single chunk doesn't need API call."""
        result = asyncio.run(
            client.merge_extractions(
                chunk_summaries=["Single summary."],
                chunk_terms=[{"term": "용어"}],
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.summary == "Single summary."
        assert len(result.terms) == 1
        assert result.terms["term"] == "용어"

    def test_merges_multiple_chunks(self, client, mock_openai):
        """Merges multiple chunks via API."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "summary": "Combined summary of all chunks.",
                "terms": [
                    {"source": "term1", "target": "용어1"},
                    {"source": "term2", "target": "용어2"},
                ],
            })
        )

        result = asyncio.run(
            client.merge_extractions(
                chunk_summaries=["Summary 1.", "Summary 2."],
                chunk_terms=[
                    {"term1": "용어1"},
                    {"term2": "용어2"},
                ],
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.summary == "Combined summary of all chunks."
        assert len(result.terms) == 2


# =============================================================================
# Translation Tests
# =============================================================================


class TestTranslate:
    """Tests for translation."""

    def test_empty_input_returns_empty(self, client):
        """Empty input returns empty list."""
        result = asyncio.run(
            client.translate(
                text_units=[],
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                term_dictionary={},
                context_summary="",
            )
        )

        assert result == []

    def test_parses_translation_response(
        self, client, mock_openai, sample_text_units
    ):
        """Parses structured translation response."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "translations": [
                    {"unit_id": "unit-001", "text": "안녕 {{1}}세상{{/1}}"},
                    {"unit_id": "unit-002", "text": "안녕히 가세요"},
                ],
            })
        )

        result = asyncio.run(
            client.translate(
                text_units=sample_text_units,
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                term_dictionary={"hello": "안녕"},
                context_summary="Test context",
            )
        )

        assert len(result) == 2
        assert result[0] == "안녕 {{1}}세상{{/1}}"
        assert result[1] == "안녕히 가세요"

    def test_handles_missing_translation(self, client, mock_openai, sample_text_units):
        """Handles missing translation for some unit IDs."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "translations": [
                    {"unit_id": "unit-001", "text": "번역된 텍스트"},
                    # unit-002 is missing
                ],
            })
        )

        result = asyncio.run(
            client.translate(
                text_units=sample_text_units,
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                term_dictionary={},
                context_summary="",
            )
        )

        assert len(result) == 2
        assert result[0] == "번역된 텍스트"
        assert result[1] == ""  # Missing ID returns empty string


# =============================================================================
# Style Notes Tests
# =============================================================================


class TestStyleNotes:
    """Tests for style_notes handling in extraction, merge, and translation."""

    def test_extract_chunk_parses_style_notes(self, client, mock_openai):
        """style_notes is parsed from extraction response."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "summary": "A greeting scene.",
                "terms": [],
                "style_notes": "Third-person limited, present tense.",
            })
        )

        result = asyncio.run(
            client.extract_chunk(
                chunk_text="Hello world!",
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.style_notes == "Third-person limited, present tense."

    def test_extract_chunk_style_notes_defaults_empty(self, client, mock_openai):
        """style_notes defaults to empty string if missing from response."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "summary": "Summary.",
                "terms": [],
            })
        )

        result = asyncio.run(
            client.extract_chunk(
                chunk_text="Text.",
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.style_notes == ""

    def test_merge_parses_style_notes(self, client, mock_openai):
        """style_notes is parsed from merge response."""
        mock_openai.return_value.responses.create = AsyncMock(
            return_value=_mock_create_response({
                "summary": "Combined summary.",
                "terms": [],
                "style_notes": "Unified style guide.",
            })
        )

        result = asyncio.run(
            client.merge_extractions(
                chunk_summaries=["S1.", "S2."],
                chunk_terms=[{}, {}],
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                chunk_styles=["Style 1.", "Style 2."],
            )
        )

        assert result.style_notes == "Unified style guide."

    def test_single_chunk_merge_preserves_style_notes(self, client):
        """Single-chunk shortcut returns chunk_styles[0] as style_notes."""
        result = asyncio.run(
            client.merge_extractions(
                chunk_summaries=["Only summary."],
                chunk_terms=[{"term": "용어"}],
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                chunk_styles=["Only style."],
            )
        )

        assert result.style_notes == "Only style."

    def test_single_chunk_merge_no_styles_returns_empty(self, client):
        """Single-chunk shortcut with no chunk_styles returns empty style_notes."""
        result = asyncio.run(
            client.merge_extractions(
                chunk_summaries=["Only summary."],
                chunk_terms=[{"term": "용어"}],
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
            )
        )

        assert result.style_notes == ""

    def test_translate_passes_style_guidelines_to_api(
        self, client, mock_openai, sample_text_units
    ):
        """style_guidelines is included in the API input."""
        mock_create = AsyncMock(
            return_value=_mock_create_response({
                "translations": [
                    {"unit_id": "unit-001", "text": "번역1"},
                    {"unit_id": "unit-002", "text": "번역2"},
                ],
            })
        )
        mock_openai.return_value.responses.create = mock_create

        asyncio.run(
            client.translate(
                text_units=sample_text_units,
                source_language=Language.ENGLISH,
                target_language=Language.KOREAN,
                term_dictionary={},
                context_summary="Context",
                style_guidelines="Use 해라체 for narrative.",
            )
        )

        # Verify style guidelines appear in the input text
        call_kwargs = mock_create.call_args.kwargs
        assert "Style Guidelines" in call_kwargs["input"]
        assert "해라체" in call_kwargs["input"]