from pathlib import Path
from typing import Protocol


class FileProvider(Protocol):
    async def get_epub_path(self, file_ref: str) -> Path: ...
    async def save_output(self, local_path: Path) -> str: ...


class LocalFileProvider:
    """Desktop mode: use local paths directly"""

    async def get_epub_path(self, file_ref: str) -> Path:
        return Path(file_ref)

    async def save_output(self, local_path: Path) -> str:
        return str(local_path)
