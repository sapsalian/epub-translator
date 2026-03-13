from pathlib import Path
from zipfile import ZipFile

from src.epub_walker.reader import extract_chapter_paragraphs, get_chapter_titles


SAMPLE_EPUB = Path("demo_files/sample.epub")
TRANSLATED_EPUB = Path("demo_files/translated.epub")


class TestGetChapterTitles:
    def test_returns_titles_in_spine_order_with_filename_fallback(self):
        with ZipFile(SAMPLE_EPUB) as zf:
            titles = get_chapter_titles(zf)

        assert len(titles) == 8
        assert titles[0] == "Preface"
        assert titles[1] == "The_Hunters_Fate_split_001"
        assert titles[2] == "Chapter 1: The Beginning of the End"
        assert titles[-1] == "Afterword"


class TestExtractChapterParagraphs:
    def test_extracts_source_and_translation_html_for_supported_tags(self):
        with ZipFile(SAMPLE_EPUB) as source_zf, ZipFile(TRANSLATED_EPUB) as translation_zf:
            paragraphs = extract_chapter_paragraphs(
                source_zf=source_zf,
                translation_zf=translation_zf,
                chapter_idx=2,
                chapter_id="ch002",
            )

        assert paragraphs[0]["id"] == "ch002_p0"
        assert paragraphs[0]["source"].startswith("Chapter 1: The Beginning of the End")
        assert paragraphs[0]["translation"].startswith("[Translated: Chapter 1: The Beginning of the End]")
        assert any(
            "The world ended in May." in paragraph["source"] and "<strong" in paragraph["source"]
            for paragraph in paragraphs
        )

    def test_returns_empty_source_when_source_epub_is_missing(self):
        with ZipFile(TRANSLATED_EPUB) as translation_zf:
            paragraphs = extract_chapter_paragraphs(
                source_zf=None,
                translation_zf=translation_zf,
                chapter_idx=0,
                chapter_id="ch000",
            )

        assert paragraphs
        assert all(paragraph["source"] == "" for paragraph in paragraphs)
        assert paragraphs[0]["translation"].startswith("[Translated: Preface]")
