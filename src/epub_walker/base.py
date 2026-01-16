from abc import ABC, abstractmethod
from typing import IO
from zipfile import ZipInfo


class XhtmlProcessor(ABC):
    """Abstract base class for XHTML file processors.

    Subclasses must implement `process_xhtml` to define how each
    XHTML file should be processed.
    """

    @abstractmethod
    def process_xhtml(self, xhtml_file: IO[bytes]) -> None:
        """Process a single XHTML file.

        Args:
            xhtml_file: A file-like object containing the XHTML content.
        """
        pass

    def __call__(self, xhtml_file: IO[bytes]) -> None:
        self.process_xhtml(xhtml_file)


class FileProcessor(ABC):
    """Abstract base class for generic file processors.

    Subclasses must implement `process_file` to define how each
    file in the EPUB should be processed.
    """

    @abstractmethod
    def process_file(self, file: IO[bytes], zip_info: ZipInfo) -> None:
        """Process a single file from the EPUB.

        Args:
            file: A file-like object containing the file content.
            zip_info: Metadata about the file.
        """
        pass

    def __call__(self, file: IO[bytes], zip_info: ZipInfo) -> None:
        self.process_file(file, zip_info)