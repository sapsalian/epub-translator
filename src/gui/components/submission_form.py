"""Submission form: file upload, email, language settings."""

import uuid
from pathlib import Path
from typing import Callable

from nicegui import ui

from src.pipeline.models import Language

# JavaScript + CSS injected once into the page <head>.
# epubDragOver / epubDragLeave / epubDrop / epubFileSelected are called by
# inline event attributes on the drop-zone element.
_HEAD_HTML = """
<style>
.epub-drop-zone {
    transition: border-color 0.15s, background-color 0.15s;
}
.epub-drop-zone.epub-drag-over {
    border-color: #3b82f6 !important;
    background-color: #eff6ff;
}
</style>
<script>
async function epubUpload(file, token) {
    if (!file.name.toLowerCase().endsWith('.epub')) {
        alert('EPUB 파일만 지원됩니다.');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    try {
        const resp = await fetch('/api/upload-epub?token=' + token, {
            method: 'POST',
            body: formData,
        });
        if (!resp.ok) {
            const data = await resp.json().catch(() => ({}));
            alert(data.error || '업로드 실패');
        }
    } catch (err) {
        alert('업로드 중 오류가 발생했습니다: ' + err);
    }
}

// Called from Python via ui.run_javascript after the drop zone is rendered,
// and again after every file removal to re-attach listeners.
// domId   : per-form-instance UUID embedded in data-domid → reliable querySelector
// uploadToken: per-session token used by epubUpload → _pending lookup
// Bound guard (data-bound="1") prevents duplicate listener accumulation.
// retries: internal counter — start omitted (defaults to 0).
// Retries up to 2 s (20 × 100 ms) to tolerate the race between
// ui.run_javascript dispatch and Vue finishing its first render.
function setupEpubDropZone(domId, uploadToken, retries) {
    var zone = document.querySelector('[data-domid="' + domId + '"]');
    if (!zone) {
        if ((retries || 0) < 20) {
            setTimeout(function() {
                setupEpubDropZone(domId, uploadToken, (retries || 0) + 1);
            }, 100);
        }
        return;
    }
    if (zone.dataset.bound === '1') return;
    zone.dataset.bound = '1';

    var input = zone.querySelector('input[type=file]');

    // Click → open native file picker synchronously within the user-gesture
    // handler (preserves browser gesture context; no WebSocket round-trip).
    zone.addEventListener('click', function(e) {
        if (e.target !== input) input.click();
    });

    zone.addEventListener('dragover', function(e) {
        e.preventDefault();
        zone.classList.add('epub-drag-over');
    });
    zone.addEventListener('dragleave', function() {
        zone.classList.remove('epub-drag-over');
    });
    zone.addEventListener('drop', function(e) {
        e.preventDefault();
        zone.classList.remove('epub-drag-over');
        var f = e.dataTransfer.files[0];
        if (f) epubUpload(f, uploadToken);
    });
    input.addEventListener('change', function() {
        var f = input.files[0];
        if (f) epubUpload(f, uploadToken);
    });
}
</script>
"""


def _drop_zone_html(dom_id: str) -> str:
    """Return the visual drop-zone HTML.

    data-domid is a per-form-instance UUID used only for querySelector — it is
    NOT the upload token.  This keeps DOM lookup reliable even if multiple tabs
    share the same upload_token via app.storage.user.
    """
    return (
        f'<div class="epub-drop-zone" data-domid="{dom_id}"'
        ' style="display:flex;flex-direction:column;align-items:center;'
        "justify-content:center;gap:8px;padding:32px;"
        "border:2px dashed #93c5fd;border-radius:8px;"
        'cursor:pointer;width:100%;box-sizing:border-box;">'
        '<input type="file" accept=".epub" style="display:none">'
        '<i class="material-icons" style="font-size:3rem;color:#60a5fa;">'
        "upload_file</i>"
        '<span style="color:#6b7280;font-size:14px;">'
        "EPUB 파일을 여기에 드래그하거나 클릭하여 선택</span>"
        '<span style="color:#9ca3af;font-size:12px;">'
        ".epub 파일만 지원됩니다</span>"
        "</div>"
    )


class SubmissionForm:
    """Form for submitting a new translation job.

    on_submit(job_params) is called with a dict when the user clicks "번역 시작".
    """

    def __init__(self, on_submit: Callable[[dict], None]):
        self._on_submit = on_submit
        self._uploaded_path: Path | None = None
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        # Both IDs are generated fresh on every page load.
        # _token  : matches uploads in _pending (server-side in-memory dict,
        #           cleared on restart anyway, so persistence adds no value).
        # _dom_id : querySelector key — unique per instance regardless.
        self._token: str = uuid.uuid4().hex
        self._dom_id: str = uuid.uuid4().hex

        ui.add_head_html(_HEAD_HTML)

        with ui.card().classes("w-full"):
            ui.label("새 번역").classes("text-lg font-bold")

            # Drop zone (click → file picker, drag → upload)
            self._drop_zone = ui.html(_drop_zone_html(self._dom_id)).classes("w-full")

            # File-selected state (hidden until upload completes)
            with ui.row().classes("items-center gap-2 px-4 py-3 w-full") as self._file_row:
                ui.icon("insert_drive_file", color="green")
                self._file_label = ui.label("").classes("text-sm text-green-700 flex-1")
                self._remove_btn = ui.button(
                    icon="close", on_click=self._handle_file_removed
                ).props("flat round dense color=grey size=xs")
            self._file_row.visible = False

            # Email
            self._email_input = ui.input(
                label="이메일 주소",
                placeholder="your@email.com",
            ).classes("w-full")
            ui.label(
                "번역 완료 시 다운로드 링크를 이메일로 보내드립니다. "
                "이 페이지에서 직접 다운로드할 수도 있습니다."
            ).classes("text-xs text-gray-400 -mt-2")

            # Language selection
            with ui.row().classes("w-full gap-4"):
                self._src_lang = ui.select(
                    label="원문 언어",
                    options={lang: lang.value for lang in Language},
                    value=Language.ENGLISH,
                ).classes("flex-1")
                self._tgt_lang = ui.select(
                    label="번역 언어",
                    options={lang: lang.value for lang in Language},
                    value=Language.KOREAN,
                ).classes("flex-1")

            # Custom instructions
            with ui.expansion("고급 설정", icon="tune").classes("w-full"):
                self._custom_instructions = ui.textarea(
                    label="추가 지시사항 (선택)",
                    placeholder="번역 시 특별히 요청할 내용을 입력하세요...",
                ).classes("w-full")

            # Submit button
            self._submit_btn = ui.button(
                "번역 시작",
                on_click=self._submit,
                icon="translate",
            ).classes("w-full").props("size=lg color=primary")
            self._submit_btn.disable()

        # Attach drag-drop + change listeners after the DOM is ready.
        # ui.run_javascript queues the call and executes it once the
        # WebSocket connection is established (i.e. after Vue has rendered).
        ui.run_javascript(f'setupEpubDropZone("{self._dom_id}", "{self._token}")')

        # Poll for upload completion every 0.5 s
        ui.timer(0.5, self._poll_upload)

    # ------------------------------------------------------------------
    # Upload polling
    # ------------------------------------------------------------------

    async def _poll_upload(self):
        from ..routes.upload import pop_pending

        data = pop_pending(self._token)
        if data is None:
            return

        self._uploaded_path = Path(data["path"])
        self._file_label.text = data["filename"]
        self._drop_zone.visible = False
        self._file_row.visible = True
        self._submit_btn.enable()
        ui.notify(f"업로드 완료: {data['filename']}", type="positive")

    # ------------------------------------------------------------------
    # File removed / reset
    # ------------------------------------------------------------------

    def _handle_file_removed(self, *_):
        self._uploaded_path = None
        self._drop_zone.visible = True
        self._file_row.visible = False
        self._submit_btn.disable()
        # Reset input value (same file → change won't re-fire without this),
        # clear the bound flag, then re-attach listeners via setupEpubDropZone.
        ui.run_javascript(
            f"(function(){{"
            f"var z=document.querySelector('[data-domid=\"{self._dom_id}\"]');"
            f"if(z){{"
            f"var i=z.querySelector('input[type=file]');if(i)i.value='';"
            f"z.dataset.bound='0';"
            f"}}"
            f"setupEpubDropZone('{self._dom_id}','{self._token}');"
            f"}})();"
        )

    def reset(self):
        """Clear form state so the user can submit another job."""
        self._handle_file_removed()
        self._email_input.value = ""
        self._custom_instructions.value = ""

    # ------------------------------------------------------------------
    # Submit
    # ------------------------------------------------------------------

    async def _submit(self):
        import asyncio

        if not self._uploaded_path:
            ui.notify("EPUB 파일을 업로드해주세요", type="warning")
            return

        email = self._email_input.value.strip()
        if not email or "@" not in email:
            ui.notify(
                "유효한 이메일 주소를 입력해주세요. 번역이 완료되면 메일로 다운로드 링크가 전송됩니다.",
                type="warning",
            )
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
