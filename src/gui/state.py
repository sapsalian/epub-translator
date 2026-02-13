from dataclasses import dataclass, field
from pathlib import Path

from src.pipeline import Language

from .credentials import get_api_key


@dataclass
class AppState:
    source_language: Language = Language.ENGLISH
    target_language: Language = Language.KOREAN
    # model is fixed to gpt-4.1-mini (not user configurable)
    custom_instructions: str = ""
    openai_api_key: str = field(default_factory=get_api_key)
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    checkpoint_dir: Path = field(default_factory=lambda: Path("./checkpoints"))
    checkpoint_retention_days: int = 7
    current_epub: Path | None = None
    is_running: bool = False


# Global singleton
app_state = AppState()
