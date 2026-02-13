from nicegui import ui

from ..state import app_state


class LogViewer:
    def __init__(self):
        self._build()

    def _build(self):
        with ui.expansion("Logs", icon="terminal").classes("w-full"):
            with ui.row().classes("w-full justify-end mb-2"):
                ui.button("Clear", on_click=self.clear, icon="delete").props("flat dense")

            self.log_area = ui.log(max_lines=500).classes("w-full h-48 font-mono text-xs")

    def add_log(self, message: str):
        self.log_area.push(message)

    def clear(self):
        self.log_area.clear()
