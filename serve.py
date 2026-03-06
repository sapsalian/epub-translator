#!/usr/bin/env python
"""Background server for remote access (VPN testing).

Usage:
    python serve.py              # HTTP, 포트 8000
    SERVER_PORT=9000 python serve.py
    USE_SSL=1 python serve.py    # HTTPS (Tailscale 인증서 사용)

SSL 인증서 경로 (기본값):
    SSL_CERT=~/.epub-translator/certs/server.crt
    SSL_KEY=~/.epub-translator/certs/server.key

인증서 갱신:
    tailscale cert --cert-file ~/.epub-translator/certs/server.crt \\
                   --key-file ~/.epub-translator/certs/server.key \\
                   macbookpro.tail62db73.ts.net
"""
import os
import socket
from pathlib import Path

import uvicorn

os.environ.setdefault("ALLOW_ALL_ORIGINS", "1")

from src.app.main import app  # noqa: E402

PORT = int(os.environ.get("SERVER_PORT", 8000))
HOST = "0.0.0.0"
USE_SSL = os.environ.get("USE_SSL", "").strip() in ("1", "true", "yes")

DEFAULT_CERT = Path.home() / ".epub-translator" / "certs" / "server.crt"
DEFAULT_KEY = Path.home() / ".epub-translator" / "certs" / "server.key"

SSL_CERT = Path(os.environ.get("SSL_CERT", str(DEFAULT_CERT)))
SSL_KEY = Path(os.environ.get("SSL_KEY", str(DEFAULT_KEY)))

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
    scheme = "https" if USE_SSL else "http"

    print(f"\n  EPUB Translator Server")
    print(f"  Local:   {scheme}://localhost:{PORT}")
    print(f"  Network: {scheme}://{local_ip}:{PORT}")
    if USE_SSL:
        print(f"  Tailscale: https://{TAILSCALE_DOMAIN}:{PORT}")
    print()

    ssl_kwargs = {}
    if USE_SSL:
        if not SSL_CERT.exists() or not SSL_KEY.exists():
            print(f"  ERROR: SSL 인증서 파일이 없습니다.")
            print(f"    인증서: {SSL_CERT}")
            print(f"    키:     {SSL_KEY}")
            print(f"  아래 명령으로 발급하세요:")
            print(f"    tailscale cert --cert-file {SSL_CERT} --key-file {SSL_KEY} {TAILSCALE_DOMAIN}")
            raise SystemExit(1)
        ssl_kwargs = {"ssl_certfile": str(SSL_CERT), "ssl_keyfile": str(SSL_KEY)}

    uvicorn.run(app, host=HOST, port=PORT, log_level="info", **ssl_kwargs)
