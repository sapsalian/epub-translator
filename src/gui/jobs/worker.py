"""Background worker that processes translation jobs one at a time."""

import asyncio
import logging
import shutil
from pathlib import Path

from src.pipeline import PipelineConfig, PipelineOrchestrator
from .. import server_config
from ..email.sender import send_completion_email, send_failure_email
from .manager import JobManager
from .models import JobState

logger = logging.getLogger(__name__)


async def _poll_progress(orchestrator: PipelineOrchestrator, epub_path: Path, job_id: str, manager: JobManager) -> None:
    """Periodically read job status from orchestrator and update JobInfo."""
    while True:
        await asyncio.sleep(1.0)
        job = manager.get_status(job_id)
        if job is None or job.state in (JobState.DONE, JobState.FAILED):
            break
        try:
            status = await orchestrator.get_job_status(epub_path)
            if status:
                job.progress = status.overall_progress
                job.stage = status.stage.value if status.stage else ""
        except Exception:
            pass  # Progress polling errors are non-fatal


async def run_worker(manager: JobManager) -> None:
    """Consume jobs from the queue indefinitely, one at a time."""
    logger.info("Translation worker started")

    while True:
        job_id = await manager.queue.get()
        job = manager.get_status(job_id)

        if job is None:
            manager.queue.task_done()
            continue

        logger.info("Starting job %s (%s)", job_id, job.epub_filename)
        job.state = JobState.RUNNING
        job.progress = 0.0

        epub_path = Path(job.epub_path_str)
        job_output_dir = server_config.OUTPUT_DIR / job_id
        job_checkpoint_dir = server_config.CHECKPOINT_DIR / job_id

        poll_task: asyncio.Task | None = None
        orchestrator: PipelineOrchestrator | None = None

        try:
            config = PipelineConfig(
                source_language=job.source_language,
                target_language=job.target_language,
                custom_instructions=job.custom_instructions,
                output_dir=job_output_dir,
                checkpoint_dir=job_checkpoint_dir,
            )
            orchestrator = PipelineOrchestrator(config)
            await orchestrator.initialize()

            poll_task = asyncio.create_task(
                _poll_progress(orchestrator, epub_path, job_id, manager)
            )

            result = await orchestrator.run(epub_path)

            job.state = JobState.DONE
            job.progress = 1.0
            job.stage = "done"

            token = manager.register_download(Path(result.output_path))
            job.download_token = token

            logger.info("Job %s completed: %s", job_id, result.output_path)
            await send_completion_email(job.email, job.epub_filename, token)

            shutil.rmtree(job_checkpoint_dir, ignore_errors=True)
            logger.info("Cleared checkpoint dir for job %s", job_id)

        except Exception as exc:
            job.state = JobState.FAILED
            job.error = str(exc)
            logger.error("Job %s failed: %s", job_id, exc)
            await send_failure_email(job.email, job.epub_filename, str(exc))

        finally:
            if poll_task and not poll_task.done():
                poll_task.cancel()
                try:
                    await poll_task
                except asyncio.CancelledError:
                    pass

            # Delete uploaded EPUB directory (uuid subdir + file) regardless of outcome
            shutil.rmtree(epub_path.parent, ignore_errors=True)

            manager.queue.task_done()
            logger.info("Job %s finished (state=%s)", job_id, job.state if job else "?")
