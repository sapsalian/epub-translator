"""Job status card: shows queue position, progress, or completion state."""

from nicegui import ui

from ..jobs.manager import JobManager
from ..jobs.models import JobInfo, JobState


class JobStatusCard:
    """Displays the status of the user's current translation job.

    Call update(job, position) on each polling tick.
    """

    def __init__(self):
        self._build()

    def _build(self):
        with ui.card().classes("w-full") as self._card:
            self._card.visible = False

            with ui.row().classes("items-center gap-2"):
                self._icon = ui.icon("schedule", color="blue", size="md")
                self._title = ui.label("").classes("text-lg font-bold")

            self._detail = ui.label("").classes("text-sm text-gray-500")
            self._progress_bar = ui.linear_progress(value=0.0).classes("w-full mt-2")
            self._progress_bar.visible = False

    def show(self):
        self._card.visible = True

    def hide(self):
        self._card.visible = False

    def update(self, job: JobInfo, queue_position: int = 0):
        """Update the card display based on current job state."""
        self._card.visible = True

        if job.state == JobState.QUEUED:
            self._icon.props("name=schedule color=blue")
            self._title.text = "Waiting in queue"
            self._detail.text = (
                f"Position: #{queue_position}" if queue_position > 0 else "Waiting..."
            )
            self._progress_bar.visible = False

        elif job.state == JobState.RUNNING:
            self._icon.props("name=autorenew color=orange")
            self._title.text = "Translating..."
            stage_label = job.stage.replace("_", " ").title() if job.stage else ""
            pct = int(job.progress * 100)
            self._detail.text = f"{stage_label} — {pct}%"
            self._progress_bar.value = job.progress
            self._progress_bar.visible = True

        elif job.state == JobState.DONE:
            self._icon.props("name=check_circle color=green")
            self._title.text = "Translation complete!"
            self._detail.text = "A download link has been sent to your email."
            self._progress_bar.value = 1.0
            self._progress_bar.visible = True

        elif job.state == JobState.FAILED:
            self._icon.props("name=error color=red")
            self._title.text = "Translation failed"
            self._detail.text = (
                job.error[:200] if job.error else "An unexpected error occurred."
            )
            self._progress_bar.visible = False
