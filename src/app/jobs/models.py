"""Job data models for the translation queue."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobState(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
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
    workflow_mode: str = "classic"
    workflow_options: dict[str, Any] = field(default_factory=dict)
    state: JobState = JobState.QUEUED
    progress: float = 0.0
    stage: str = ""
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    epub_id: str | None = None
    input_path: str | None = None
    source_epub_path: str | None = None
    download_token: str | None = None
    output_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "filename": self.filename,
            "upload_id": self.upload_id,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "custom_instructions": self.custom_instructions,
            "workflow_mode": self.workflow_mode,
            "workflow_options": self.workflow_options,
            "state": self.state.value,
            "progress": self.progress,
            "stage": self.stage,
            "error": self.error,
            "created_at": self.created_at,
            "epub_id": self.epub_id,
            "input_path": self.input_path,
            "source_epub_path": self.source_epub_path,
            "download_token": self.download_token,
            "output_path": self.output_path,
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
            workflow_mode=data.get("workflow_mode", "classic"),
            workflow_options=data.get("workflow_options", {}),
            state=JobState(data.get("state", "queued")),
            progress=data.get("progress", 0.0),
            stage=data.get("stage", ""),
            error=data.get("error", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            epub_id=data.get("epub_id"),
            input_path=data.get("input_path"),
            source_epub_path=data.get("source_epub_path"),
            download_token=data.get("download_token"),
            output_path=data.get("output_path"),
        )
