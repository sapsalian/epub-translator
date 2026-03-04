"""Tests for the download route logic (without starting NiceGUI server)."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.gui.jobs.manager import JobManager


class TestDownloadRouteLogic:
    """Test the route handler logic by calling it directly."""

    def setup_method(self):
        self.manager = JobManager()

    def test_resolve_valid_token_returns_path(self, tmp_path):
        output_file = tmp_path / "book_ko.epub"
        output_file.write_bytes(b"fake epub content")
        token = self.manager.register_download(output_file)
        resolved = self.manager.resolve_download(token)
        assert resolved == output_file

    def test_resolve_invalid_token_returns_none(self):
        assert self.manager.resolve_download("badtoken") is None

    def test_resolve_after_file_deleted(self, tmp_path):
        output_file = tmp_path / "book_ko.epub"
        output_file.write_bytes(b"fake epub")
        token = self.manager.register_download(output_file)
        output_file.unlink()
        resolved = self.manager.resolve_download(token)
        # Token still resolves, but file doesn't exist
        assert resolved is not None
        assert not resolved.exists()

    def test_remove_token_makes_resolve_return_none(self, tmp_path):
        output_file = tmp_path / "book_ko.epub"
        output_file.write_bytes(b"fake epub")
        token = self.manager.register_download(output_file)
        self.manager.remove_download_token(token)
        assert self.manager.resolve_download(token) is None

    @pytest.mark.asyncio
    async def test_download_route_returns_404_for_bad_token(self):
        """Import and call the route handler with a patched job_manager."""
        import src.gui.routes.download as route_module

        with patch.object(route_module, "job_manager", self.manager):
            response = await route_module.download_file("nonexistent_token")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_route_returns_410_when_file_missing(self, tmp_path):
        import src.gui.routes.download as route_module

        output_file = tmp_path / "missing.epub"
        # Register without creating the file
        token = self.manager.register_download(output_file)

        with patch.object(route_module, "job_manager", self.manager):
            response = await route_module.download_file(token)
        assert response.status_code == 410

    @pytest.mark.asyncio
    async def test_download_route_returns_file_response_when_valid(self, tmp_path):
        from fastapi.responses import FileResponse
        import src.gui.routes.download as route_module

        output_file = tmp_path / "book_ko.epub"
        output_file.write_bytes(b"epub content")
        token = self.manager.register_download(output_file)

        with patch.object(route_module, "job_manager", self.manager):
            response = await route_module.download_file(token)

        assert isinstance(response, FileResponse)
        assert response.media_type == "application/epub+zip"
