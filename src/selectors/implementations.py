"""
Concrete element selector implementations.

Each selector defines a different strategy for identifying elements
that should be processed (e.g., translated) in XHTML content.
"""

from lxml import etree
from .base import ElementSelector


class TargetTagSelector(ElementSelector):
    """
    Select elements by tag name, excluding those nested under same target tags.

    Useful for block-level elements like paragraphs and headings where
    nested duplicates should be avoided.
    """

    DEFAULT_TAGS = {
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'li', 'blockquote', 'td', 'th', 'dt', 'dd',
        'caption', 'figcaption'
    }

    def __init__(self, target_tags: set[str] | None = None):
        """
        Args:
            target_tags: Set of tag names to select. Uses DEFAULT_TAGS if None.
        """
        self.target_tags = target_tags or self.DEFAULT_TAGS

    def select(self, elem: etree._Element) -> bool:
        tag_name = etree.QName(elem).localname
        if tag_name not in self.target_tags:
            return False
        return not self._has_target_ancestor(elem)

    def _has_target_ancestor(self, elem: etree._Element) -> bool:
        for ancestor in elem.iterancestors():
            ancestor_tag = etree.QName(ancestor).localname
            if ancestor_tag in self.target_tags:
                return True
        return False


class TextEmergenceSelector(ElementSelector):
    """
    Select elements where text content directly emerges.

    An element is selected if it has non-empty elem.text or any child has
    non-empty tail text. This captures elements where visible text appears.
    """

    def select(self, elem: etree._Element) -> bool:
        if elem.text and elem.text.strip():
            return True
        for child in elem:
            if child.tail and child.tail.strip():
                return True
        return False


class PhrasingContentSelector(ElementSelector):
    """
    Select elements whose children are all phrasing (inline) content.

    Phrasing content elements are inline-level elements like span, strong, em, etc.
    This selector identifies "leaf" block elements that contain only inline content.
    """

    DEFAULT_PHRASING_TAGS = {
        'span', 'strong', 'em', 'b', 'i', 'u', 's', 'small', 'mark',
        'cite', 'dfn', 'abbr', 'sub', 'sup', 'code', 'kbd', 'samp',
        'var', 'q', 'data', 'time', 'a', 'img', 'picture', 'map',
        'area', 'ruby', 'rt', 'rp', 'br', 'wbr'
    }

    def __init__(self, phrasing_tags: set[str] | None = None):
        """
        Args:
            phrasing_tags: Set of phrasing content tag names. Uses DEFAULT_PHRASING_TAGS if None.
        """
        self.phrasing_tags = phrasing_tags or self.DEFAULT_PHRASING_TAGS

    def select(self, elem: etree._Element) -> bool:
        for child in elem:
            child_tag = etree.QName(child).localname
            if child_tag not in self.phrasing_tags:
                return False
        return True
