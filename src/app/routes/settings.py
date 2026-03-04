"""Settings endpoints."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class SettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    model: str | None = None
    source_language: str | None = None
    target_language: str | None = None


@router.get("/settings")
async def get_settings(request: Request):
    manager = request.app.state.settings_manager
    return manager.settings.to_public_dict()


@router.put("/settings")
async def update_settings(request: Request, body: SettingsUpdate):
    manager = request.app.state.settings_manager
    updated = manager.update(**body.model_dump(exclude_none=True))
    return updated.to_public_dict()
