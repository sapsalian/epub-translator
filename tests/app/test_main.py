from pathlib import Path

from src.app.config import AppConfig
from src.app.jobs.manager import JobManager
from src.app.jobs.models import JobInfo, JobState
from src.app.main import migrate_source_epubs


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


def test_migrate_source_epubs_copies_done_jobs_without_source_path(tmp_path: Path):
    config = AppConfig(base_dir=tmp_path)
    config.ensure_dirs()

    source_file = tmp_path / "input-book.epub"
    source_file.write_bytes(b"PK\x03\x04dummy")

    manager = JobManager(config.jobs_path)
    job = _make_job(
        state=JobState.DONE,
        input_path=str(source_file),
        output_path=str(tmp_path / "output.epub"),
        source_epub_path=None,
    )
    manager._jobs[job.job_id] = job  # noqa: SLF001
    manager.save()

    updated_count = migrate_source_epubs(config, manager)

    migrated = manager.get_job(job.job_id)
    assert updated_count == 1
    assert migrated is not None
    assert migrated.source_epub_path == str(config.source_epub_dir / "j1.epub")
    assert Path(migrated.source_epub_path).exists()


def test_migrate_source_epubs_skips_non_done_jobs(tmp_path: Path):
    config = AppConfig(base_dir=tmp_path)
    config.ensure_dirs()

    source_file = tmp_path / "input-book.epub"
    source_file.write_bytes(b"PK\x03\x04dummy")

    manager = JobManager(config.jobs_path)
    job = _make_job(
        state=JobState.PROCESSING,
        input_path=str(source_file),
        output_path=str(tmp_path / "output.epub"),
    )
    manager._jobs[job.job_id] = job  # noqa: SLF001
    manager.save()

    updated_count = migrate_source_epubs(config, manager)

    unchanged = manager.get_job(job.job_id)
    assert updated_count == 0
    assert unchanged is not None
    assert unchanged.source_epub_path is None
