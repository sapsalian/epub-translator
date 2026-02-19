"""Tests for the background translation worker."""

import asyncio
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.gui.jobs.manager import JobManager
from src.gui.jobs.models import JobInfo, JobState
from src.pipeline.models import Language


def make_job(tmp_path: Path) -> JobInfo:
    epub = tmp_path / "book.epub"
    epub.write_bytes(b"fake epub")
    return JobInfo(
        job_id=uuid.uuid4().hex,
        epub_filename="book.epub",
        epub_path_str=str(epub),
        email="user@example.com",
        source_language=Language.ENGLISH,
        target_language=Language.KOREAN,
        custom_instructions="",
    )


@pytest.mark.asyncio
class TestRunWorker:
    async def _run_one_job(self, manager: JobManager, job: JobInfo) -> None:
        """Submit one job and run worker until queue is drained."""
        from src.gui.jobs.worker import run_worker

        await manager.submit(job)
        worker_task = asyncio.create_task(run_worker(manager))
        await manager.queue.join()  # wait until job is processed
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    async def test_successful_job_sets_state_done(self, tmp_path):
        manager = JobManager()
        job = make_job(tmp_path)

        mock_result = MagicMock()
        mock_result.output_path = str(tmp_path / "book_ko.epub")

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator.get_job_status.return_value = None

        with (
            patch("src.gui.jobs.worker.PipelineOrchestrator", return_value=mock_orchestrator),
            patch("src.gui.jobs.worker.PipelineConfig"),
            patch("src.gui.jobs.worker.send_completion_email", new_callable=AsyncMock),
            patch("src.gui.jobs.worker.send_failure_email", new_callable=AsyncMock),
        ):
            await self._run_one_job(manager, job)

        assert job.state == JobState.DONE
        assert job.progress == 1.0
        assert job.download_token is not None

    async def test_successful_job_sends_completion_email(self, tmp_path):
        manager = JobManager()
        job = make_job(tmp_path)

        mock_result = MagicMock()
        mock_result.output_path = str(tmp_path / "book_ko.epub")
        mock_orchestrator = AsyncMock()
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator.get_job_status.return_value = None

        with (
            patch("src.gui.jobs.worker.PipelineOrchestrator", return_value=mock_orchestrator),
            patch("src.gui.jobs.worker.PipelineConfig"),
            patch("src.gui.jobs.worker.send_completion_email", new_callable=AsyncMock) as mock_email,
            patch("src.gui.jobs.worker.send_failure_email", new_callable=AsyncMock),
        ):
            await self._run_one_job(manager, job)

        mock_email.assert_called_once()
        call_kwargs = mock_email.call_args
        assert call_kwargs[0][0] == "user@example.com"
        assert call_kwargs[0][1] == "book.epub"

    async def test_failed_job_sets_state_failed(self, tmp_path):
        manager = JobManager()
        job = make_job(tmp_path)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run.side_effect = RuntimeError("API error")
        mock_orchestrator.get_job_status.return_value = None

        with (
            patch("src.gui.jobs.worker.PipelineOrchestrator", return_value=mock_orchestrator),
            patch("src.gui.jobs.worker.PipelineConfig"),
            patch("src.gui.jobs.worker.send_completion_email", new_callable=AsyncMock),
            patch("src.gui.jobs.worker.send_failure_email", new_callable=AsyncMock),
        ):
            await self._run_one_job(manager, job)

        assert job.state == JobState.FAILED
        assert "API error" in job.error

    async def test_failed_job_sends_failure_email(self, tmp_path):
        manager = JobManager()
        job = make_job(tmp_path)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run.side_effect = RuntimeError("connection lost")
        mock_orchestrator.get_job_status.return_value = None

        with (
            patch("src.gui.jobs.worker.PipelineOrchestrator", return_value=mock_orchestrator),
            patch("src.gui.jobs.worker.PipelineConfig"),
            patch("src.gui.jobs.worker.send_completion_email", new_callable=AsyncMock),
            patch("src.gui.jobs.worker.send_failure_email", new_callable=AsyncMock) as mock_fail,
        ):
            await self._run_one_job(manager, job)

        mock_fail.assert_called_once()
        assert mock_fail.call_args[0][0] == "user@example.com"

    async def test_uploaded_epub_deleted_on_success(self, tmp_path):
        manager = JobManager()
        job = make_job(tmp_path)
        epub_path = Path(job.epub_path_str)
        assert epub_path.exists()

        mock_result = MagicMock()
        mock_result.output_path = str(tmp_path / "book_ko.epub")
        mock_orchestrator = AsyncMock()
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator.get_job_status.return_value = None

        with (
            patch("src.gui.jobs.worker.PipelineOrchestrator", return_value=mock_orchestrator),
            patch("src.gui.jobs.worker.PipelineConfig"),
            patch("src.gui.jobs.worker.send_completion_email", new_callable=AsyncMock),
            patch("src.gui.jobs.worker.send_failure_email", new_callable=AsyncMock),
        ):
            await self._run_one_job(manager, job)

        assert not epub_path.exists()

    async def test_uploaded_epub_deleted_on_failure(self, tmp_path):
        manager = JobManager()
        job = make_job(tmp_path)
        epub_path = Path(job.epub_path_str)

        mock_orchestrator = AsyncMock()
        mock_orchestrator.run.side_effect = RuntimeError("fail")
        mock_orchestrator.get_job_status.return_value = None

        with (
            patch("src.gui.jobs.worker.PipelineOrchestrator", return_value=mock_orchestrator),
            patch("src.gui.jobs.worker.PipelineConfig"),
            patch("src.gui.jobs.worker.send_completion_email", new_callable=AsyncMock),
            patch("src.gui.jobs.worker.send_failure_email", new_callable=AsyncMock),
        ):
            await self._run_one_job(manager, job)

        assert not epub_path.exists()

    async def test_download_token_registered_in_manager(self, tmp_path):
        manager = JobManager()
        job = make_job(tmp_path)

        mock_result = MagicMock()
        mock_result.output_path = str(tmp_path / "book_ko.epub")
        mock_orchestrator = AsyncMock()
        mock_orchestrator.run.return_value = mock_result
        mock_orchestrator.get_job_status.return_value = None

        with (
            patch("src.gui.jobs.worker.PipelineOrchestrator", return_value=mock_orchestrator),
            patch("src.gui.jobs.worker.PipelineConfig"),
            patch("src.gui.jobs.worker.send_completion_email", new_callable=AsyncMock),
            patch("src.gui.jobs.worker.send_failure_email", new_callable=AsyncMock),
        ):
            await self._run_one_job(manager, job)

        token = job.download_token
        assert token is not None
        resolved = manager.resolve_download(token)
        assert resolved == Path(mock_result.output_path)
