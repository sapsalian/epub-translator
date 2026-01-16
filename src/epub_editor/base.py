from abc import ABC, abstractmethod
from lxml import etree
from zipfile import ZipInfo


class ElemEditor(ABC):
    """Abstract base class for element-level editors.

    Subclasses must implement `edit_element` to define how individual
    XML elements should be modified.
    """

    @abstractmethod
    def edit_element(self, elem: etree._Element, zip_info: ZipInfo) -> None:
        """Edit a single XML element in place.

        Args:
            elem: The XML element to modify.
            zip_info: Metadata about the source file containing this element.
        """
        pass

    def __call__(self, elem: etree._Element, zip_info: ZipInfo) -> None:
        self.edit_element(elem, zip_info)


class DOMEditor(ABC):
    """Abstract base class for document-level editors.

    Subclasses must implement `edit_document` to define how entire
    XHTML document trees should be modified.
    """

    @abstractmethod
    def edit_document(self, root: etree._Element, zip_info: ZipInfo) -> None:
        """Edit an entire XHTML document tree in place.

        Args:
            root: The root element of the document tree.
            zip_info: Metadata about the source file.
        """
        pass

    def __call__(self, root: etree._Element, zip_info: ZipInfo) -> None:
        self.edit_document(root, zip_info)