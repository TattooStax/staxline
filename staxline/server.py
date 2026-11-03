"""App server: serves the static UI and the local API.

Zero-dependency by design (stdlib http.server) so the installed
base can never break on a package index or a version conflict.
Workers for modem and model live in their own processes later;
this server owns only records and the UI (docs/ARCHITECTURE.md).
"""
import json
import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import __version__

STATIC_DIR = Path(__file__).parent / "static"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/health":
            return self._json({"status": "ok", "app": "staxline",
                               "version": __version__})
        if self.path.startswith("/api/"):
            return self._json({"error": "not implemented"}, status=404)
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def _json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep the console quiet
        pass


def main():
    port = int(os.environ.get("STAXLINE_PORT", "8787"))
    host = os.environ.get("STAXLINE_HOST", "127.0.0.1")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"StaxLine skeleton at http://{host}:{port} "
          f"(UI shell only — see docs/PLAN.md)")
    server.serve_forever()


if __name__ == "__main__":
    main()
