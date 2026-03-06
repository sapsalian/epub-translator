"""Background worker that processes translation jobs sequentially."""

import asyncio
import logging
import os
import shutil
from pathlib import Path

from src.pipeline import PipelineConfig, PipelineOrchestrator
from src.pipeline.models import Language

from .manager import JobManager
from .models import JobState

logger = logging.getLogger(__name__)


async def _poll_progress(
    orchestrator: PipelineOrchestrator,
    epub_path: Path,
    job_id: str,
    manager: JobManager,
) -> None:
    while True:
        await asyncio.sleep(1.0)
        job = manager.get_job(job_id)
        if job is None or job.state in (JobState.DONE, JobState.FAILED):
            break
        try:
            status = await orchestrator.get_job_status(epub_path)
            if status:
                job.progress = status.overall_progress
                job.stage = status.stage.value if status.stage else ""
                manager.save()
        except Exception:
            pass


async def run_worker(
    manager: JobManager,
    settings_getter,
    output_dir: Path,
    checkpoint_dir: Path,
    upload_dir: Path,
) -> None:
    logger.info("Translation worker started")

    while True:
        job_id = await manager.queue.get()
        job = manager.get_job(job_id)

        if job is None:
            manager.queue.task_done()
            continue

        logger.info("Starting job %s (%s)", job_id, job.filename)
        job.state = JobState.PROCESSING
        job.progress = 0.0
        manager.save()

        settings = settings_getter()
        if settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = settings.openai_api_key

        epub_path = upload_dir / job.upload_id / job.filename
        job_output_dir = output_dir / job_id
        job_checkpoint_dir = checkpoint_dir / job_id

        poll_task: asyncio.Task | None = None

        try:
            config = PipelineConfig.from_env(
                source_language=Language(job.source_language),
                target_language=Language(job.target_language),
                custom_instructions=job.custom_instructions,
                output_dir=job_output_dir,
                checkpoint_dir=job_checkpoint_dir,
                model=settings.model,
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
            job.output_path = result.output_path
            job.download_token = manager.register_download(Path(result.output_path))
            manager.save()

            logger.info("Job %s completed: %s", job_id, result.output_path)
            shutil.rmtree(job_checkpoint_dir, ignore_errors=True)

        except Exception as exc:
            job.state = JobState.FAILED
            job.error = str(exc)
            manager.save()
            logger.error("Job %s failed: %s", job_id, exc)

        finally:
            if poll_task and not poll_task.done():
                poll_task.cancel()
                try:
                    await poll_task
                except asyncio.CancelledError:
                    pass

            upload_epub_dir = upload_dir / job.upload_id
            shutil.rmtree(upload_epub_dir, ignore_errors=True)
            manager.queue.task_done()
            logger.info("Job %s finished (state=%s)", job_id, job.state.value)
