from nicegui import ui

from src.pipeline import Language

from ..credentials import save_api_key
from ..state import app_state


class SettingsPanel:
    def __init__(self):
        self._build()

    def _build(self):
        with ui.expansion("Settings", icon="settings").classes("w-full"):
            with ui.column().classes("w-full gap-4"):
                # OpenAI API Key (auto-saved to system keyring)
                ui.input(
                    label="OpenAI API Key",
                    placeholder="sk-...",
                    password=True,
                    password_toggle_button=True,
                    on_change=lambda e: save_api_key(e.value),
                ).bind_value(app_state, "openai_api_key").classes("w-full")

                # Language selection
                with ui.row().classes("w-full gap-4"):
                    ui.select(
                        label="Source Language",
                        options={lang: lang.value for lang in Language},
                        value=app_state.source_language,
                    ).bind_value(app_state, "source_language").classes("w-1/2")

                    ui.select(
                        label="Target Language",
                        options={lang: lang.value for lang in Language},
                        value=app_state.target_language,
                    ).bind_value(app_state, "target_language").classes("w-1/2")

                # Custom instructions
                ui.textarea(
                    label="Custom Instructions (optional)",
                    placeholder="Additional instructions for translation...",
                ).bind_value(app_state, "custom_instructions").classes("w-full")
