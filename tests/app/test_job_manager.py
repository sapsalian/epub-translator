"""Tests for JobManager."""

import pytest
from pathlib import Path

from src.app.jobs.manager import JobManager
from src.app.jobs.models import JobInfo, JobState


def _make_job(job_id="j1", **overrides):
    defaults = dict(
        job_id=job_id,
        filename="book.epub",
        upload_id="u1",
        source_language="en",
        target_language="ko",
    )
    defaults.update(overrides)
    return JobInfo(**defaults)


class TestJobManager:
    @pytest.mark.asyncio
    async def test_add_and_get_job(self, tmp_path):
        manager = JobManager(tmp_path / "jobs.json")
        job = _make_job()
        await manager.add_job(job)

        retrieved = manager.get_job("j1")
        assert retrieved is not None
        assert retrieved.job_id == "j1"
        assert retrieved.filename == "book.epub"

    @pytest.mark.asyncio
    async def test_list_jobs(self, tmp_path):
        manager = JobManager(tmp_path / "jobs.json")
        await manager.add_job(_make_job("j1"))
        await manager.add_job(_make_job("j2"))

        jobs = manager.list_jobs()
        assert len(jobs) == 2
        assert {j.job_id for j in jobs} == {"j1", "j2"}

    @pytest.mark.asyncio
    async def test_delete_job(self, tmp_path):
        manager = JobManager(tmp_path / "jobs.json")
        await manager.add_job(_make_job("j1"))

        assert manager.delete_job("j1") is True
        assert manager.get_job("j1") is None

    def test_delete_nonexistent_job(self, tmp_path):
        manager = JobManager(tmp_path / "jobs.json")
        assert manager.delete_job("nonexistent") is False

    @pytest.mark.asyncio
    async def test_queue_position(self, tmp_path):
        manager = JobManager(tmp_path / "jobs.json")
        await manager.add_job(_make_job("j1"))
        await manager.add_job(_make_job("j2"))
        await manager.add_job(_make_job("j3"))

        assert manager.get_queue_position("j1") == 1
        assert manager.get_queue_position("j2") == 2
        assert manager.get_queue_position("j3") == 3

    @pytest.mark.asyncio
    async def test_queue_position_non_queued(self, tmp_path):
        manager = JobManager(tmp_path / "jobs.json")
        job = _make_job("j1")
        await manager.add_job(job)
        job.state = JobState.PROCESSING

        assert manager.get_queue_position("j1") == 0

    def test_register_and_resolve_download(self, tmp_path):
        manager = JobManager(tmp_path / "jobs.json")
        file_path = tmp_path / "output.epub"
        token = manager.register_download(file_path)

        assert manager.resolve_download(token) == file_path
        assert manager.resolve_download("bad-token") is None

    @pytest.mark.asyncio
    async def test_persistence_across_instances(self, tmp_path):
        jobs_path = tmp_path / "jobs.json"

        manager1 = JobManager(jobs_path)
        await manager1.add_job(_make_job("j1"))

        manager2 = JobManager(jobs_path)
        restored = manager2.get_job("j1")
        assert restored is not None
        assert restored.job_id == "j1"
        assert restored.filename == "book.epub"

    def test_corrupted_json_starts_empty(self, tmp_path):
        jobs_path = tmp_path / "jobs.json"
        jobs_path.write_text("not valid json")

        manager = JobManager(jobs_path)
        assert manager.list_jobs() == []
