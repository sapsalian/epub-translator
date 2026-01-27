"""Tests for persistence models."""

import pytest
from datetime import datetime

from src.pipeline.persistence.models import (
    JobStage,
    JobStatus,
    StageProgress,
    STAGE_WEIGHTS,
)


class TestStageProgress:
    """Tests for StageProgress model."""

    def test_percentage_with_zero_total(self):
        """Percentage is 0 when total is 0."""
        progress = StageProgress(total=0, completed=0)
        assert progress.percentage == 0.0

    def test_percentage_calculation(self):
        """Percentage calculated correctly."""
        progress = StageProgress(total=10, completed=5)
        assert progress.percentage == 50.0

    def test_percentage_full(self):
        """Percentage is 100 when complete."""
        progress = StageProgress(total=10, completed=10)
        assert progress.percentage == 100.0

    def test_is_complete_false(self):
        """is_complete is False when not done."""
        progress = StageProgress(total=10, completed=5)
        assert progress.is_complete is False

    def test_is_complete_true(self):
        """is_complete is True when done."""
        progress = StageProgress(total=10, completed=10)
        assert progress.is_complete is True

    def test_is_complete_over_complete(self):
        """is_complete is True even if over-completed."""
        progress = StageProgress(total=10, completed=15)
        assert progress.is_complete is True


class TestJobStatus:
    """Tests for JobStatus model."""

    def test_default_values(self):
        """Default values are set correctly."""
        status = JobStatus(epub_id="test", target_language="ko")
        assert status.stage == JobStage.PENDING
        assert status.extracting.total == 0
        assert status.error_message is None

    def test_overall_progress_pending(self):
        """Overall progress is 0 when pending."""
        status = JobStatus(epub_id="test", target_language="ko")
        assert status.overall_progress == 0.0

    def test_overall_progress_extracting(self):
        """Overall progress during extraction."""
        status = JobStatus(
            epub_id="test",
            target_language="ko",
            stage=JobStage.EXTRACTING,
            extracting=StageProgress(total=10, completed=5),
        )
        # base=0, weight=0.10, progress=0.5
        expected = 0.0 + (0.5 * 0.10)
        assert status.overall_progress == pytest.approx(expected)

    def test_overall_progress_translating(self):
        """Overall progress during translation."""
        status = JobStatus(
            epub_id="test",
            target_language="ko",
            stage=JobStage.TRANSLATING,
            translating=StageProgress(total=10, completed=5),
        )
        # base=0.25, weight=0.70, progress=0.5
        expected = 0.25 + (0.5 * 0.70)
        assert status.overall_progress == pytest.approx(expected)

    def test_overall_progress_completed(self):
        """Overall progress is 1.0 when completed."""
        status = JobStatus(
            epub_id="test",
            target_language="ko",
            stage=JobStage.COMPLETED,
        )
        assert status.overall_progress == 1.0

    def test_overall_progress_failed(self):
        """Overall progress is 0 when failed."""
        status = JobStatus(
            epub_id="test",
            target_language="ko",
            stage=JobStage.FAILED,
        )
        assert status.overall_progress == 0.0

    def test_overall_percentage(self):
        """Overall percentage is progress * 100."""
        status = JobStatus(
            epub_id="test",
            target_language="ko",
            stage=JobStage.TRANSLATING,
            translating=StageProgress(total=10, completed=5),
        )
        assert status.overall_percentage == pytest.approx(status.overall_progress * 100)

    def test_update_stage(self):
        """update_stage returns new instance with updated values."""
        status = JobStatus(epub_id="test", target_language="ko")
        updated = status.update_stage(JobStage.EXTRACTING, total=10, completed=0)

        # Original unchanged
        assert status.stage == JobStage.PENDING

        # Updated has new values
        assert updated.stage == JobStage.EXTRACTING
        assert updated.extracting.total == 10
        assert updated.extracting.completed == 0

    def test_increment_progress(self):
        """increment_progress increases completed count."""
        status = JobStatus(
            epub_id="test",
            target_language="ko",
            stage=JobStage.TRANSLATING,
            translating=StageProgress(total=10, completed=3),
        )
        updated = status.increment_progress(JobStage.TRANSLATING, count=2)

        assert updated.translating.completed == 5
        assert status.translating.completed == 3  # Original unchanged

    def test_mark_failed(self):
        """mark_failed sets stage and error message."""
        status = JobStatus(epub_id="test", target_language="ko")
        updated = status.mark_failed("Something went wrong")

        assert updated.stage == JobStage.FAILED
        assert updated.error_message == "Something went wrong"

    def test_mark_completed(self):
        """mark_completed sets stage to COMPLETED."""
        status = JobStatus(epub_id="test", target_language="ko")
        updated = status.mark_completed()

        assert updated.stage == JobStage.COMPLETED

    def test_json_round_trip(self):
        """Serialization and deserialization work correctly."""
        status = JobStatus(
            epub_id="test123",
            target_language="ko",
            stage=JobStage.TRANSLATING,
            translating=StageProgress(total=10, completed=5),
            error_message=None,
        )

        json_str = status.to_json()
        restored = JobStatus.from_json(json_str)

        assert restored.epub_id == status.epub_id
        assert restored.target_language == status.target_language
        assert restored.stage == status.stage
        assert restored.translating.total == status.translating.total
        assert restored.translating.completed == status.translating.completed


class TestStageWeights:
    """Tests for stage weight configuration."""

    def test_weights_sum_to_one(self):
        """Stage weights sum to approximately 1.0."""
        total = sum(
            weight
            for stage, (base, weight) in STAGE_WEIGHTS.items()
            if stage not in (JobStage.PENDING, JobStage.COMPLETED, JobStage.FAILED)
        )
        assert total == pytest.approx(1.0)

    def test_weights_ordered(self):
        """Base values increase through stages."""
        stages = [
            JobStage.EXTRACTING,
            JobStage.PREPROCESSING,
            JobStage.TRANSLATING,
            JobStage.INSERTING,
        ]
        bases = [STAGE_WEIGHTS[s][0] for s in stages]
        assert bases == sorted(bases)
