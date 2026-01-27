"""
Abstract base for persistence backends.

Defines the Protocol that all persistence backends must implement,
enabling swappable storage (file-based, Redis, etc.).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PersistenceBackend(Protocol):
    """
    Protocol for persistence backends.

    All methods are async to support both local file I/O (with aiofiles)
    and network-based storage (Redis, cloud storage, etc.).

    Keys follow the pattern: {epub_id}:{type}:{optional_qualifiers}
    Examples:
        - "abc123:extraction"
        - "abc123:preprocess:ko"
        - "abc123:translation:xhtml001:ko"
        - "abc123:status"
    """

    async def save(self, key: str, data: str) -> None:
        """
        Save data to storage.

        Args:
            key: Unique key for the data.
            data: JSON string to store.

        Raises:
            PersistenceError: If save fails.
        """
        ...

    async def load(self, key: str) -> str | None:
        """
        Load data from storage.

        Args:
            key: Key to load.

        Returns:
            JSON string if found, None otherwise.

        Raises:
            PersistenceError: If load fails (other than not found).
        """
        ...

    async def delete(self, key: str) -> None:
        """
        Delete data from storage.

        Args:
            key: Key to delete.

        Raises:
            PersistenceError: If delete fails.
        """
        ...

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in storage.

        Args:
            key: Key to check.

        Returns:
            True if key exists, False otherwise.
        """
        ...

    async def list_keys(self, prefix: str) -> list[str]:
        """
        List all keys matching a prefix.

        Args:
            prefix: Key prefix to match (e.g., "abc123:" for all keys of an epub).

        Returns:
            List of matching keys.
        """
        ...

    async def clear_prefix(self, prefix: str) -> int:
        """
        Delete all keys matching a prefix.

        Args:
            prefix: Key prefix to match.

        Returns:
            Number of keys deleted.
        """
        ...


class PersistenceError(Exception):
    """Base exception for persistence operations."""

    pass
