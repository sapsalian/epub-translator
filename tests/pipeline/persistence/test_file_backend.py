"""Tests for file-based persistence backend."""

import pytest
import pytest_asyncio
import tempfile
from pathlib import Path

from src.pipeline.persistence.file_backend import FilePersistenceBackend
from src.pipeline.persistence.base import PersistenceError


@pytest_asyncio.fixture
async def backend():
    """Create a temporary backend for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        backend = FilePersistenceBackend(tmpdir)
        await backend.initialize()
        yield backend


class TestFilePersistenceBackend:
    """Tests for FilePersistenceBackend."""

    @pytest.mark.asyncio
    async def test_save_and_load(self, backend: FilePersistenceBackend):
        """Data can be saved and loaded."""
        await backend.save("test:key", '{"value": 123}')
        data = await backend.load("test:key")
        assert data == '{"value": 123}'

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, backend: FilePersistenceBackend):
        """Loading nonexistent key returns None."""
        data = await backend.load("nonexistent:key")
        assert data is None

    @pytest.mark.asyncio
    async def test_exists_true(self, backend: FilePersistenceBackend):
        """exists returns True for existing key."""
        await backend.save("test:key", "data")
        assert await backend.exists("test:key") is True

    @pytest.mark.asyncio
    async def test_exists_false(self, backend: FilePersistenceBackend):
        """exists returns False for nonexistent key."""
        assert await backend.exists("nonexistent:key") is False

    @pytest.mark.asyncio
    async def test_delete(self, backend: FilePersistenceBackend):
        """Data can be deleted."""
        await backend.save("test:key", "data")
        await backend.delete("test:key")
        assert await backend.exists("test:key") is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend: FilePersistenceBackend):
        """Deleting nonexistent key doesn't raise."""
        await backend.delete("nonexistent:key")  # Should not raise

    @pytest.mark.asyncio
    async def test_list_keys_with_prefix(self, backend: FilePersistenceBackend):
        """list_keys returns matching keys."""
        await backend.save("epub1:extraction", "data1")
        await backend.save("epub1:translation:x1:ko", "data2")
        await backend.save("epub1:translation:x2:ko", "data3")
        await backend.save("epub2:extraction", "data4")

        keys = await backend.list_keys("epub1:")
        assert len(keys) == 3
        assert "epub1:extraction" in keys
        assert "epub1:translation:x1:ko" in keys
        assert "epub1:translation:x2:ko" in keys

    @pytest.mark.asyncio
    async def test_list_keys_empty(self, backend: FilePersistenceBackend):
        """list_keys returns empty list when no matches."""
        await backend.save("epub1:extraction", "data")
        keys = await backend.list_keys("epub999:")
        assert keys == []

    @pytest.mark.asyncio
    async def test_clear_prefix(self, backend: FilePersistenceBackend):
        """clear_prefix deletes matching keys."""
        await backend.save("epub1:extraction", "data1")
        await backend.save("epub1:translation:x1:ko", "data2")
        await backend.save("epub2:extraction", "data3")

        count = await backend.clear_prefix("epub1:")
        assert count == 2

        assert await backend.exists("epub1:extraction") is False
        assert await backend.exists("epub1:translation:x1:ko") is False
        assert await backend.exists("epub2:extraction") is True

    @pytest.mark.asyncio
    async def test_get_all_epub_ids(self, backend: FilePersistenceBackend):
        """get_all_epub_ids returns unique epub IDs."""
        await backend.save("epub1:extraction", "data1")
        await backend.save("epub1:translation:x1:ko", "data2")
        await backend.save("epub2:extraction", "data3")
        await backend.save("epub3:status:ko", "data4")

        ids = await backend.get_all_epub_ids()
        assert ids == {"epub1", "epub2", "epub3"}

    @pytest.mark.asyncio
    async def test_key_to_filename_conversion(self, backend: FilePersistenceBackend):
        """Keys with colons are properly converted to filenames."""
        key = "epub123:translation:xhtml001:ko"
        filename = backend._key_to_filename(key)
        assert ":" not in filename
        assert filename.endswith(".json")

        # Convert back
        restored = backend._filename_to_key(filename)
        assert restored == key

    @pytest.mark.asyncio
    async def test_overwrite_existing(self, backend: FilePersistenceBackend):
        """Saving to existing key overwrites."""
        await backend.save("test:key", "original")
        await backend.save("test:key", "updated")
        data = await backend.load("test:key")
        assert data == "updated"

    @pytest.mark.asyncio
    async def test_unicode_content(self, backend: FilePersistenceBackend):
        """Unicode content is handled correctly."""
        content = '{"text": "한글 테스트 🎉"}'
        await backend.save("test:unicode", content)
        loaded = await backend.load("test:unicode")
        assert loaded == content


class TestFilePersistenceBackendProtocol:
    """Verify FilePersistenceBackend implements PersistenceBackend Protocol."""

    def test_implements_protocol(self):
        """FilePersistenceBackend can be used where PersistenceBackend is expected."""
        from src.pipeline.persistence.base import PersistenceBackend

        backend = FilePersistenceBackend("/tmp")
        assert isinstance(backend, PersistenceBackend)
