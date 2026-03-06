#!/usr/bin/env python
"""Background server for remote access (VPN testing).

Usage:
    python serve.py              # 포트 8000, 0.0.0.0
    SERVER_PORT=9000 python serve.py

HTTPS 접속:
    tailscale serve가 443포트 HTTPS를 처리하고 로컬 8000으로 프록시함.
    → https://macbookpro.tail62db73.ts.net (포트 번호 불필요)

    tailscale serve 설정 (최초 1회):
        tailscale serve --bg 8000
"""
import os
import socket

import uvicorn

os.environ.setdefault("ALLOW_ALL_ORIGINS", "1")

from src.app.main import app  # noqa: E402

PORT = int(os.environ.get("SERVER_PORT", 8000))
HOST = "0.0.0.0"

TAILSCALE_DOMAIN = "macbookpro.tail62db73.ts.net"


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "localhost"


if __name__ == "__main__":
    local_ip = get_local_ip()
    print(f"\n  EPUB Translator Server")
    print(f"  Local:   http://localhost:{PORT}")
    print(f"  Network: http://{local_ip}:{PORT}")
    print(f"  Tailscale: https://{TAILSCALE_DOMAIN}")
    print()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
