"""Tests for AppConfig."""

from pathlib import Path

from src.app.config import AppConfig


class TestAppConfig:
    def test_default_base_dir(self):
        config = AppConfig()
        assert config.base_dir == Path.home() / ".epub-translator"

    def test_custom_base_dir(self, tmp_path):
        config = AppConfig(base_dir=tmp_path)
        assert config.settings_path == tmp_path / "settings.json"
        assert config.jobs_path == tmp_path / "jobs.json"
        assert config.upload_dir == tmp_path / "uploads"
        assert config.output_dir == tmp_path / "output"
        assert config.checkpoint_dir == tmp_path / "checkpoints"
        assert config.workspace_dir == tmp_path / "workspaces"
        assert config.source_epub_dir == tmp_path / "source_epubs"

    def test_ensure_dirs(self, tmp_path):
        config = AppConfig(base_dir=tmp_path)
        config.ensure_dirs()
        assert config.upload_dir.is_dir()
        assert config.output_dir.is_dir()
        assert config.checkpoint_dir.is_dir()
        assert config.workspace_dir.is_dir()
        assert config.source_epub_dir.is_dir()
