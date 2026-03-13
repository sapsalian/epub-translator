from pathlib import Path
from zipfile import ZipFile

from src.epub_walker.reader import extract_chapter_paragraphs, get_chapter_titles, render_chapter_html


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

    def test_fallback_strips_multi_html_extensions(self, tmp_path):
        epub_path = tmp_path / "multi-ext.epub"
        with ZipFile(epub_path, "w") as zf:
            zf.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
            )
            zf.writestr(
                "OEBPS/content.opf",
                """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest>
    <item id="c1" href="chapter-01.htm.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>""",
            )
            zf.writestr(
                "OEBPS/chapter-01.htm.xhtml",
                """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"><body><p>hello</p></body></html>""",
            )

        with ZipFile(epub_path) as zf:
            titles = get_chapter_titles(zf)

        assert titles == ["chapter-01"]


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


class TestRenderChapterHtml:
    def test_inlines_css_and_assigns_data_paragraph_id(self):
        with ZipFile(TRANSLATED_EPUB) as zf:
            html = render_chapter_html(zf, chapter_idx=2, chapter_id="ch002")

        assert "<style" in html
        assert 'data-paragraph-id="ch002_p0"' in html
        assert 'data-paragraph-id="ch002_p1"' in html
        assert "overscroll-behavior-x: none" in html
        assert "touch-action: pan-y" in html
        assert "table, pre" in html
        assert "overflow-x: auto" in html

    def test_inlines_svg_image_href(self, tmp_path):
        epub_path = tmp_path / "image-inline.epub"
        with ZipFile(epub_path, "w") as zf:
            zf.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
            )
            zf.writestr(
                "OEBPS/content.opf",
                """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0">
  <manifest>
    <item id="c1" href="wrap0000.xhtml" media-type="application/xhtml+xml"/>
    <item id="cover" href="cover.jpg" media-type="image/jpeg"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
  </spine>
</package>""",
            )
            zf.writestr(
                "OEBPS/wrap0000.xhtml",
                """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <body>
    <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
      <image xlink:href="cover.jpg"/>
    </svg>
  </body>
</html>""",
            )
            zf.writestr("OEBPS/cover.jpg", b"\xff\xd8\xff\xe0fake-jpeg")

        with ZipFile(epub_path) as zf:
            html = render_chapter_html(zf, chapter_idx=0, chapter_id="ch000")

        assert "xlink:href=\"data:image/jpeg;base64," in html
