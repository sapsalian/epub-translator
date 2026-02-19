"""Web server entrypoint for the EPUB Translator (server branch)."""

import asyncio
import shutil
import logging
from datetime import datetime, timedelta

from nicegui import app, ui

from . import server_config
from .jobs.manager import job_manager
from .jobs.worker import run_worker
from .views.login_view import build_login_page
from .views.main_view import MainView

from .routes import register_routes

logger = logging.getLogger(__name__)

register_routes()  # Register FastAPI routes at import time


async def _cleanup_old_output_files():
    """Delete output directories older than OUTPUT_RETENTION_HOURS."""
    while True:
        await asyncio.sleep(3600)  # run once per hour
        cutoff = datetime.now() - timedelta(hours=server_config.OUTPUT_RETENTION_HOURS)
        output_dir = server_config.OUTPUT_DIR
        if not output_dir.exists():
            continue
        for job_dir in output_dir.iterdir():
            if not job_dir.is_dir():
                continue
            try:
                mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
                if mtime < cutoff:
                    shutil.rmtree(job_dir, ignore_errors=True)
                    logger.info("Cleaned up old output dir: %s", job_dir)
            except OSError:
                pass


async def _on_startup():
    # Ensure required directories exist
    for directory in (
        server_config.OUTPUT_DIR,
        server_config.UPLOAD_DIR,
        server_config.CHECKPOINT_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    # Start background worker and cleanup task
    asyncio.create_task(run_worker(job_manager))
    asyncio.create_task(_cleanup_old_output_files())
    logger.info("Server started (BASE_URL=%s)", server_config.BASE_URL)


@ui.page("/login")
def login_page():
    build_login_page()


@ui.page("/")
def main_page():
    view = MainView()
    view.build()


def run(port: int = 8080):
    app.on_startup(_on_startup)
    ui.run(
        port=port,
        title="EPUB Translator",
        storage_secret=server_config.SECRET_KEY,
        reload=False,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="EPUB Translator — web server mode")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    run(port=args.port)
