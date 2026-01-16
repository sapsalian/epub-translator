"""
Demo: Rewriting an EPUB file with modified content.

This script demonstrates how to read an EPUB, modify its XHTML content,
and write it back to a new EPUB file.
"""

from lxml import etree
from epub_editor import edit_epub_elements
from epub_editor.base import ElemEditor
from zipfile import ZipInfo


class ReverseTextEditor(ElemEditor):
    """Element editor that reverses text and tail of each element."""

    def edit_element(self, elem: etree._Element, zip_info: ZipInfo) -> None:
        if elem.text and elem.text.strip():
            elem.text = elem.text[::-1]
        if elem.tail and elem.tail.strip():
            elem.tail = elem.tail[::-1]


edit_epub_elements('demo_files/sample.epub', 'demo_files/reversed.epub', ReverseTextEditor())
print("Done: reversed.epub has been created.")