"""Background worker that processes translation jobs sequentially."""

import asyncio
import logging
import os
import shutil
from pathlib import Path

from src.pipeline import PipelineConfig, PipelineOrchestrator
from src.pipeline.models import Language
from src.pipeline.persistence import CheckpointManager, FilePersistenceBackend

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
        if job is None or job.state in (JobState.DONE, JobState.FAILED, JobState.AWAITING_REVIEW):
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
    workspace_dir: Path,
    source_epub_dir: Path,
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

        job_output_dir = output_dir / job_id
        job_checkpoint_dir = checkpoint_dir / job_id
        job_workspace_dir = workspace_dir / job_id
        workspace_epub_path = job_workspace_dir / job.filename

        poll_task: asyncio.Task | None = None

        try:
            job_workspace_dir.mkdir(parents=True, exist_ok=True)

            if not workspace_epub_path.exists():
                uploaded_epub_path = upload_dir / job.upload_id / job.filename
                if uploaded_epub_path.exists():
                    shutil.copy2(uploaded_epub_path, workspace_epub_path)
                elif job.input_path:
                    input_path = Path(job.input_path)
                    if input_path.exists():
                        shutil.copy2(input_path, workspace_epub_path)

            if not workspace_epub_path.exists():
                raise FileNotFoundError(f"Input EPUB not found for job {job_id}")

            job.input_path = str(workspace_epub_path)
            manager.save()

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
            job.epub_id = orchestrator._generate_epub_id(workspace_epub_path)  # noqa: SLF001
            manager.save()

            poll_task = asyncio.create_task(
                _poll_progress(orchestrator, workspace_epub_path, job_id, manager)
            )
            is_glossary_mode = job.workflow_mode == "glossary_review"
            review_approved = bool(job.workflow_options.get("review_approved"))

            if is_glossary_mode and not review_approved:
                await orchestrator.run(workspace_epub_path, stop_after_preprocess=True)
                job.state = JobState.AWAITING_REVIEW
                job.stage = "awaiting_review"
                manager.save()
                logger.info("Job %s paused for glossary review", job_id)
            else:
                glossary_overrides = None
                if is_glossary_mode and job.epub_id:
                    backend = FilePersistenceBackend(str(job_checkpoint_dir))
                    await backend.initialize()
                    checkpoint_manager = CheckpointManager(backend)
                    glossary_overrides = await checkpoint_manager.load_glossary_edit(
                        job.epub_id, job.target_language
                    )

                result = await orchestrator.run(
                    workspace_epub_path,
                    glossary_overrides=glossary_overrides,
                )
                if result is None:
                    raise RuntimeError("Pipeline returned no result for completion run")

                job.state = JobState.DONE
                job.progress = 1.0
                job.stage = "done"
                job.output_path = result.output_path
                job.download_token = manager.register_download(Path(result.output_path))
                job.workflow_options["review_approved"] = False

                source_dest = source_epub_dir / f"{job.job_id}.epub"
                if job.input_path and Path(job.input_path).exists() and not source_dest.exists():
                    source_dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(job.input_path, source_dest)
                if source_dest.exists():
                    job.source_epub_path = str(source_dest)

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
