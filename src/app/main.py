"""FastAPI application factory."""

import asyncio
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import AppConfig
from .jobs.manager import JobManager
from .jobs.models import JobState
from .jobs.worker import run_worker
from .routes import download, health, jobs, languages, settings, upload
from .settings.manager import SettingsManager


def migrate_source_epubs(config: AppConfig, job_manager: JobManager) -> int:
    updated_count = 0

    for job in job_manager.list_jobs():
        if job.state != JobState.DONE:
            continue
        if job.source_epub_path:
            continue
        if not job.input_path:
            continue

        input_path = Path(job.input_path)
        if not input_path.exists():
            continue

        source_dest = config.source_epub_dir / f"{job.job_id}.epub"
        if not source_dest.exists():
            source_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(input_path, source_dest)

        if source_dest.exists():
            job.source_epub_path = str(source_dest)
            updated_count += 1

    if updated_count > 0:
        job_manager.save()

    return updated_count


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: AppConfig = app.state.config
    migrate_source_epubs(config, app.state.job_manager)
    worker_task = asyncio.create_task(
        run_worker(
            manager=app.state.job_manager,
            settings_getter=lambda: app.state.settings_manager.settings,
            output_dir=config.output_dir,
            checkpoint_dir=config.checkpoint_dir,
            upload_dir=config.upload_dir,
            workspace_dir=config.workspace_dir,
            source_epub_dir=config.source_epub_dir,
        )
    )
    yield
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


def create_app(config: AppConfig | None = None) -> FastAPI:
    if config is None:
        config = AppConfig()
    config.ensure_dirs()

    app = FastAPI(title="EPUB Translator", lifespan=lifespan)

    allow_all_origins = os.environ.get("ALLOW_ALL_ORIGINS", "0") == "1"
    cors_origins = ["*"] if allow_all_origins else ["http://localhost:5173"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=not allow_all_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.config = config
    app.state.settings_manager = SettingsManager(config.settings_path)
    app.state.job_manager = JobManager(config.jobs_path)

    app.include_router(health.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(upload.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(download.router)
    app.include_router(languages.router, prefix="/api")

    dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="static")

    return app


app = create_app()
