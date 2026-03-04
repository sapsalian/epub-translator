"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import AppConfig
from .jobs.manager import JobManager
from .jobs.worker import run_worker
from .routes import download, health, jobs, languages, settings, upload
from .settings.manager import SettingsManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    config: AppConfig = app.state.config
    worker_task = asyncio.create_task(
        run_worker(
            manager=app.state.job_manager,
            settings_getter=lambda: app.state.settings_manager.settings,
            output_dir=config.output_dir,
            checkpoint_dir=config.checkpoint_dir,
            upload_dir=config.upload_dir,
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
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
