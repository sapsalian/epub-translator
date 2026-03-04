"""Job queue manager — single background worker, multiple clients."""

import asyncio
import uuid
from pathlib import Path

from .models import JobInfo, JobState


class JobManager:
    """Manages the translation job queue and download token registry.

    Designed as an app-level singleton.  Thread safety is provided by
    asyncio's single-threaded event loop — all public methods are
    called from async context only.
    """

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._jobs: dict[str, JobInfo] = {}
        self._tokens: dict[str, Path] = {}  # download_token → file_path

    async def submit(self, job: JobInfo) -> None:
        """Add a job to the queue."""
        self._jobs[job.job_id] = job
        await self._queue.put(job.job_id)

    def get_status(self, job_id: str) -> JobInfo | None:
        return self._jobs.get(job_id)

    def get_queue_position(self, job_id: str) -> int:
        """Return 1-based queue position, or 0 if running/done/not found.

        Position is estimated from the order jobs were submitted and
        how many are still QUEUED ahead of this one.
        """
        job = self._jobs.get(job_id)
        if job is None or job.state != JobState.QUEUED:
            return 0

        queued_ids = [
            jid for jid, j in self._jobs.items() if j.state == JobState.QUEUED
        ]
        try:
            return queued_ids.index(job_id) + 1
        except ValueError:
            return 0

    def register_download(self, file_path: Path) -> str:
        """Associate a unique token with the output file and return it."""
        token = uuid.uuid4().hex
        self._tokens[token] = file_path
        return token

    def resolve_download(self, token: str) -> Path | None:
        """Return the file path for a given token, or None if invalid."""
        return self._tokens.get(token)

    def remove_download_token(self, token: str) -> None:
        self._tokens.pop(token, None)

    @property
    def queue(self) -> asyncio.Queue[str]:
        return self._queue

    @property
    def jobs(self) -> dict[str, JobInfo]:
        return self._jobs


# App-level singleton — safe because all access happens in asyncio event loop
job_manager = JobManager()
