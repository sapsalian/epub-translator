"""Tests for OpenAI client."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pipeline.api.openai_client import OpenAIClient
from src.pipeline.api.retry import RetryConfig
from src.pipeline.api.schemas import (
    ChunkExtractionOutput,
    MergeOutput,
    TranslationOutput,
)
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


def _mock_parse_response(output_parsed):
    """Create a mock Responses API parse response."""
    mock_response = MagicMock()
    mock_response.output_parsed = output_parsed
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
        parsed_output = ChunkExtractionOutput(
            summary="A story about greeting.",
            terms={"hello": "안녕하세요", "world": "세계"},
        )
        mock_openai.return_value.responses.parse = AsyncMock(
            return_value=_mock_parse_response(parsed_output)
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
        parsed_output = ChunkExtractionOutput(
            summary="Continuing the story.",
            terms={"new_term": "새 용어"},
        )
        mock_openai.return_value.responses.parse = AsyncMock(
            return_value=_mock_parse_response(parsed_output)
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
        parsed_output = MergeOutput(
            summary="Combined summary of all chunks.",
            terms={"term1": "용어1", "term2": "용어2"},
        )
        mock_openai.return_value.responses.parse = AsyncMock(
            return_value=_mock_parse_response(parsed_output)
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
        parsed_output = TranslationOutput(
            translations={
                "unit-001": "안녕 {{1}}세상{{/1}}",
                "unit-002": "안녕히 가세요",
            }
        )
        mock_openai.return_value.responses.parse = AsyncMock(
            return_value=_mock_parse_response(parsed_output)
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
        parsed_output = TranslationOutput(
            translations={
                "unit-001": "번역된 텍스트",
                # unit-002 is missing
            }
        )
        mock_openai.return_value.responses.parse = AsyncMock(
            return_value=_mock_parse_response(parsed_output)
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
# Structured Output Error Handling Tests
# =============================================================================


class TestStructuredOutputErrors:
    """Tests for error handling in structured output parsing."""

    def test_none_output_raises(self, client, mock_openai):
        """Raises ValueError when output_parsed is None."""
        mock_openai.return_value.responses.parse = AsyncMock(
            return_value=_mock_parse_response(None)
        )

        with pytest.raises(ValueError, match="Structured output parsing returned None"):
            asyncio.run(
                client.extract_chunk(
                    chunk_text="Some text.",
                    source_language=Language.ENGLISH,
                    target_language=Language.KOREAN,
                )
            )