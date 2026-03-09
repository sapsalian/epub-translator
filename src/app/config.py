"""Application configuration with directory paths."""

from dataclasses import dataclass, field
from pathlib import Path


def _default_base_dir() -> Path:
    return Path.home() / ".epub-translator"


@dataclass
class AppConfig:
    base_dir: Path = field(default_factory=_default_base_dir)

    @property
    def settings_path(self) -> Path:
        return self.base_dir / "settings.json"

    @property
    def jobs_path(self) -> Path:
        return self.base_dir / "jobs.json"

    @property
    def upload_dir(self) -> Path:
        return self.base_dir / "uploads"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "output"

    @property
    def checkpoint_dir(self) -> Path:
        return self.base_dir / "checkpoints"

    @property
    def workspace_dir(self) -> Path:
        return self.base_dir / "workspaces"

    def ensure_dirs(self) -> None:
        for d in (self.upload_dir, self.output_dir, self.checkpoint_dir, self.workspace_dir):
            d.mkdir(parents=True, exist_ok=True)
