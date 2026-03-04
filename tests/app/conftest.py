"""Shared fixtures for src/app tests."""

import pytest
import pytest_asyncio
import httpx
from fastapi import FastAPI

from src.app.config import AppConfig
from src.app.jobs.manager import JobManager
from src.app.routes import download, health, jobs, languages, settings, upload
from src.app.settings.manager import SettingsManager


@pytest.fixture
def tmp_config(tmp_path):
    return AppConfig(base_dir=tmp_path)


@pytest.fixture
def test_app(tmp_config):
    """FastAPI app without lifespan (no background worker)."""
    tmp_config.ensure_dirs()

    app = FastAPI()
    app.state.config = tmp_config
    app.state.settings_manager = SettingsManager(tmp_config.settings_path)
    app.state.job_manager = JobManager(tmp_config.jobs_path)

    app.include_router(health.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(upload.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(download.router)
    app.include_router(languages.router, prefix="/api")

    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
