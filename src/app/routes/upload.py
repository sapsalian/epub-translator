"""File upload endpoint."""

import uuid

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/upload")
async def upload_file(request: Request, file: UploadFile):
    if not file.filename or not file.filename.lower().endswith(".epub"):
        return JSONResponse({"error": "Only .epub files are supported"}, status_code=400)

    upload_id = uuid.uuid4().hex
    upload_dir = request.app.state.config.upload_dir / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    dest = upload_dir / file.filename
    dest.write_bytes(await file.read())

    return {"upload_id": upload_id, "filename": file.filename}
