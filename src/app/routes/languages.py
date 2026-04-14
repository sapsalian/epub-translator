"""Language list endpoint."""

from fastapi import APIRouter

from src.pipeline.models import Language

router = APIRouter()

_LANGUAGE_LABELS: dict[str, str] = {
    "ko": "Korean",
    "en": "English",
    "ja": "Japanese",
    "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "da": "Danish",
}


@router.get("/languages")
async def list_languages():
    languages = [
        {"code": lang.value, "label": _LANGUAGE_LABELS.get(lang.value, lang.value)}
        for lang in Language
    ]
    return {"languages": languages}
