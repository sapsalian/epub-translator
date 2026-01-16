"""
Experimental demo: Text replacement strategies for EPUB translation.

This demo shows how to use the matchers package to identify elements
for text replacement. Each matcher implements a different strategy.
"""

from epub_editor import edit_epub
from matchers import TargetTagMatcher, TextEmergenceMatcher, PhrasingContentMatcher, ElementMatcher
from lxml import etree
from zipfile import ZipInfo


def create_text_replacer(matcher: ElementMatcher):
    """
    Create a DOM editor function that uses the given matcher.

    Args:
        matcher: An ElementMatcher instance to filter elements.

    Returns:
        A function compatible with edit_epub's xhtml_editor parameter.
    """
    def replace_text(tree: etree._Element, file_info: ZipInfo) -> None:
        # Must wrap with list() to avoid modifying tree during iteration
        for elem in list(tree.iter()):
            if matcher(elem):
                text = "".join(elem.itertext()).strip()
                if not text:
                    continue
                for child in list(elem):
                    elem.remove(child)
                elem.text = f"[Translated: {text}]"

    return replace_text

# Example usage with different matchers
matcher = TextEmergenceMatcher()
edit_epub('demo_files/sample.epub', 'demo_files/translated.epub', create_text_replacer(matcher))
