"""
Experimental demo: Text replacement strategies for EPUB translation.

This demo shows how to use the selectors package to identify elements
for text replacement. Each selector implements a different strategy.
"""

from epub_editor import edit_epub
from selectors import TargetTagSelector, TextEmergenceSelector, PhrasingContentSelector
from lxml import etree
from zipfile import ZipInfo


def create_text_replacer(selector):
    """
    Create a DOM editor function that uses the given selector.

    Args:
        selector: An ElementSelector instance to filter elements.

    Returns:
        A function compatible with edit_epub's xhtml_editor parameter.
    """
    def replace_text(tree: etree._Element, file_info: ZipInfo) -> None:
        # Must wrap with list() to avoid modifying tree during iteration
        for elem in list(tree.iter()):
            if selector(elem):
                text = "".join(elem.itertext()).strip()
                if not text:
                    continue
                for child in list(elem):
                    elem.remove(child)
                elem.text = f"[Translated: {text}]"

    return replace_text

# Example usage with different selectors
selector = TextEmergenceSelector()
edit_epub('demo_files/sample.epub', 'demo_files/translated.epub', create_text_replacer(selector))
