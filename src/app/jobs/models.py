"""Job data models for the translation queue."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobState(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


@dataclass
class JobInfo:
    job_id: str
    filename: str
    upload_id: str
    source_language: str
    target_language: str
    custom_instructions: str = ""
    state: JobState = JobState.QUEUED
    progress: float = 0.0
    stage: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    download_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "upload_id": self.upload_id,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "custom_instructions": self.custom_instructions,
            "state": self.state.value,
            "progress": self.progress,
            "stage": self.stage,
            "error": self.error,
            "created_at": self.created_at,
            "download_token": self.download_token,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobInfo":
        return cls(
            job_id=data["job_id"],
            filename=data["filename"],
            upload_id=data["upload_id"],
            source_language=data.get("source_language", "en"),
            target_language=data.get("target_language", "ko"),
            custom_instructions=data.get("custom_instructions", ""),
            state=JobState(data.get("state", "queued")),
            progress=data.get("progress", 0.0),
            stage=data.get("stage", ""),
            error=data.get("error", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            download_token=data.get("download_token"),
        )
