"""Live API tests for OpenAI client.

These tests call the real OpenAI API to verify schema compatibility
and response parsing. Requires OPENAI_API_KEY in .env.

Run: .venv/bin/python -m pytest -m live -v
"""

import re

import pytest

from src.pipeline.models import Language, TextLocation, TextUnit

from .conftest import live, skip_without_key

pytestmark = [live, skip_without_key]


# =============================================================================
# Extract Chunk Tests
# =============================================================================


class TestExtractChunkLive:
    """Live tests for chunk extraction."""

    @pytest.mark.asyncio
    async def test_returns_valid_response(self, live_client):
        """API returns parseable summary and terms."""
        result = await live_client.extract_chunk(
            chunk_text="Milo ran through the dark forest. The Hellhounds were close behind.",
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
        )

        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        assert isinstance(result.terms, dict)

    @pytest.mark.asyncio
    async def test_with_existing_terms(self, live_client):
        """Existing terms are accepted without error."""
        result = await live_client.extract_chunk(
            chunk_text="Milo met the Hellhounds at dawn.",
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            existing_terms={"Milo": "마일로"},
        )

        assert isinstance(result.summary, str)
        assert isinstance(result.terms, dict)


# =============================================================================
# Merge Extractions Tests
# =============================================================================


class TestMergeExtractionsLive:
    """Live tests for merging chunk extractions."""

    @pytest.mark.asyncio
    async def test_merge_two_chunks(self, live_client):
        """Two chunk summaries merge into a coherent result."""
        result = await live_client.merge_extractions(
            chunk_summaries=[
                "Milo enters a dark forest and encounters strange creatures.",
                "Milo escapes the forest and reaches a village.",
            ],
            chunk_terms=[
                {"Milo": "마일로", "Hellhounds": "헬하운드"},
                {"Milo": "마일로", "Elder": "장로"},
            ],
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
        )

        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        assert isinstance(result.terms, dict)
        assert len(result.terms) >= 1


# =============================================================================
# Translation Tests
# =============================================================================


class TestTranslateLive:
    """Live tests for translation."""

    @pytest.mark.asyncio
    async def test_returns_correct_count(self, live_client):
        """Translation returns one result per text unit."""
        units = [
            TextUnit(
                unit_id="u1",
                location=TextLocation(xhtml_path="ch1.xhtml", xpath="/p[1]"),
                source_text="Hello world",
                tagged_text="Hello world",
                inner_tags=[],
            ),
            TextUnit(
                unit_id="u2",
                location=TextLocation(xhtml_path="ch1.xhtml", xpath="/p[2]"),
                source_text="Goodbye",
                tagged_text="Goodbye",
                inner_tags=[],
            ),
        ]

        result = await live_client.translate(
            text_units=units,
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            term_dictionary={},
            context_summary="Simple greeting text.",
        )

        assert len(result) == 2
        assert all(isinstance(t, str) and len(t) > 0 for t in result)

    @pytest.mark.asyncio
    async def test_preserves_placeholders(self, live_client):
        """Placeholder tags are preserved in translation."""
        units = [
            TextUnit(
                unit_id="u1",
                location=TextLocation(xhtml_path="ch1.xhtml", xpath="/p[1]"),
                source_text="The bold word is important.",
                tagged_text="The {{1}}bold word{{/1}} is important.",
                inner_tags=[],
            ),
        ]

        result = await live_client.translate(
            text_units=units,
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            term_dictionary={},
            context_summary="",
        )

        assert len(result) == 1
        assert re.search(r"\{\{1\}\}", result[0]), f"Missing {{{{1}}}} in: {result[0]}"
        assert re.search(r"\{\{/1\}\}", result[0]), f"Missing {{{{/1}}}} in: {result[0]}"
