"""FastAPI upload route: POST /api/upload-epub"""

import uuid

from fastapi import UploadFile, Query
from fastapi.responses import JSONResponse
from nicegui import app as nicegui_app

from .. import server_config

# token (str) → {"path": str, "filename": str}
# Populated by the upload endpoint; consumed (popped) by the polling timer in
# SubmissionForm._poll_upload.
_pending: dict[str, dict] = {}


@nicegui_app.post("/api/upload-epub")
async def upload_epub(file: UploadFile, token: str = Query(...)):
    """Accept a single EPUB file and park it under a token for the NiceGUI
    timer to pick up."""
    if not file.filename.lower().endswith(".epub"):
        return JSONResponse({"error": "EPUB 파일만 지원됩니다"}, status_code=400)

    upload_dir = server_config.UPLOAD_DIR / uuid.uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / file.filename
    dest.write_bytes(await file.read())

    _pending[token] = {"path": str(dest), "filename": file.filename}
    return {"status": "ok"}


def pop_pending(token: str) -> dict | None:
    """Return and remove the pending upload entry for *token*, or None."""
    return _pending.pop(token, None)
