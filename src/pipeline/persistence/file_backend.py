"""
File-based persistence backend.

Stores checkpoint data as JSON files in a specified directory.
Thread-safe through atomic file writes.
"""

import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path

import aiofiles
import aiofiles.os

from .base import PersistenceBackend, PersistenceError

logger = logging.getLogger(__name__)


class FilePersistenceBackend:
    """
    File-based implementation of PersistenceBackend.

    Stores each key as a separate JSON file with the key encoded
    in the filename. Uses atomic writes to prevent corruption.

    File naming: keys are converted by replacing ':' with '__'
    Example: "abc123:extraction" -> "abc123__extraction.json"
    """

    def __init__(self, base_dir: str | Path) -> None:
        """
        Initialize the file backend.

        Args:
            base_dir: Directory to store checkpoint files.
                      Will be created if it doesn't exist.
        """
        self._base_dir = Path(base_dir)
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """
        Initialize the backend (create directory if needed).

        Should be called before first use.
        """
        await aiofiles.os.makedirs(self._base_dir, exist_ok=True)
        logger.debug("Initialized file backend at %s", self._base_dir)

    def _key_to_filename(self, key: str) -> str:
        """Convert a key to a safe filename."""
        # Replace colons with double underscores
        safe_key = key.replace(":", "__")
        return f"{safe_key}.json"

    def _filename_to_key(self, filename: str) -> str:
        """Convert a filename back to a key."""
        # Remove .json extension and restore colons
        key = filename.removesuffix(".json")
        return key.replace("__", ":")

    def _get_path(self, key: str) -> Path:
        """Get the full path for a key."""
        return self._base_dir / self._key_to_filename(key)

    async def save(self, key: str, data: str) -> None:
        """
        Save data to a file atomically.

        Uses write-to-temp-then-rename pattern for atomicity.
        """
        path = self._get_path(key)

        try:
            # Ensure directory exists
            await aiofiles.os.makedirs(path.parent, exist_ok=True)

            # Write to temp file first, then rename (atomic on POSIX)
            fd, temp_path = tempfile.mkstemp(
                dir=self._base_dir,
                prefix=".tmp_",
                suffix=".json",
            )
            os.close(fd)

            try:
                async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                    await f.write(data)

                # Atomic rename
                await aiofiles.os.replace(temp_path, path)
                logger.debug("Saved checkpoint: %s", key)

            except Exception:
                # Clean up temp file on error
                try:
                    await aiofiles.os.remove(temp_path)
                except OSError:
                    pass
                raise

        except Exception as e:
            raise PersistenceError(f"Failed to save key '{key}': {e}") from e

    async def load(self, key: str) -> str | None:
        """Load data from a file."""
        path = self._get_path(key)

        try:
            if not await aiofiles.os.path.exists(path):
                return None

            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                data = await f.read()

            logger.debug("Loaded checkpoint: %s", key)
            return data

        except FileNotFoundError:
            return None
        except Exception as e:
            raise PersistenceError(f"Failed to load key '{key}': {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a file."""
        path = self._get_path(key)

        try:
            if await aiofiles.os.path.exists(path):
                await aiofiles.os.remove(path)
                logger.debug("Deleted checkpoint: %s", key)

        except FileNotFoundError:
            pass  # Already deleted
        except Exception as e:
            raise PersistenceError(f"Failed to delete key '{key}': {e}") from e

    async def exists(self, key: str) -> bool:
        """Check if a file exists."""
        path = self._get_path(key)
        return await aiofiles.os.path.exists(path)

    async def list_keys(self, prefix: str) -> list[str]:
        """List all keys matching a prefix."""
        try:
            # Convert prefix to filename prefix
            filename_prefix = prefix.replace(":", "__")

            keys: list[str] = []
            if await aiofiles.os.path.exists(self._base_dir):
                for entry in await aiofiles.os.listdir(self._base_dir):
                    if entry.startswith(filename_prefix) and entry.endswith(".json"):
                        key = self._filename_to_key(entry)
                        keys.append(key)

            return sorted(keys)

        except Exception as e:
            raise PersistenceError(f"Failed to list keys with prefix '{prefix}': {e}") from e

    async def clear_prefix(self, prefix: str) -> int:
        """Delete all keys matching a prefix."""
        keys = await self.list_keys(prefix)
        for key in keys:
            await self.delete(key)
        logger.info("Cleared %d keys with prefix '%s'", len(keys), prefix)
        return len(keys)

    async def get_all_epub_ids(self) -> set[str]:
        """
        Get all unique epub_ids from stored keys.

        Returns:
            Set of epub_ids that have any stored data.
        """
        try:
            epub_ids: set[str] = set()

            if await aiofiles.os.path.exists(self._base_dir):
                for entry in await aiofiles.os.listdir(self._base_dir):
                    if entry.endswith(".json") and not entry.startswith("."):
                        key = self._filename_to_key(entry)
                        # epub_id is the first part before ':'
                        epub_id = key.split(":")[0]
                        epub_ids.add(epub_id)

            return epub_ids

        except Exception as e:
            raise PersistenceError(f"Failed to get epub_ids: {e}") from e


# Verify it implements the Protocol
def _check_protocol() -> None:
    """Static check that FilePersistenceBackend implements PersistenceBackend."""
    backend: PersistenceBackend = FilePersistenceBackend("/tmp")  # noqa: F841
