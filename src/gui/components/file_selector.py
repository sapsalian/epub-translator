from pathlib import Path
from typing import Callable

from nicegui import ui, events


class FileSelector:
    def __init__(self, on_file_selected: Callable[[Path], None], upload_dir: Path | None = None):
        self.on_file_selected = on_file_selected
        self.selected_file: Path | None = None
        self.upload_dir = upload_dir or Path("./uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self._build()

    def _build(self):
        with ui.card().classes("w-full"):
            ui.label("Select EPUB File").classes("text-lg font-bold")

            with ui.row().classes("w-full items-center gap-4"):
                self.file_label = ui.label("No file selected").classes(
                    "text-gray-500 flex-1"
                )
                ui.upload(
                    label="Browse...",
                    on_upload=self._handle_upload,
                    auto_upload=True,
                    max_files=1,
                ).props('accept=".epub"').classes("max-w-xs")

    async def _handle_upload(self, e: events.UploadEventArguments):
        # Save uploaded file to upload directory
        filename = e.file.name
        dest_path = self.upload_dir / filename

        # Save file using built-in method
        await e.file.save(dest_path)

        self._set_file(dest_path)

    def _set_file(self, path: Path):
        self.selected_file = path
        self.file_label.text = f"✓ {path.name}"
        self.file_label.classes(remove="text-gray-500", add="text-green-600")
        self.on_file_selected(path)
        ui.notify(f"Selected: {path.name}", type="positive")

    def cleanup_uploaded_file(self):
        """Delete the uploaded file after translation is complete."""
        if self.selected_file and self.selected_file.exists():
            try:
                self.selected_file.unlink()
            except OSError:
                pass
        self.selected_file = None
