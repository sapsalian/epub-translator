"""Tests for job models and manager."""

import asyncio
import uuid
from pathlib import Path

import pytest

from src.gui.jobs.models import JobInfo, JobState
from src.gui.jobs.manager import JobManager
from src.pipeline.models import Language


def make_job(job_id: str | None = None, state: JobState = JobState.QUEUED) -> JobInfo:
    job = JobInfo(
        job_id=job_id or uuid.uuid4().hex,
        epub_filename="book.epub",
        epub_path_str="/tmp/book.epub",
        email="user@example.com",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        custom_instructions="",
    )
    job.state = state
    return job


class TestJobModel:
    def test_default_state_is_queued(self):
        job = make_job()
        assert job.state == JobState.QUEUED

    def test_default_progress_is_zero(self):
        job = make_job()
        assert job.progress == 0.0

    def test_state_transition(self):
        job = make_job()
        job.state = JobState.RUNNING
        assert job.state == JobState.RUNNING

    def test_job_state_values(self):
        assert JobState.QUEUED == "queued"
        assert JobState.RUNNING == "running"
        assert JobState.DONE == "done"
        assert JobState.FAILED == "failed"


@pytest.mark.asyncio
class TestJobManager:
    async def test_submit_adds_job(self):
        mgr = JobManager()
        job = make_job("j1")
        await mgr.submit(job)
        assert mgr.get_status("j1") is job

    async def test_get_status_unknown_returns_none(self):
        mgr = JobManager()
        assert mgr.get_status("nonexistent") is None

    async def test_queue_position_single_job(self):
        mgr = JobManager()
        job = make_job("j1")
        await mgr.submit(job)
        assert mgr.get_queue_position("j1") == 1

    async def test_queue_position_multiple_jobs(self):
        mgr = JobManager()
        for i in range(3):
            await mgr.submit(make_job(f"j{i}"))
        assert mgr.get_queue_position("j0") == 1
        assert mgr.get_queue_position("j1") == 2
        assert mgr.get_queue_position("j2") == 3

    async def test_queue_position_running_job_returns_zero(self):
        mgr = JobManager()
        job = make_job("j1", state=JobState.RUNNING)
        await mgr.submit(job)
        assert mgr.get_queue_position("j1") == 0

    async def test_queue_position_done_job_returns_zero(self):
        mgr = JobManager()
        job = make_job("j1", state=JobState.DONE)
        await mgr.submit(job)
        assert mgr.get_queue_position("j1") == 0

    async def test_queue_position_unknown_returns_zero(self):
        mgr = JobManager()
        assert mgr.get_queue_position("unknown") == 0

    async def test_register_and_resolve_download(self):
        mgr = JobManager()
        path = Path("/tmp/output.epub")
        token = mgr.register_download(path)
        assert len(token) == 32  # uuid4 hex
        assert mgr.resolve_download(token) == path

    async def test_resolve_unknown_token_returns_none(self):
        mgr = JobManager()
        assert mgr.resolve_download("badtoken") is None

    async def test_remove_download_token(self):
        mgr = JobManager()
        token = mgr.register_download(Path("/tmp/out.epub"))
        mgr.remove_download_token(token)
        assert mgr.resolve_download(token) is None

    async def test_queue_is_fifo(self):
        mgr = JobManager()
        jobs = [make_job(f"j{i}") for i in range(3)]
        for job in jobs:
            await mgr.submit(job)
        for job in jobs:
            popped_id = await mgr.queue.get()
            assert popped_id == job.job_id
