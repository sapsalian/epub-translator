"""Tests for dynamic input builders."""

from src.pipeline.api.inputs import (
    build_chunk_extraction_input,
    build_meta_merge_input,
    build_translation_input,
)
from src.pipeline.models import Language


class TestBuildChunkExtractionInput:
    """Tests for build_chunk_extraction_input."""

    def test_includes_custom_instructions(self):
        """Custom instructions section appears in output."""
        result = build_chunk_extraction_input(
            chunk_text="Some text.",
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            custom_instructions="Prefer formal register.",
        )

        assert "Custom Instructions:" in result
        assert "Prefer formal register." in result

    def test_omits_custom_instructions_when_empty(self):
        """No custom instructions section when empty."""
        result = build_chunk_extraction_input(
            chunk_text="Some text.",
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            custom_instructions="",
        )

        assert "Custom Instructions:" not in result


class TestBuildMetaMergeInput:
    """Tests for build_meta_merge_input."""

    def test_includes_chunk_styles(self):
        """Chunk style notes section appears in output."""
        result = build_meta_merge_input(
            chunk_summaries=["S1.", "S2."],
            chunk_terms=[{}, {}],
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            chunk_styles=["First-person, past tense.", "Third-person, present tense."],
        )

        assert "--- Chunk Style Notes ---" in result
        assert "First-person, past tense." in result
        assert "Third-person, present tense." in result

    def test_omits_styles_when_none(self):
        """No styles section when chunk_styles is None."""
        result = build_meta_merge_input(
            chunk_summaries=["S1."],
            chunk_terms=[{}],
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            chunk_styles=None,
        )

        assert "Chunk Style Notes" not in result

    def test_omits_styles_when_all_empty(self):
        """No styles section when all chunk_styles are empty strings."""
        result = build_meta_merge_input(
            chunk_summaries=["S1.", "S2."],
            chunk_terms=[{}, {}],
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            chunk_styles=["", ""],
        )

        assert "Chunk Style Notes" not in result

    def test_includes_custom_instructions(self):
        """Custom instructions section appears in output."""
        result = build_meta_merge_input(
            chunk_summaries=["S1."],
            chunk_terms=[{}],
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            custom_instructions="Be concise.",
        )

        assert "Custom Instructions:" in result
        assert "Be concise." in result


class TestBuildTranslationInput:
    """Tests for build_translation_input."""

    def test_includes_style_guidelines(self):
        """Style guidelines section appears in output."""
        result = build_translation_input(
            unit_ids=["u1"],
            texts=["Hello."],
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            term_dictionary={},
            context_summary="",
            style_guidelines="Use 해라체 for narrative.",
        )

        assert "Style Guidelines:" in result
        assert "해라체" in result

    def test_omits_style_guidelines_when_empty(self):
        """No style guidelines section when empty."""
        result = build_translation_input(
            unit_ids=["u1"],
            texts=["Hello."],
            source_language=Language.ENGLISH,
            target_language=Language.KOREAN,
            term_dictionary={},
            context_summary="",
            style_guidelines="",
        )

        assert "Style Guidelines:" not in result
