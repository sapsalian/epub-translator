"""
Experimental demo: Text replacement strategies for EPUB translation.

This demo shows how to use the matchers package to identify elements
for text replacement. Each matcher implements a different strategy.
"""

from epub_editor import edit_epub_elements
from epub_editor.base import ElemEditor
from matchers import TargetTagMatcher, TextEmergenceMatcher, PhrasingContentMatcher, ElementMatcher
from lxml import etree
from zipfile import ZipInfo


class TextReplacer(ElemEditor):
    """Element editor that replaces text with a translated placeholder."""

    def edit_element(self, elem: etree._Element, zip_info: ZipInfo) -> None:
        # Must wrap with list() to avoid modifying tree during iteration
        text = "".join(elem.itertext()).strip()
        if not text:
            return
        for child in list(elem):
            elem.remove(child)
        elem.text = f"[Translated: {text}]"


# Example usage with different matchers
matcher = TextEmergenceMatcher()
edit_epub_elements('demo_files/sample.epub', 'demo_files/translated.epub', TextReplacer(), matcher)
