"""Persistent settings stored in ~/.epub-translator/settings.json."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AppSettings:
    openai_api_key: str = ""
    model: str = "gpt-4.1-mini"
    source_language: str = "en"
    target_language: str = "ko"

    def to_dict(self) -> dict[str, Any]:
        return {
            "openai_api_key": self.openai_api_key,
            "model": self.model,
            "source_language": self.source_language,
            "target_language": self.target_language,
        }

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "api_key_set": bool(self.openai_api_key),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        return cls(
            openai_api_key=data.get("openai_api_key", ""),
            model=data.get("model", "gpt-4.1-mini"),
            source_language=data.get("source_language", "en"),
            target_language=data.get("target_language", "ko"),
        )


class SettingsManager:
    def __init__(self, settings_path: Path) -> None:
        self._path = settings_path
        self._settings = self._load()

    def _load(self) -> AppSettings:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                return AppSettings.from_dict(data)
            except (json.JSONDecodeError, KeyError):
                pass
        return AppSettings()

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._settings.to_dict(), indent=2))

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def update(self, **kwargs: Any) -> AppSettings:
        for key, value in kwargs.items():
            if hasattr(self._settings, key) and value is not None:
                setattr(self._settings, key, value)
        self._save()
        return self._settings
