from pathlib import Path
from zipfile import ZipFile

from .parser import get_spine_xhtml_paths_by_order

__all__ = ["walk_xhtmls"]

def walk_xhtmls(epub_path: Path, xhtml_func) -> None:
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
                    