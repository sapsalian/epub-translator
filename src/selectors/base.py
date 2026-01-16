"""
Base class for element selectors.

Selectors determine whether an element should be processed (e.g., translated).
"""

from abc import ABC, abstractmethod
from lxml import etree


class ElementSelector(ABC):
    """
    Abstract base class for element selection strategies.

    Subclasses implement the `select` method to define custom filtering logic.
    """

    @abstractmethod
    def select(self, elem: etree._Element) -> bool:
        """
        Determine whether the given element should be selected for processing.

        Args:
            elem: The element to evaluate.

        Returns:
            True if the element should be processed, False otherwise.
        """
        pass

    def __call__(self, elem: etree._Element) -> bool:
        """Allow selector to be used as a callable."""
        return self.select(elem)
