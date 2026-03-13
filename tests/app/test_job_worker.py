"""Tests for job worker behavior."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.app.jobs.manager import JobManager
from src.app.jobs.models import JobInfo, JobState
from src.app.jobs.worker import run_worker
from src.pipeline.models import Language
from src.pipeline.persistence import CheckpointManager, FilePersistenceBackend


@dataclass
class _Settings:
    openai_api_key: str = ""
    model: str = "gpt-4.1-mini"


class _DummyResult:
    def __init__(self, output_path: str) -> None:
        self.output_path = output_path


class _DummyOrchestrator:
    last_glossary_overrides = None

    def __init__(self, config) -> None:
        self._config = config

    async def initialize(self) -> None:
        return None

    def _generate_epub_id(self, epub_path: Path) -> str:
        return f"epub-{epub_path.name}"

    async def get_job_status(self, epub_path: Path):
        return None

    async def run(
        self,
        epub_path: Path,
        *,
        stop_after_preprocess: bool = False,
        glossary_overrides=None,
    ):
        _DummyOrchestrator.last_glossary_overrides = glossary_overrides
        if stop_after_preprocess:
            return None
        return _DummyResult(str(self._config.output_dir / "translated.epub"))


def _make_job(**overrides) -> JobInfo:
    defaults = dict(
        job_id="j1",
        filename="book.epub",
        upload_id="u1",
        source_language="en",
        target_language="ko",
    )
    defaults.update(overrides)
    return JobInfo(**defaults)


@pytest.mark.asyncio
async def test_worker_copies_upload_to_workspace(monkeypatch, tmp_path: Path):
    from src.app.jobs import worker as worker_module

    monkeypatch.setattr(worker_module, "PipelineOrchestrator", _DummyOrchestrator)

    jobs_path = tmp_path / "jobs.json"
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    checkpoint_dir = tmp_path / "checkpoints"
    workspace_dir = tmp_path / "workspaces"
    source_epub_dir = tmp_path / "source_epubs"

    upload_epub_dir = upload_dir / "u1"
    upload_epub_dir.mkdir(parents=True, exist_ok=True)
    (upload_epub_dir / "book.epub").write_bytes(b"PK\x03\x04dummy")

    manager = JobManager(jobs_path)
    await manager.add_job(_make_job())

    task = asyncio.create_task(
        run_worker(
            manager=manager,
            settings_getter=lambda: _Settings(),
            output_dir=output_dir,
            checkpoint_dir=checkpoint_dir,
            upload_dir=upload_dir,
            workspace_dir=workspace_dir,
            source_epub_dir=source_epub_dir,
        )
    )

    await asyncio.wait_for(manager.queue.join(), timeout=5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    job = manager.get_job("j1")
    assert job is not None
    assert job.state == JobState.DONE
    assert job.input_path is not None
    assert Path(job.input_path).exists()
    assert Path(job.input_path).parent == workspace_dir / "j1"
    assert job.source_epub_path == str(source_epub_dir / "j1.epub")
    assert Path(job.source_epub_path).exists()


@pytest.mark.asyncio
async def test_worker_uses_existing_workspace_when_upload_missing(monkeypatch, tmp_path: Path):
    from src.app.jobs import worker as worker_module

    monkeypatch.setattr(worker_module, "PipelineOrchestrator", _DummyOrchestrator)

    jobs_path = tmp_path / "jobs.json"
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    checkpoint_dir = tmp_path / "checkpoints"
    workspace_dir = tmp_path / "workspaces"
    source_epub_dir = tmp_path / "source_epubs"

    workspace_epub = workspace_dir / "j1" / "book.epub"
    workspace_epub.parent.mkdir(parents=True, exist_ok=True)
    workspace_epub.write_bytes(b"PK\x03\x04dummy")

    manager = JobManager(jobs_path)
    await manager.add_job(_make_job(input_path=str(workspace_epub)))

    task = asyncio.create_task(
        run_worker(
            manager=manager,
            settings_getter=lambda: _Settings(),
            output_dir=output_dir,
            checkpoint_dir=checkpoint_dir,
            upload_dir=upload_dir,
            workspace_dir=workspace_dir,
            source_epub_dir=source_epub_dir,
        )
    )

    await asyncio.wait_for(manager.queue.join(), timeout=5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    job = manager.get_job("j1")
    assert job is not None
    assert job.state == JobState.DONE
    assert job.input_path == str(workspace_epub)
    assert job.source_epub_path == str(source_epub_dir / "j1.epub")
    assert Path(job.source_epub_path).exists()


@pytest.mark.asyncio
async def test_worker_pauses_glossary_review_mode(monkeypatch, tmp_path: Path):
    from src.app.jobs import worker as worker_module

    monkeypatch.setattr(worker_module, "PipelineOrchestrator", _DummyOrchestrator)

    jobs_path = tmp_path / "jobs.json"
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    checkpoint_dir = tmp_path / "checkpoints"
    workspace_dir = tmp_path / "workspaces"
    source_epub_dir = tmp_path / "source_epubs"

    upload_epub_dir = upload_dir / "u1"
    upload_epub_dir.mkdir(parents=True, exist_ok=True)
    (upload_epub_dir / "book.epub").write_bytes(b"PK\x03\x04dummy")

    manager = JobManager(jobs_path)
    await manager.add_job(_make_job(workflow_mode="glossary_review"))

    task = asyncio.create_task(
        run_worker(
            manager=manager,
            settings_getter=lambda: _Settings(),
            output_dir=output_dir,
            checkpoint_dir=checkpoint_dir,
            upload_dir=upload_dir,
            workspace_dir=workspace_dir,
            source_epub_dir=source_epub_dir,
        )
    )

    await asyncio.wait_for(manager.queue.join(), timeout=5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    job = manager.get_job("j1")
    assert job is not None
    assert job.state == JobState.AWAITING_REVIEW
    assert job.stage == "awaiting_review"


@pytest.mark.asyncio
async def test_worker_uses_edited_glossary_after_approval(monkeypatch, tmp_path: Path):
    from src.app.jobs import worker as worker_module

    monkeypatch.setattr(worker_module, "PipelineOrchestrator", _DummyOrchestrator)
    _DummyOrchestrator.last_glossary_overrides = None

    jobs_path = tmp_path / "jobs.json"
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "output"
    checkpoint_dir = tmp_path / "checkpoints"
    workspace_dir = tmp_path / "workspaces"
    source_epub_dir = tmp_path / "source_epubs"

    upload_epub_dir = upload_dir / "u1"
    upload_epub_dir.mkdir(parents=True, exist_ok=True)
    (upload_epub_dir / "book.epub").write_bytes(b"PK\x03\x04dummy")

    checkpoint_backend = FilePersistenceBackend(str(checkpoint_dir / "j1"))
    await checkpoint_backend.initialize()
    checkpoint_manager = CheckpointManager(checkpoint_backend)
    expected_mappings = {"Milo": "밀로"}
    await checkpoint_manager.save_glossary_edit("epub-book.epub", Language.KOREAN, expected_mappings)

    manager = JobManager(jobs_path)
    await manager.add_job(
        _make_job(
            workflow_mode="glossary_review",
            workflow_options={"review_approved": True},
        )
    )

    task = asyncio.create_task(
        run_worker(
            manager=manager,
            settings_getter=lambda: _Settings(),
            output_dir=output_dir,
            checkpoint_dir=checkpoint_dir,
            upload_dir=upload_dir,
            workspace_dir=workspace_dir,
            source_epub_dir=source_epub_dir,
        )
    )

    await asyncio.wait_for(manager.queue.join(), timeout=5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    job = manager.get_job("j1")
    assert job is not None
    assert job.state == JobState.DONE
    assert _DummyOrchestrator.last_glossary_overrides == expected_mappings
    assert job.source_epub_path == str(source_epub_dir / "j1.epub")
    assert Path(job.source_epub_path).exists()
