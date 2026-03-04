import threading
import time
import urllib.request


def start_server(port: int) -> None:
    """uvicorn을 daemon thread로 시작."""
    import uvicorn
    from src.app.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()


def wait_for_server(port: int, timeout: float = 15.0) -> bool:
    """서버가 응답할 때까지 polling. timeout 내 응답하면 True."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/api/health"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False
