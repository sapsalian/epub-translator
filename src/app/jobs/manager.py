"""Job queue manager with JSON file persistence."""

import asyncio
import json
import uuid
from pathlib import Path

from .models import JobInfo, JobState


class JobManager:
    def __init__(self, jobs_path: Path) -> None:
        self._jobs_path = jobs_path
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._jobs: dict[str, JobInfo] = {}
        self._tokens: dict[str, Path] = {}
        self._load()

    def _load(self) -> None:
        if self._jobs_path.exists():
            try:
                data = json.loads(self._jobs_path.read_text())
                for item in data:
                    job = JobInfo.from_dict(item)
                    self._jobs[job.job_id] = job
                    if job.download_token and job.output_path:
                        self._tokens[job.download_token] = Path(job.output_path)
            except (json.JSONDecodeError, KeyError):
                pass

    def _save(self) -> None:
        self._jobs_path.parent.mkdir(parents=True, exist_ok=True)
        data = [job.to_dict() for job in self._jobs.values()]
        self._jobs_path.write_text(json.dumps(data, indent=2))

    async def add_job(self, job: JobInfo) -> None:
        self._jobs[job.job_id] = job
        self._save()
        await self._queue.put(job.job_id)

    def get_job(self, job_id: str) -> JobInfo | None:
        return self._jobs.get(job_id)

    def list_jobs(self) -> list[JobInfo]:
        return list(self._jobs.values())

    def delete_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save()
            return True
        return False

    def get_queue_position(self, job_id: str) -> int:
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
        token = uuid.uuid4().hex
        self._tokens[token] = file_path
        return token

    def resolve_download(self, token: str) -> Path | None:
        return self._tokens.get(token)

    def save(self) -> None:
        self._save()

    @property
    def queue(self) -> asyncio.Queue[str]:
        return self._queue
