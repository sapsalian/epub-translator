"""Job status card: shows queue position, progress, or completion state."""

from nicegui import ui

from ..jobs.models import JobInfo, JobState

_STAGE_LABELS: dict[str, str] = {
    "extracting": "텍스트 추출",
    "preprocessing": "전처리",
    "translating": "번역",
    "inserting": "결과 삽입",
    "done": "완료",
}


class JobStatusCard:
    """Displays the status of the user's current translation job.

    Call update(job, position) on each polling tick.
    """

    def __init__(self):
        self._download_token: str | None = None
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

            self._close_tab_note = ui.label(
                "이 탭을 닫아도 괜찮습니다 — 번역은 서버에서 계속됩니다."
            ).classes("text-xs text-gray-400 mt-1")
            self._close_tab_note.visible = False

            self._download_btn = ui.button(
                "EPUB 다운로드", icon="download", on_click=self._handle_download
            ).props("color=positive").classes("mt-1")
            self._download_btn.visible = False

    def _handle_download(self):
        if self._download_token:
            ui.navigate.to(f"/download/{self._download_token}")

    def show(self):
        self._card.visible = True

    def hide(self):
        self._card.visible = False

    def update(self, job: JobInfo, queue_position: int = 0):
        """Update the card display based on current job state."""
        self._card.visible = True

        if job.state == JobState.QUEUED:
            self._icon.props("name=schedule color=blue")
            self._title.text = "대기 중"
            self._detail.text = (
                f"{queue_position}번째 대기 중" if queue_position > 0 else "잠시만 기다려주세요..."
            )
            self._progress_bar.visible = False
            self._close_tab_note.visible = True
            self._download_btn.visible = False

        elif job.state == JobState.RUNNING:
            self._icon.props("name=autorenew color=orange")
            self._title.text = "번역 진행 중..."
            stage_label = _STAGE_LABELS.get(job.stage, job.stage) if job.stage else ""
            pct = int(job.progress * 100)
            self._detail.text = f"{stage_label} — {pct}%"
            self._progress_bar.value = job.progress
            self._progress_bar.visible = True
            self._close_tab_note.visible = True
            self._download_btn.visible = False

        elif job.state == JobState.DONE:
            self._icon.props("name=check_circle color=green")
            self._title.text = "번역 완료!"
            self._detail.text = "이메일로도 다운로드 링크를 보내드렸습니다."
            self._progress_bar.value = 1.0
            self._progress_bar.visible = True
            self._close_tab_note.visible = False
            self._download_token = job.download_token
            self._download_btn.visible = bool(job.download_token)

        elif job.state == JobState.FAILED:
            self._icon.props("name=error color=red")
            self._title.text = "번역 실패"
            self._detail.text = (
                job.error[:200] if job.error else "예기치 않은 오류가 발생했습니다."
            )
            self._progress_bar.visible = False
            self._close_tab_note.visible = False
            self._download_btn.visible = False
