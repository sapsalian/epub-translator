from nicegui import ui

from src.pipeline.persistence.models import JobStatus, JobStage


class ProgressCard:
    def __init__(self):
        self.visible = False
        self._build()

    def _build(self):
        with ui.card().classes("w-full") as self.container:
            self.container.visible = False

            ui.label("Progress").classes("text-lg font-bold")

            with ui.column().classes("w-full gap-2"):
                # Overall progress
                with ui.row().classes("w-full items-center"):
                    ui.label("Overall:").classes("w-20")
                    self.overall_progress = ui.linear_progress(value=0, show_value=False).classes(
                        "flex-grow"
                    )
                    self.overall_label = ui.label("0%").classes("w-12 text-right")

                # Current stage
                self.stage_label = ui.label("Stage: PENDING").classes("text-sm text-gray-600")

                # Stage progress
                with ui.row().classes("w-full items-center"):
                    ui.label("Stage:").classes("w-20")
                    self.stage_progress = ui.linear_progress(value=0, show_value=False).classes(
                        "flex-grow"
                    )
                    self.stage_progress_label = ui.label("0/0").classes("w-16 text-right")

    def show(self):
        self.container.visible = True

    def hide(self):
        self.container.visible = False

    def update(self, status: JobStatus):
        self.overall_progress.value = status.overall_progress
        self.overall_label.text = f"{status.overall_percentage:.0f}%"
        self.stage_label.text = f"Stage: {status.stage.value.upper()}"

        # Update stage-specific progress
        stage_data = getattr(status, status.stage.value, None)
        if stage_data and hasattr(stage_data, "total") and stage_data.total > 0:
            self.stage_progress.value = stage_data.completed / stage_data.total
            self.stage_progress_label.text = f"{stage_data.completed}/{stage_data.total}"
