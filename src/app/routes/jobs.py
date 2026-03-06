"""Job management endpoints."""

import asyncio
import json
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from ..jobs.models import JobInfo

router = APIRouter()


class JobCreateRequest(BaseModel):
    upload_id: str
    source_language: str
    target_language: str
    custom_instructions: str = ""


@router.post("/jobs")
async def create_job(request: Request, body: JobCreateRequest):
    manager = request.app.state.job_manager
    config = request.app.state.config

    epub_dir = config.upload_dir / body.upload_id
    if not epub_dir.exists():
        return JSONResponse({"error": "Upload not found"}, status_code=404)

    epub_files = list(epub_dir.glob("*.epub"))
    if not epub_files:
        return JSONResponse({"error": "No EPUB file in upload"}, status_code=404)

    job_id = uuid.uuid4().hex
    job = JobInfo(
        job_id=job_id,
        filename=epub_files[0].name,
        upload_id=body.upload_id,
        source_language=body.source_language,
        target_language=body.target_language,
        custom_instructions=body.custom_instructions,
    )
    await manager.add_job(job)
    return {"job_id": job_id}


@router.get("/jobs")
async def list_jobs(request: Request):
    manager = request.app.state.job_manager
    jobs = manager.list_jobs()
    return [job.to_dict() for job in jobs]


@router.get("/jobs/stream")
async def stream_jobs(request: Request):
    manager = request.app.state.job_manager

    async def event_generator():
        jobs = [j.to_dict() for j in manager.list_jobs()]
        yield f"data: {json.dumps(jobs)}\n\n"

        queue = manager.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    await asyncio.wait_for(queue.get(), timeout=30)
                    jobs = [j.to_dict() for j in manager.list_jobs()]
                    yield f"data: {json.dumps(jobs)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: str):
    manager = request.app.state.job_manager
    job = manager.get_job(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)

    result = job.to_dict()
    result["queue_position"] = manager.get_queue_position(job_id)
    return result


@router.delete("/jobs/{job_id}")
async def delete_job(request: Request, job_id: str):
    manager = request.app.state.job_manager
    if manager.delete_job(job_id):
        return {"ok": True}
    return JSONResponse({"error": "Job not found"}, status_code=404)
