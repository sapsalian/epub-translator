import os
from pathlib import Path
from typing import Callable

from nicegui import ui, run

from src.pipeline import PipelineConfig, PipelineOrchestrator, Language
from src.pipeline.persistence.models import JobStage

from ..state import app_state
from ..file_provider import LocalFileProvider
from ..logging_handler import setup_gui_logging
from ..components.file_selector import FileSelector
from ..components.settings_panel import SettingsPanel
from ..components.progress_card import ProgressCard
from ..components.log_viewer import LogViewer
from ..components.result_card import ResultCard


def _safe_ui_call(fn: Callable[[], None]) -> None:
    """Safely call UI function, ignoring errors if client disconnected."""
    try:
        fn()
    except RuntimeError:
        pass  # Client disconnected, ignore UI updates


class SingleTranslationView:
    def __init__(self):
        self.orchestrator: PipelineOrchestrator | None = None
        self.file_provider = LocalFileProvider()
        self.polling_timer = None

    def build(self):
        with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
            # Header
            ui.label("EPUB Translator").classes("text-2xl font-bold")

            # File selection
            self.file_selector = FileSelector(on_file_selected=self._on_file_selected)

            # Settings
            self.settings_panel = SettingsPanel()

            # Start button
            self.start_btn = ui.button(
                "Start Translation",
                on_click=self._start_translation,
                icon="translate",
            ).classes("w-full").props("size=lg color=primary")
            self.start_btn.disable()

            # Progress
            self.progress_card = ProgressCard()

            # Log viewer
            self.log_viewer = LogViewer()

            # Result
            self.result_card = ResultCard()

        # Setup log capture
        setup_gui_logging(self.log_viewer.add_log)

    def _on_file_selected(self, path: Path):
        app_state.current_epub = path
        self.start_btn.enable()
        self.result_card.hide()
        ui.notify(f"Selected: {path.name}")

    async def _start_translation(self):
        if not app_state.current_epub:
            ui.notify("Please select an EPUB file first", type="warning")
            return

        # Validate API key
        api_key = app_state.openai_api_key.strip()
        if not api_key:
            ui.notify("Please enter your OpenAI API key in Settings", type="warning")
            return

        app_state.is_running = True
        self.start_btn.disable()
        self.start_btn.text = "Translating..."
        self.progress_card.show()
        self.result_card.hide()

        try:
            # Set API key as environment variable
            os.environ["OPENAI_API_KEY"] = api_key

            # Create config (model is fixed to gpt-4.1-mini)
            config = PipelineConfig(
                source_language=app_state.source_language,
                target_language=app_state.target_language,
                model="gpt-4.1-mini",
                custom_instructions=app_state.custom_instructions,
                output_dir=app_state.output_dir,
                checkpoint_dir=app_state.checkpoint_dir,
            )

            self.orchestrator = PipelineOrchestrator(config)
            await self.orchestrator.initialize()

            # Start progress polling
            self._start_polling()

            # Run translation
            epub_path = await self.file_provider.get_epub_path(str(app_state.current_epub))
            result = await self.orchestrator.run(epub_path)

            # Success
            _safe_ui_call(lambda: self.result_card.show_success(result))
            _safe_ui_call(lambda: ui.notify("Translation completed!", type="positive"))

        except Exception as e:
            error_msg = str(e)
            _safe_ui_call(lambda: self.result_card.show_error(error_msg))
            _safe_ui_call(lambda: ui.notify(f"Translation failed: {error_msg}", type="negative"))

        finally:
            self._stop_polling()
            self.file_selector.cleanup_uploaded_file()
            app_state.current_epub = None
            app_state.is_running = False
            _safe_ui_call(lambda: self.start_btn.enable())
            _safe_ui_call(lambda: setattr(self.start_btn, "text", "Start Translation"))

    def _start_polling(self):
        async def poll():
            try:
                if self.orchestrator and app_state.current_epub:
                    status = await self.orchestrator.get_job_status(app_state.current_epub)
                    if status:
                        self.progress_card.update(status)
                        if status.stage in (JobStage.COMPLETED, JobStage.FAILED):
                            self._stop_polling()
            except RuntimeError:
                self._stop_polling()  # Client disconnected

        self.polling_timer = ui.timer(0.5, poll)

    def _stop_polling(self):
        if self.polling_timer:
            self.polling_timer.deactivate()
            self.polling_timer = None
