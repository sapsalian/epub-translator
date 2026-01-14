from pathlib import Path
from zipfile import ZipFile

from .parser import get_spine_xhtml_paths_by_order
from .types import XhtmlProcessorFunc, FileProcessorFunc

__all__ = ["walk_ordered_xhtmls", "walk_all_files"]

def walk_ordered_xhtmls(epub_path: Path, xhtml_func: XhtmlProcessorFunc) -> None:
    """
    Walks through all xhtml files in an EPUB file in spine order and applies a function to each.

    Args:
        epub_path (Path): The path to the EPUB file.
        xhtml_func (Callable[[IO[bytes]], None]): A function to process each xhtml file.
    """
    
    with ZipFile(epub_path, "r") as zf:
        ordered_xhtml_paths = get_spine_xhtml_paths_by_order(zf)
        for path in ordered_xhtml_paths:
            with zf.open(path.as_posix()) as xhtml_file:
                xhtml_func(xhtml_file)
                    

def walk_all_files(epub_path: Path, file_func: FileProcessorFunc) -> None:
    """
    Walks through all files in an EPUB file and applies a function to each.

    Args:
        epub_path (Path): The path to the EPUB file.
        file_func (Callable[[str, IO[bytes]], None]): A function to process each file.
    """
    
    with ZipFile(epub_path, "r") as zf:
        for item in zf.infolist():
            with zf.open(item.filename) as file:
                file_func(file, item)