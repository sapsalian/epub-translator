"""Job data models for the translation queue."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from src.pipeline.models import Language


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


@dataclass
class JobInfo:
    job_id: str
    epub_filename: str
    epub_path_str: str        # str to avoid Path serialization issues
    email: str
    source_language: Language
    target_language: Language
    custom_instructions: str
    state: JobState = JobState.QUEUED
    progress: float = 0.0    # 0.0 ~ 1.0
    stage: str = ""
    error: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    download_token: str | None = None
