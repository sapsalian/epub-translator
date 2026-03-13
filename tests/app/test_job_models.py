"""Tests for JobInfo and JobState models."""

from src.app.jobs.models import JobInfo, JobState


class TestJobState:
    def test_enum_values(self):
        assert JobState.QUEUED.value == "queued"
        assert JobState.PROCESSING.value == "processing"
        assert JobState.AWAITING_REVIEW.value == "awaiting_review"
        assert JobState.DONE.value == "done"
        assert JobState.FAILED.value == "failed"


class TestJobInfo:
    def _make_job(self, **overrides):
        defaults = dict(
            job_id="j1",
            filename="book.epub",
            upload_id="u1",
            source_language="en",
            target_language="ko",
        )
        defaults.update(overrides)
        return JobInfo(**defaults)

    def test_to_dict_from_dict_roundtrip(self):
        job = self._make_job(custom_instructions="formal tone")
        data = job.to_dict()
        restored = JobInfo.from_dict(data)

        assert restored.job_id == job.job_id
        assert restored.filename == job.filename
        assert restored.upload_id == job.upload_id
        assert restored.source_language == job.source_language
        assert restored.target_language == job.target_language
        assert restored.custom_instructions == job.custom_instructions
        assert restored.workflow_mode == job.workflow_mode
        assert restored.workflow_options == job.workflow_options
        assert restored.state == job.state
        assert restored.created_at == job.created_at

    def test_to_dict_state_is_string(self):
        job = self._make_job(state=JobState.PROCESSING)
        assert job.to_dict()["state"] == "processing"

    def test_from_dict_with_defaults(self):
        minimal = {"job_id": "j1", "filename": "b.epub", "upload_id": "u1"}
        job = JobInfo.from_dict(minimal)
        assert job.state == JobState.QUEUED
        assert job.workflow_mode == "classic"
        assert job.workflow_options == {}
        assert job.progress == 0.0
        assert job.error == ""
        assert job.download_token is None
        assert job.source_epub_path is None

    def test_to_dict_includes_workflow_fields(self):
        job = self._make_job(
            workflow_mode="glossary_review",
            workflow_options={"review_required": True},
        )
        data = job.to_dict()
        assert data["workflow_mode"] == "glossary_review"
        assert data["workflow_options"] == {"review_required": True}

    def test_to_dict_from_dict_roundtrip_with_source_epub_path(self):
        job = self._make_job(source_epub_path="/tmp/source_epubs/j1.epub")
        restored = JobInfo.from_dict(job.to_dict())
        assert restored.source_epub_path == "/tmp/source_epubs/j1.epub"
