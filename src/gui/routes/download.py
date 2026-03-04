"""FastAPI download route: GET /download/{token}"""

from fastapi import Response
from fastapi.responses import FileResponse
from nicegui import app as nicegui_app

from ..jobs.manager import job_manager


@nicegui_app.get("/download/{token}")
async def download_file(token: str) -> Response:
    """Serve the translated EPUB file for a given download token."""
    file_path = job_manager.resolve_download(token)

    if file_path is None:
        return Response("Download link not found or expired.", status_code=404)

    if not file_path.exists():
        return Response("File no longer available.", status_code=410)

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/epub+zip",
    )
