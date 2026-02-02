"""
Concrete element matcher implementations.

Each matcher defines a different strategy for identifying elements
that should be processed (e.g., translated) in XHTML content.
"""

from lxml import etree
from .base import ElementMatcher


class OuterContextMatcher(ElementMatcher):
    """
    Match elements by tag name, excluding those nested under same target tags.

    Useful for block-level elements like paragraphs and headings where
    nested duplicates should be avoided.
    """

    TARGET_TAGS = frozenset({
        'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'li', 'blockquote', 'td', 'th', 'dt', 'dd',
        'caption', 'figcaption'
    })

    def match(self, elem: etree._Element) -> bool:
        tag_name = etree.QName(elem).localname
        if tag_name not in self.TARGET_TAGS:
            return False
        return not self._has_target_ancestor(elem)

    def reset(self) -> None:
        pass

    def _has_target_ancestor(self, elem: etree._Element) -> bool:
        for ancestor in elem.iterancestors():
            ancestor_tag = etree.QName(ancestor).localname
            if ancestor_tag in self.TARGET_TAGS:
                return True
        return False


class TextEmergenceMatcher(ElementMatcher):
    """
    Match elements where text content first emerges.

    An element matches if it has non-empty elem.text or any child has
    non-empty tail text, AND no ancestor has text content. This ensures
    we only match the topmost element where text first appears.

    Uses caching for O(N) performance when matching all elements in a tree.
    Call reset() when processing a new document.
    """

    def __init__(self) -> None:
        self._cache: dict[int, bool] = {}

    def reset(self) -> None:
        """Clear the cache. Call this when processing a new document."""
        self._cache.clear()

    def match(self, elem: etree._Element) -> bool:
        if self._has_ancestor_text(elem):
            return False
        
        return self._has_direct_text(elem)

    def _has_ancestor_text(self, elem: etree._Element) -> bool:
        parent = elem.getparent()
        if parent is None:
            return False

        result = self._has_ancestor_text(parent) or self._has_direct_text(parent)
        return result

    def _has_direct_text(self, elem: etree._Element) -> bool:
        if elem.text and elem.text.strip():
            return True
        for child in elem:
            if child.tail and child.tail.strip():
                return True
        return False


class LeafBlockMatcher(ElementMatcher):
    """
    Match elements whose children are all phrasing (inline) content.

    Phrasing content elements are inline-level elements like span, strong, em, etc.
    This matcher identifies "leaf" block elements that contain only inline content.
    """

    PHRASING_TAGS = frozenset({
        'span', 'strong', 'em', 'b', 'i', 'u', 's', 'small', 'mark',
        'cite', 'dfn', 'abbr', 'sub', 'sup', 'code', 'kbd', 'samp',
        'var', 'q', 'data', 'time', 'a', 'img', 'picture', 'map',
        'area', 'ruby', 'rt', 'rp', 'br', 'wbr'
    })

    def match(self, elem: etree._Element) -> bool:
        for child in elem:
            child_tag = etree.QName(child).localname
            if child_tag not in self.PHRASING_TAGS:
                return False
        return True

    def reset(self) -> None:
        pass


class AllElementsMatcher(ElementMatcher):
    """
    Match all elements unconditionally.

    This matcher is useful when every element in the document
    needs to be processed without any filtering.
    """

    def match(self, elem: etree._Element) -> bool:
        return True

    def reset(self) -> None:
        pass