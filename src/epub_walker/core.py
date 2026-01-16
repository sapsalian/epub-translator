from pathlib import Path
from zipfile import ZipFile

from .parser import get_spine_xhtml_paths_by_order
from .base import XhtmlProcessor, FileProcessor


def walk_ordered_xhtmls(epub_path: Path, xhtml_processor: XhtmlProcessor) -> None:
    """
    Walks through all xhtml files in an EPUB file in spine order and applies a processor to each.

    Args:
        epub_path: The path to the EPUB file.
        xhtml_processor: A processor to handle each xhtml file.
    """
    with ZipFile(epub_path, "r") as zf:
        ordered_xhtml_paths = get_spine_xhtml_paths_by_order(zf)
        for path in ordered_xhtml_paths:
            with zf.open(path.as_posix()) as xhtml_file:
                xhtml_processor(xhtml_file)
                    

def walk_all_files(epub_path: Path, file_processor: FileProcessor) -> None:
    """
    Walks through all files in an EPUB file and applies a processor to each.

    Args:
        epub_path: The path to the EPUB file.
        file_processor: A processor to handle each file.
    """
    with ZipFile(epub_path, "r") as zf:
        for item in zf.infolist():
            with zf.open(item.filename) as file:
                file_processor(file, item)