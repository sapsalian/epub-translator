"""Submission form: file upload, email, language settings."""

import uuid
from pathlib import Path
from typing import Callable

from nicegui import ui, events

from src.pipeline.models import Language
from .. import server_config


class SubmissionForm:
    """Form for submitting a new translation job.

    on_submit(job_params) is called with a dict when the user submits.
    """

    def __init__(self, on_submit: Callable[[dict], None]):
        self._on_submit = on_submit
        self._uploaded_path: Path | None = None
        self._build()

    def _build(self):
        with ui.card().classes("w-full"):
            ui.label("New Translation").classes("text-lg font-bold")

            # File upload
            self._file_label = ui.label("No file selected").classes(
                "text-sm text-gray-500"
            )
            ui.upload(
                label="Browse EPUB...",
                on_upload=self._handle_upload,
                auto_upload=True,
                max_files=1,
            ).props('accept=".epub"').classes("w-full")

            # Email
            self._email_input = ui.input(
                label="Email address",
                placeholder="you@example.com",
            ).classes("w-full")

            # Language selection
            with ui.row().classes("w-full gap-4"):
                self._src_lang = ui.select(
                    label="Source Language",
                    options={lang: lang.value for lang in Language},
                    value=Language.ENGLISH,
                ).classes("flex-1")

                self._tgt_lang = ui.select(
                    label="Target Language",
                    options={lang: lang.value for lang in Language},
                    value=Language.KOREAN,
                ).classes("flex-1")

            # Custom instructions (collapsible)
            with ui.expansion("Advanced settings", icon="tune").classes("w-full"):
                self._custom_instructions = ui.textarea(
                    label="Custom Instructions (optional)",
                    placeholder="Additional instructions for translation...",
                ).classes("w-full")

            # Submit button
            self._submit_btn = ui.button(
                "Submit Translation",
                on_click=self._submit,
                icon="translate",
            ).classes("w-full").props("size=lg color=primary")
            self._submit_btn.disable()

    async def _handle_upload(self, e: events.UploadEventArguments):
        filename = e.file.name
        upload_dir = server_config.UPLOAD_DIR / uuid.uuid4().hex
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / filename
        await e.file.save(dest)
        self._uploaded_path = dest
        self._file_label.text = f"✓ {filename}"
        self._file_label.classes(remove="text-gray-500", add="text-green-600")
        self._submit_btn.enable()
        ui.notify(f"Uploaded: {filename}", type="positive")

    async def _submit(self):
        import asyncio

        if not self._uploaded_path:
            ui.notify("Please upload an EPUB file", type="warning")
            return

        email = self._email_input.value.strip()
        if not email or "@" not in email:
            ui.notify("Please enter a valid email address", type="warning")
            return

        self._submit_btn.disable()
        result = self._on_submit(
            {
                "epub_path": self._uploaded_path,
                "epub_filename": self._uploaded_path.name,
                "email": email,
                "source_language": self._src_lang.value,
                "target_language": self._tgt_lang.value,
                "custom_instructions": self._custom_instructions.value or "",
            }
        )
        if asyncio.iscoroutine(result):
            await result
