"""
Filters for selecting translatable elements.

Provides composition-based filtering that wraps ElementMatcher instances
to add translation-specific constraints.
"""

from lxml import etree

from src.matchers.base import ElementMatcher

from .constants import UNTRANSLATABLE_TAGS


class TranslatableElementFilter:
    """
    Filter that wraps an ElementMatcher to exclude untranslatable elements.

    Checks that neither the element itself nor any of its ancestors
    are in the UNTRANSLATABLE_TAGS set before delegating to the inner matcher.

    Example:
        matcher = TextEmergenceMatcher()
        filter = TranslatableElementFilter(matcher)

        for elem in tree.iter():
            if filter(elem):
                # This element is translatable
                ...
    """

    def __init__(self, matcher: ElementMatcher) -> None:
        """
        Initialize the filter with an inner matcher.

        Args:
            matcher: The ElementMatcher to wrap.
        """
        self._matcher = matcher

    def __call__(self, elem: etree._Element) -> bool:
        """
        Check if an element should be translated.

        Args:
            elem: The element to check.

        Returns:
            True if the element matches and is translatable.
        """
        # Check if element itself is untranslatable
        tag_name = self._get_local_name(elem)
        if tag_name in UNTRANSLATABLE_TAGS:
            return False

        # Check ancestors
        if self._has_untranslatable_ancestor(elem):
            return False

        # Delegate to inner matcher
        return self._matcher(elem)

    def reset(self) -> None:
        """Reset the inner matcher's state."""
        self._matcher.reset()

    def _has_untranslatable_ancestor(self, elem: etree._Element) -> bool:
        """
        Check if any ancestor is an untranslatable tag.

        Args:
            elem: The element to check.

        Returns:
            True if any ancestor is untranslatable.
        """
        for ancestor in elem.iterancestors():
            tag_name = self._get_local_name(ancestor)
            if tag_name in UNTRANSLATABLE_TAGS:
                return True
        return False

    def _get_local_name(self, elem: etree._Element) -> str:
        """
        Get the local name of an element (without namespace).

        Args:
            elem: The element.

        Returns:
            Lowercase local name of the tag.
        """
        if isinstance(elem.tag, str):
            return etree.QName(elem.tag).localname.lower()
        return ""
