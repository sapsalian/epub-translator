"""Main application view (requires authentication)."""

import uuid

from nicegui import ui, app

from ..auth import logout, require_auth
from ..jobs.manager import job_manager
from ..jobs.models import JobInfo, JobState
from ..components.submission_form import SubmissionForm
from ..components.job_status_card import JobStatusCard


class MainView:
    """Main page: submission form + job status for the current client."""

    def __init__(self):
        self._job_id: str | None = None
        self._polling_timer = None

    def build(self):
        if not require_auth():
            return

        with ui.column().classes("w-full max-w-2xl mx-auto p-4 gap-4"):
            # Header
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("EPUB 번역기").classes("text-2xl font-bold")
                ui.button("로그아웃", on_click=logout, icon="logout").props(
                    "flat color=grey"
                )

            # Submission form area (shown by default)
            with ui.column().classes("w-full") as self._form_area:
                self._form = SubmissionForm(on_submit=self._handle_submit)

            # Status area (hidden until job submitted or restored)
            with ui.column().classes("w-full gap-3") as self._status_area:
                self._status_card = JobStatusCard()
                self._new_translation_btn = ui.button(
                    "새 번역 시작", on_click=self._reset_to_form, icon="add"
                ).props("outline").classes("self-start")
                self._new_translation_btn.visible = False

        # Restore job from client storage (page reload resilience)
        stored_job_id = app.storage.client.get("job_id")
        if stored_job_id and job_manager.get_status(stored_job_id):
            self._job_id = stored_job_id
            self._show_status_view()
            self._start_polling()
        else:
            self._show_form_view()

    def _show_form_view(self):
        self._form_area.set_visibility(True)
        self._status_area.set_visibility(False)

    def _show_status_view(self):
        self._form_area.set_visibility(False)
        self._status_area.set_visibility(True)

    def _reset_to_form(self):
        app.storage.client.pop("job_id", None)
        self._job_id = None
        self._stop_polling()
        self._form.reset()
        self._new_translation_btn.visible = False
        self._show_form_view()

    async def _handle_submit(self, params: dict):
        job_id = uuid.uuid4().hex
        job = JobInfo(
            job_id=job_id,
            epub_filename=params["epub_filename"],
            epub_path_str=str(params["epub_path"]),
            email=params["email"],
            source_language=params["source_language"],
            target_language=params["target_language"],
            custom_instructions=params["custom_instructions"],
        )
        await job_manager.submit(job)
        self._job_id = job_id
        app.storage.client["job_id"] = job_id
        self._show_status_view()
        self._start_polling()
        ui.notify("번역 요청이 접수되었습니다! 완료되면 이메일로 알려드리겠습니다.", type="positive")

    def _start_polling(self):
        async def poll():
            if not self._job_id:
                return
            job = job_manager.get_status(self._job_id)
            if job is None:
                self._stop_polling()
                return
            position = job_manager.get_queue_position(self._job_id)
            try:
                self._status_card.update(job, position)
            except RuntimeError:
                self._stop_polling()
                return
            if job.state in (JobState.DONE, JobState.FAILED):
                self._stop_polling()
                self._new_translation_btn.visible = True

        self._polling_timer = ui.timer(2.0, poll)

    def _stop_polling(self):
        if self._polling_timer:
            self._polling_timer.deactivate()
            self._polling_timer = None
