from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree

from src.epub_walker.writer import patch_epub_paragraphs


def _build_sample_epub(epub_path: Path) -> None:
    with ZipFile(epub_path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
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
    <item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="chapter2.xhtml" media-type="application/xhtml+xml"/>
    <item id="style" href="style.css" media-type="text/css"/>
  </manifest>
  <spine>
    <itemref idref="c1"/>
    <itemref idref="c2"/>
  </spine>
</package>""",
        )
        zf.writestr(
            "OEBPS/chapter1.xhtml",
            """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Ch1</title></head>
  <body>
    <p>first chapter para one</p>
    <p>first chapter para two</p>
  </body>
</html>""",
        )
        zf.writestr(
            "OEBPS/chapter2.xhtml",
            """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Ch2</title></head>
  <body>
    <h1>chapter 2 title</h1>
    <p>chapter two para one</p>
  </body>
</html>""",
        )
        zf.writestr("OEBPS/style.css", "p { color: #222; }")


def _paragraph_inner_html(epub_path: Path, chapter_path: str, index: int) -> str:
    with ZipFile(epub_path) as zf:
        root = etree.fromstring(zf.read(chapter_path))
    elements = root.xpath(".//*[local-name()='p' or local-name()='h1']")
    element = elements[index]
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(etree.tostring(child, encoding="unicode"))
    return "".join(parts).strip()


class TestPatchEpubParagraphs:
    def test_patches_requested_paragraphs_by_chapter_and_index(self, tmp_path):
        epub_path = tmp_path / "book.epub"
        _build_sample_epub(epub_path)

        patch_epub_paragraphs(
            epub_path,
            {
                "ch000_p1": "updated <strong>paragraph</strong> one",
                "ch001_p0": "updated chapter 2 title",
            },
        )

        ch1_second = _paragraph_inner_html(epub_path, "OEBPS/chapter1.xhtml", 1)
        ch2_first = _paragraph_inner_html(epub_path, "OEBPS/chapter2.xhtml", 0)
        untouched = _paragraph_inner_html(epub_path, "OEBPS/chapter1.xhtml", 0)

        assert ch1_second.startswith("updated ")
        assert "<strong" in ch1_second
        assert "paragraph" in ch1_second
        assert ch1_second.endswith("</strong> one")
        assert ch2_first == "updated chapter 2 title"
        assert untouched == "first chapter para one"

        with ZipFile(epub_path) as zf:
            assert zf.read("OEBPS/style.css").decode("utf-8") == "p { color: #222; }"

    def test_raises_for_invalid_paragraph_id(self, tmp_path):
        epub_path = tmp_path / "book.epub"
        _build_sample_epub(epub_path)

        with pytest.raises(ValueError, match="Invalid paragraph id"):
            patch_epub_paragraphs(epub_path, {"bad-id": "x"})

    def test_raises_for_invalid_inner_html(self, tmp_path):
        epub_path = tmp_path / "book.epub"
        _build_sample_epub(epub_path)

        with pytest.raises(ValueError, match="Invalid HTML fragment"):
            patch_epub_paragraphs(epub_path, {"ch000_p0": "<strong>broken"})

    def test_patches_inline_edit_unit_strong(self, strong_para_epub):
        patch_epub_paragraphs(strong_para_epub, {"ch000_p0": "updated"})
        with ZipFile(strong_para_epub) as zf:
            root = etree.fromstring(zf.read("OEBPS/chapter1.xhtml"))
        p_elements = root.xpath(".//*[local-name()='p']")
        assert len(p_elements) == 1
        p = p_elements[0]
        strong_children = [c for c in p if etree.QName(c).localname == "strong"]
        assert len(strong_children) == 1, "Expected <p> to still contain <strong>"
        assert strong_children[0].text == "updated"
