"""Job management endpoints."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.epub_walker.reader import extract_chapter_paragraphs, get_chapter_titles, render_chapter_html
from src.pipeline.persistence import CheckpointManager, FilePersistenceBackend

from ..jobs.models import JobInfo
from ..jobs.models import JobState

router = APIRouter()


class JobCreateRequest(BaseModel):
    upload_id: str
    source_language: str
    target_language: str
    custom_instructions: str = ""
    workflow_mode: str = "classic"
    workflow_options: dict[str, Any] = Field(default_factory=dict)


class GlossaryItem(BaseModel):
    source: str
    target: str


class GlossaryUpdateRequest(BaseModel):
    terms: list[GlossaryItem]


async def _get_checkpoint_manager(request: Request, job_id: str) -> CheckpointManager:
    checkpoint_path = request.app.state.config.checkpoint_dir / job_id
    backend = FilePersistenceBackend(str(checkpoint_path))
    await backend.initialize()
    return CheckpointManager(backend)


def _get_job_or_error(request: Request, job_id: str) -> JobInfo | JSONResponse:
    manager = request.app.state.job_manager
    job = manager.get_job(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return job


def _get_done_job_or_error(request: Request, job_id: str) -> JobInfo | JSONResponse:
    job = _get_job_or_error(request, job_id)
    if isinstance(job, JSONResponse):
        return job
    if job.state != JobState.DONE:
        return JSONResponse({"error": "Job is not done yet"}, status_code=409)
    if not job.output_path:
        return JSONResponse({"error": "Output EPUB is not available"}, status_code=409)
    return job


def _resolve_source_epub_path(job: JobInfo) -> Path | None:
    candidates = []
    if job.source_epub_path:
        candidates.append(Path(job.source_epub_path))
    if job.input_path:
        candidates.append(Path(job.input_path))
    for path in candidates:
        if path.exists():
            return path
    return None


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
        workflow_mode=body.workflow_mode,
        workflow_options=body.workflow_options,
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
    job = _get_job_or_error(request, job_id)
    if isinstance(job, JSONResponse):
        return job

    result = job.to_dict()
    result["queue_position"] = manager.get_queue_position(job_id)
    return result


@router.get("/jobs/{job_id}/chapters")
async def get_job_chapters(request: Request, job_id: str):
    job = _get_done_job_or_error(request, job_id)
    if isinstance(job, JSONResponse):
        return job

    output_path = Path(job.output_path)
    with ZipFile(output_path) as translation_zf:
        titles = get_chapter_titles(translation_zf)

    return [
        {"chapter_id": f"ch{index:03d}", "title": title}
        for index, title in enumerate(titles)
    ]


@router.get("/jobs/{job_id}/chapters/{chapter_id}")
async def get_job_chapter_content(request: Request, job_id: str, chapter_id: str):
    job = _get_done_job_or_error(request, job_id)
    if isinstance(job, JSONResponse):
        return job
    if not chapter_id.startswith("ch") or not chapter_id[2:].isdigit():
        return JSONResponse({"error": "Invalid chapter id"}, status_code=400)

    chapter_idx = int(chapter_id[2:])
    output_path = Path(job.output_path)
    source_path = _resolve_source_epub_path(job)

    with ZipFile(output_path) as translation_zf:
        titles = get_chapter_titles(translation_zf)
        if chapter_idx < 0 or chapter_idx >= len(titles):
            return JSONResponse({"error": "Chapter not found"}, status_code=404)

        translation_html = render_chapter_html(translation_zf, chapter_idx, chapter_id)

        source_html: str | None = None
        if source_path is not None:
            with ZipFile(source_path) as source_zf:
                paragraphs = extract_chapter_paragraphs(source_zf, translation_zf, chapter_idx, chapter_id)
                source_html = render_chapter_html(source_zf, chapter_idx, chapter_id)
        else:
            paragraphs = extract_chapter_paragraphs(None, translation_zf, chapter_idx, chapter_id)

    return {
        "chapter_id": chapter_id,
        "title": titles[chapter_idx],
        "paragraphs": paragraphs,
        "source_html": source_html,
        "translation_html": translation_html,
    }


@router.post("/jobs/{job_id}/retry")
async def retry_job(request: Request, job_id: str):
    manager = request.app.state.job_manager
    job = manager.get_job(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.state.value != "failed":
        return JSONResponse({"error": "Only failed jobs can be retried"}, status_code=400)

    job.state = JobState.QUEUED
    job.progress = 0.0
    job.stage = ""
    job.error = ""
    job.download_token = None
    job.output_path = None
    manager.save()
    await manager.queue.put(job_id)
    return {"ok": True}


@router.get("/jobs/{job_id}/glossary")
async def get_job_glossary(request: Request, job_id: str):
    manager = request.app.state.job_manager
    job = manager.get_job(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.workflow_mode != "glossary_review":
        return JSONResponse({"error": "Job is not in glossary_review mode"}, status_code=400)
    if not job.epub_id:
        return JSONResponse({"error": "Glossary is not ready yet"}, status_code=409)

    checkpoint_manager = await _get_checkpoint_manager(request, job_id)
    preprocess = await checkpoint_manager.load_preprocess(job.epub_id, job.target_language)
    if preprocess is None:
        return JSONResponse({"error": "Preprocess checkpoint not found"}, status_code=409)

    edited = await checkpoint_manager.load_glossary_edit(job.epub_id, job.target_language)
    mappings = edited if edited is not None else preprocess.term_dictionary.mappings
    terms = [{"source": source, "target": target} for source, target in sorted(mappings.items())]
    return {"terms": terms, "has_edits": edited is not None}


@router.put("/jobs/{job_id}/glossary")
async def update_job_glossary(request: Request, job_id: str, body: GlossaryUpdateRequest):
    manager = request.app.state.job_manager
    job = manager.get_job(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.workflow_mode != "glossary_review":
        return JSONResponse({"error": "Job is not in glossary_review mode"}, status_code=400)
    if job.state != JobState.AWAITING_REVIEW:
        return JSONResponse({"error": "Job is not awaiting review"}, status_code=409)
    if not job.epub_id:
        return JSONResponse({"error": "Glossary is not ready yet"}, status_code=409)

    mappings: dict[str, str] = {}
    for item in body.terms:
        source = item.source.strip()
        target = item.target.strip()
        if not source or not target:
            return JSONResponse({"error": "source and target must be non-empty"}, status_code=400)
        if source in mappings:
            return JSONResponse({"error": f"duplicate source term: {source}"}, status_code=400)
        mappings[source] = target

    checkpoint_manager = await _get_checkpoint_manager(request, job_id)
    await checkpoint_manager.save_glossary_edit(job.epub_id, job.target_language, mappings)
    return {"ok": True, "count": len(mappings)}


@router.post("/jobs/{job_id}/continue")
async def continue_job(request: Request, job_id: str):
    manager = request.app.state.job_manager
    job = manager.get_job(job_id)
    if job is None:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    if job.workflow_mode != "glossary_review":
        return JSONResponse({"error": "Job is not in glossary_review mode"}, status_code=400)
    if job.state != JobState.AWAITING_REVIEW:
        return JSONResponse({"error": "Job is not awaiting review"}, status_code=409)

    job.state = JobState.QUEUED
    job.error = ""
    job.workflow_options["review_approved"] = True
    manager.save()
    await manager.queue.put(job_id)
    return {"ok": True}


@router.delete("/jobs/{job_id}")
async def delete_job(request: Request, job_id: str):
    manager = request.app.state.job_manager
    if manager.delete_job(job_id):
        return {"ok": True}
    return JSONResponse({"error": "Job not found"}, status_code=404)
