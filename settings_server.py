"""Local web UI for Membean bot settings."""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from env_store import apply_api_payload, settings_for_api

ROOT = Path(__file__).resolve().parent
PAGE_PATH = ROOT / "settings" / "index.html"
DEFAULT_PORT = 8765


class SettingsHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[settings] {self.address_string()} — {fmt % args}")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json_response(self, status: int, data: dict) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            if not PAGE_PATH.exists():
                self._send(500, b"settings/index.html missing", "text/plain")
                return
            self._send(200, PAGE_PATH.read_bytes(), "text/html; charset=utf-8")
            return
        if path == "/api/settings":
            self._json_response(200, {"ok": True, "settings": settings_for_api()})
            return
        self._send(404, b"Not found", "text/plain")

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/settings":
            self._send(404, b"Not found", "text/plain")
            return

        length = int(self.headers.get("Content-Length", 0))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            apply_api_payload(payload)
            self._json_response(200, {"ok": True, "message": "Gespeichert"})
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            self._json_response(400, {"ok": False, "message": str(exc)})


def run_settings_server(port: int = DEFAULT_PORT, open_browser: bool = True) -> None:
    server = HTTPServer(("127.0.0.1", port), SettingsHandler)
    url = f"http://127.0.0.1:{port}"
    print("Membean Einstellungen")
    print("-" * 40)
    print(f"Öffne: {url}")
    print("Ctrl+C zum Beenden")
    print()

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer beendet.")
    finally:
        server.server_close()
