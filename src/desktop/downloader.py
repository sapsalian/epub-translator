"""pywebview js_api - 네이티브 저장 다이얼로그."""

import urllib.request

import webview
from webview import FileDialog


class DesktopDownloadApi:
    """프론트엔드에서 window.pywebview.api.download()로 호출되는 다운로드 핸들러."""

    def __init__(self, port: int) -> None:
        self._port = port
        self._window: webview.Window | None = None

    def set_window(self, window: webview.Window) -> None:
        self._window = window

    def download(self, token: str, suggested_filename: str) -> bool:
        if self._window is None:
            return False

        save_path = self._window.create_file_dialog(
            FileDialog.SAVE,
            save_filename=suggested_filename,
            file_types=("EPUB Files (*.epub)", "All Files (*.*)"),
        )
        if not save_path:
            return False

        dest = save_path[0] if isinstance(save_path, (list, tuple)) else save_path
        url = f"http://127.0.0.1:{self._port}/download/{token}"
        urllib.request.urlretrieve(url, dest)
        return True
