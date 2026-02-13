import subprocess
import sys
from pathlib import Path

from nicegui import ui

from src.pipeline.models import InsertionResult


class ResultCard:
    def __init__(self):
        self._output_path: Path | None = None
        self._build()

    def _build(self):
        with ui.card().classes("w-full") as self.container:
            self.container.visible = False

            with ui.row().classes("items-center gap-2"):
                self.status_icon = ui.icon("check_circle", color="green", size="md")
                ui.label("Result").classes("text-lg font-bold")

            self.result_label = ui.label("").classes("text-sm")

            with ui.row().classes("gap-2 mt-2"):
                self.open_btn = ui.button("Open Folder", on_click=self._open_folder, icon="folder_open")
                self.download_btn = ui.button("Download", on_click=self._download, icon="download")

    def show_success(self, result: InsertionResult):
        self.container.visible = True
        self._output_path = Path(result.output_path)
        self.status_icon.props("name=check_circle color=green")
        self.result_label.text = f"Output: {result.output_path}"
        self.open_btn.enable()
        self.download_btn.enable()

    def show_error(self, error: str):
        self.container.visible = True
        self.status_icon.props("name=error color=red")
        self.result_label.text = f"Error: {error}"
        self.open_btn.disable()
        self.download_btn.disable()

    def hide(self):
        self.container.visible = False

    def _open_folder(self):
        if self._output_path:
            folder = self._output_path.parent
            if sys.platform == "darwin":
                subprocess.run(["open", str(folder)])
            elif sys.platform == "win32":
                subprocess.run(["explorer", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])

    def _download(self):
        if not self._output_path or not self._output_path.exists():
            ui.notify("Output file not found", type="negative")
            return

        ui.download(str(self._output_path), self._output_path.name)
