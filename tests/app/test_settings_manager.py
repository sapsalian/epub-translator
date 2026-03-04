"""Tests for SettingsManager."""

import json

from src.app.settings.manager import AppSettings, SettingsManager


class TestAppSettings:
    def test_to_public_dict_hides_api_key(self):
        s = AppSettings(openai_api_key="sk-secret")
        public = s.to_public_dict()
        assert "openai_api_key" not in public
        assert public["api_key_set"] is True

    def test_to_public_dict_api_key_not_set(self):
        s = AppSettings()
        assert s.to_public_dict()["api_key_set"] is False


class TestSettingsManager:
    def test_defaults_when_no_file(self, tmp_path):
        manager = SettingsManager(tmp_path / "settings.json")
        assert manager.settings.model == "gpt-4.1-mini"
        assert manager.settings.source_language == "en"
        assert manager.settings.target_language == "ko"
        assert manager.settings.openai_api_key == ""

    def test_update_persists_to_file(self, tmp_path):
        path = tmp_path / "settings.json"
        manager = SettingsManager(path)
        manager.update(model="gpt-4o", openai_api_key="sk-test")

        assert manager.settings.model == "gpt-4o"
        assert manager.settings.openai_api_key == "sk-test"

        data = json.loads(path.read_text())
        assert data["model"] == "gpt-4o"
        assert data["openai_api_key"] == "sk-test"

    def test_reload_from_file(self, tmp_path):
        path = tmp_path / "settings.json"
        manager = SettingsManager(path)
        manager.update(model="gpt-4o")

        manager2 = SettingsManager(path)
        assert manager2.settings.model == "gpt-4o"

    def test_corrupted_json_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{invalid json!!")

        manager = SettingsManager(path)
        assert manager.settings.model == "gpt-4.1-mini"

    def test_partial_update(self, tmp_path):
        manager = SettingsManager(tmp_path / "settings.json")
        manager.update(source_language="ja")
        assert manager.settings.source_language == "ja"
        assert manager.settings.target_language == "ko"
