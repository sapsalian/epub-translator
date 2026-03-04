"""Download endpoint for translated EPUB files."""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, Response

router = APIRouter()


@router.get("/download/{token}")
async def download_file(request: Request, token: str) -> Response:
    manager = request.app.state.job_manager
    file_path = manager.resolve_download(token)

    if file_path is None:
        return Response("Download link not found or expired.", status_code=404)

    if not file_path.exists():
        return Response("File no longer available.", status_code=410)

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/epub+zip",
    )
