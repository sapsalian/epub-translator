"""데스크탑 앱 메인 클래스."""
import webview

from .downloader import DesktopDownloadApi
from .port_finder import find_free_port
from .server import start_server, wait_for_server


class DesktopApp:
    """pywebview 기반 데스크탑 앱."""

    def run(self) -> None:
        port = find_free_port()
        start_server(port)

        if not wait_for_server(port):
            raise RuntimeError("FastAPI 서버가 시작되지 않았습니다.")

        api = DesktopDownloadApi(port)
        window = webview.create_window(
            "EPUB Translator",
            url=f"http://127.0.0.1:{port}",
            width=1024,
            height=768,
            min_size=(800, 600),
            js_api=api,
        )
        api.set_window(window)
        webview.start(debug=False)
