"""
Base class for element matchers.

Matchers determine whether an element should be processed (e.g., translated).
"""

from abc import ABC, abstractmethod
from lxml import etree


class ElementMatcher(ABC):
    """
    Abstract base class for element matching strategies.

    Subclasses implement the `match` method to define custom filtering logic.
    """

    @abstractmethod
    def match(self, elem: etree._Element) -> bool:
        """
        Determine whether the given element matches the criteria for processing.

        Args:
            elem: The element to evaluate.

        Returns:
            True if the element should be processed, False otherwise.
        """
        pass

    def __call__(self, elem: etree._Element) -> bool:
        """Allow matcher to be used as a callable."""
        return self.match(elem)
