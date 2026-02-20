"""
Data models for job status and progress tracking.

These models are used to track translation job progress across
all pipeline stages, enabling resume functionality and real-time
progress reporting (e.g., via SSE).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class JobStage(str, Enum):
    """Current stage of a translation job."""

    PENDING = "pending"
    EXTRACTING = "extracting"
    PREPROCESSING = "preprocessing"
    TRANSLATING = "translating"
    INSERTING = "inserting"
    COMPLETED = "completed"
    FAILED = "failed"


class StageProgress(BaseModel):
    """Progress within a single stage."""

    total: int = Field(default=0, description="Total items to process")
    completed: int = Field(default=0, description="Items completed")

    @computed_field
    @property
    def percentage(self) -> float:
        """Progress percentage (0.0 to 100.0)."""
        if self.total <= 0:
            return 0.0
        return min(100.0, (self.completed / self.total) * 100)

    @computed_field
    @property
    def is_complete(self) -> bool:
        """Whether this stage is complete."""
        return self.total > 0 and self.completed >= self.total


# Stage weights for overall progress calculation
# Based on typical time distribution across stages
STAGE_WEIGHTS: dict[JobStage, tuple[float, float]] = {
    # (base_progress, weight)
    JobStage.PENDING: (0.0, 0.0),
    JobStage.EXTRACTING: (0.0, 0.05),    # 0–5%
    JobStage.PREPROCESSING: (0.05, 0.25), # 5–30%
    JobStage.TRANSLATING: (0.30, 0.65),   # 30–95%
    JobStage.INSERTING: (0.95, 0.05),     # 95–100%
    JobStage.COMPLETED: (1.0, 0.0),
    JobStage.FAILED: (0.0, 0.0),
}


class JobStatus(BaseModel):
    """
    Complete status of a translation job.

    Tracks progress across all pipeline stages and provides
    overall progress calculation for UI display.
    """

    epub_id: str = Field(description="EPUB identifier")
    target_language: str = Field(description="Target language code (e.g., 'ko')")
    stage: JobStage = Field(default=JobStage.PENDING, description="Current stage")

    # Per-stage progress (field names match JobStage enum values)
    extracting: StageProgress = Field(
        default_factory=StageProgress,
        description="Extraction progress (total = XHTML count)",
    )
    preprocessing: StageProgress = Field(
        default_factory=StageProgress,
        description="Preprocessing progress (total = chunk count)",
    )
    translating: StageProgress = Field(
        default_factory=StageProgress,
        description="Translation progress (total = XHTML count)",
    )
    inserting: StageProgress = Field(
        default_factory=StageProgress,
        description="Insertion progress (total = XHTML count)",
    )

    # Metadata
    error_message: str | None = Field(
        default=None, description="Error message if failed"
    )
    started_at: datetime = Field(
        default_factory=datetime.now, description="Job start time"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now, description="Last update time"
    )

    @computed_field
    @property
    def overall_progress(self) -> float:
        """
        Overall progress as a value from 0.0 to 1.0.

        Calculated using stage weights:
        - Extraction:    0–5%
        - Preprocessing: 5–30%
        - Translation:   30–95%
        - Insertion:     95–100%
        """
        if self.stage in (JobStage.PENDING, JobStage.FAILED):
            return 0.0
        if self.stage == JobStage.COMPLETED:
            return 1.0

        base, weight = STAGE_WEIGHTS.get(self.stage, (0.0, 0.0))
        stage_progress = self._current_stage_progress()
        return base + (stage_progress * weight)

    @computed_field
    @property
    def overall_percentage(self) -> float:
        """Overall progress as percentage (0.0 to 100.0)."""
        return self.overall_progress * 100

    def _current_stage_progress(self) -> float:
        """Get progress ratio (0.0 to 1.0) for current stage."""
        if self.stage in (JobStage.PENDING, JobStage.COMPLETED, JobStage.FAILED):
            return 0.0
        progress: StageProgress = getattr(self, self.stage.value)
        if progress.total > 0:
            return progress.completed / progress.total
        return 0.0

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return self.model_dump_json(indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "JobStatus":
        """Deserialize from JSON string."""
        return cls.model_validate_json(json_str)

    def update_stage(
        self,
        stage: JobStage,
        total: int | None = None,
        completed: int | None = None,
    ) -> "JobStatus":
        """
        Update stage and optionally set progress.

        Returns a new JobStatus instance with updated values.

        Args:
            stage: New stage to set.
            total: Total items for the stage (optional).
            completed: Completed items for the stage (optional).

        Returns:
            Updated JobStatus instance.
        """
        updates: dict = {"stage": stage, "updated_at": datetime.now()}

        # Use stage.value directly as field name
        if stage not in (JobStage.PENDING, JobStage.COMPLETED, JobStage.FAILED):
            field_name = stage.value
            current_progress: StageProgress = getattr(self, field_name)
            new_progress = StageProgress(
                total=total if total is not None else current_progress.total,
                completed=completed if completed is not None else current_progress.completed,
            )
            updates[field_name] = new_progress

        return self.model_copy(update=updates)

    def increment_progress(self, stage: JobStage, count: int = 1) -> "JobStatus":
        """
        Increment completed count for a stage.

        Args:
            stage: Stage to update.
            count: Amount to increment (default 1).

        Returns:
            Updated JobStatus instance.
        """
        if stage in (JobStage.PENDING, JobStage.COMPLETED, JobStage.FAILED):
            return self

        field_name = stage.value
        current_progress: StageProgress = getattr(self, field_name)
        new_progress = StageProgress(
            total=current_progress.total,
            completed=current_progress.completed + count,
        )

        return self.model_copy(
            update={field_name: new_progress, "updated_at": datetime.now()}
        )

    def mark_failed(self, error_message: str) -> "JobStatus":
        """
        Mark job as failed with error message.

        Args:
            error_message: Description of the failure.

        Returns:
            Updated JobStatus instance.
        """
        return self.model_copy(
            update={
                "stage": JobStage.FAILED,
                "error_message": error_message,
                "updated_at": datetime.now(),
            }
        )

    def mark_completed(self) -> "JobStatus":
        """
        Mark job as completed.

        Returns:
            Updated JobStatus instance.
        """
        return self.model_copy(
            update={"stage": JobStage.COMPLETED, "updated_at": datetime.now()}
        )
