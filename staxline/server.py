"""App server: serves the static UI and the local API.

Zero-dependency by design (stdlib http.server) so the installed
base can never break on a package index or a version conflict.
This server owns records and the UI (docs/ARCHITECTURE.md);
the modem binding is injected, so the same server runs the
real worker in production and a scripted fake in tests — and
runs UI-only, saying so honestly, when no modem is attached.

Sleep behavior: the server is a plain process; when the host
sleeps it sleeps. Nothing here pretends otherwise — ingest is
explicit (a button, and later the worker's poll), and whatever
the modem held through a sleep is picked up on the next pass.
"""
import json
import os
import re
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from . import __version__
from . import db as dbmod
from . import sms_chain

STATIC_DIR = Path(__file__).parent / "static"
CONV_RE = re.compile(r"^/api/conversations/(\d+)$")
CONV_DRAFTS_RE = re.compile(r"^/api/conversations/(\d+)/drafts$")
DRAFT_APPROVE_RE = re.compile(r"^/api/drafts/(\d+)/approve$")


class App:
    """Records + the modem seam. One lock guards the database:
    the HTTP server is threaded, SQLite is not asked to be."""

    def __init__(self, db, modem=None):
        self.db = db
        self.modem = modem
        self.lock = threading.Lock()

    # -- reads -------------------------------------------------

    def conversations(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT v.id, c.name, c.number, v.last_message_at, "
                "(SELECT COUNT(*) FROM drafts d "
                " WHERE d.conversation_id = v.id "
                "   AND d.state = 'held') AS held, "
                "(SELECT m.body FROM messages m "
                " WHERE m.conversation_id = v.id "
                " ORDER BY m.id DESC LIMIT 1) AS last_body, "
                "(SELECT m.direction FROM messages m "
                " WHERE m.conversation_id = v.id "
                " ORDER BY m.id DESC LIMIT 1) AS last_dir "
                "FROM conversations v "
                "JOIN contacts c ON c.id = v.contact_id "
                "ORDER BY v.last_message_at DESC").fetchall()
        return [{"id": r[0], "name": r[1], "number": r[2],
                 "last_message_at": r[3], "held_drafts": r[4],
                 "last_body": r[5], "last_direction": r[6]}
                for r in rows]

    def conversation(self, conv_id):
        with self.lock:
            head = self.db.execute(
                "SELECT c.name, c.number FROM conversations v "
                "JOIN contacts c ON c.id = v.contact_id "
                "WHERE v.id = ?", (conv_id,)).fetchone()
            if head is None:
                return None
            msgs = self.db.execute(
                "SELECT id, direction, body, state, created_at "
                "FROM messages WHERE conversation_id = ? "
                "ORDER BY id", (conv_id,)).fetchall()
            drafts = self.db.execute(
                "SELECT id, body, state, created_at FROM drafts "
                "WHERE conversation_id = ? ORDER BY id",
                (conv_id,)).fetchall()
        return {
            "id": conv_id, "name": head[0], "number": head[1],
            "messages": [
                {"id": m[0], "direction": m[1], "body": m[2],
                 "state": m[3], "at": m[4]} for m in msgs],
            "drafts": [
                {"id": d[0], "body": d[1], "state": d[2],
                 "at": d[3]} for d in drafts],
        }

    def contacts(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT id, name, number, first_contact_at, "
                "last_contact_at FROM contacts "
                "ORDER BY last_contact_at DESC").fetchall()
        return [{"id": r[0], "name": r[1], "number": r[2],
                 "first_contact_at": r[3], "last_contact_at": r[4]}
                for r in rows]

    def activity(self, limit=50):
        with self.lock:
            rows = self.db.execute(
                "SELECT at, kind, text FROM activity "
                "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"at": r[0], "kind": r[1], "text": r[2]}
                for r in rows]

    # -- writes ------------------------------------------------

    def hold_draft(self, conv_id, body):
        with self.lock:
            exists = self.db.execute(
                "SELECT 1 FROM conversations WHERE id = ?",
                (conv_id,)).fetchone()
            if exists is None:
                return None
            return dbmod.add_draft(self.db, conv_id, body)

    def approve_draft(self, draft_id):
        if self.modem is None:
            raise RuntimeError("modem worker not connected")
        with self.lock:
            return sms_chain.approve_and_send(self.modem, self.db,
                                              draft_id)

    def ingest(self):
        if self.modem is None:
            raise RuntimeError("modem worker not connected")
        with self.lock:
            return len(sms_chain.ingest_sms(self.modem, self.db))


def make_handler(app):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIR),
                             **kwargs)

        def do_GET(self):
            path = urlparse(self.path).path
            try:
                if path == "/api/health":
                    return self._json({
                        "status": "ok", "app": "staxline",
                        "version": __version__,
                        "modem": app.modem is not None})
                if path == "/api/conversations":
                    return self._json(app.conversations())
                m = CONV_RE.match(path)
                if m:
                    conv = app.conversation(int(m.group(1)))
                    if conv is None:
                        return self._json({"error": "no such "
                                           "conversation"},
                                          status=404)
                    return self._json(conv)
                if path == "/api/contacts":
                    return self._json(app.contacts())
                if path == "/api/activity":
                    return self._json(app.activity())
                if path.startswith("/api/"):
                    return self._json({"error": "not implemented"},
                                      status=404)
            except Exception as e:
                return self._json({"error": str(e)}, status=502)
            if path == "/":
                self.path = "/index.html"
            return super().do_GET()

        def do_POST(self):
            path = urlparse(self.path).path
            try:
                if path == "/api/ingest":
                    return self._json({"ingested": app.ingest()})
                m = CONV_DRAFTS_RE.match(path)
                if m:
                    body = self._body().get("body", "").strip()
                    if not body:
                        return self._json({"error": "empty draft"},
                                          status=400)
                    draft_id = app.hold_draft(int(m.group(1)), body)
                    if draft_id is None:
                        return self._json({"error": "no such "
                                           "conversation"},
                                          status=404)
                    return self._json({"draft_id": draft_id,
                                       "state": "held"})
                m = DRAFT_APPROVE_RE.match(path)
                if m:
                    state = app.approve_draft(int(m.group(1)))
                    return self._json({"state": state})
                return self._json({"error": "not implemented"},
                                  status=404)
            except ValueError as e:
                return self._json({"error": str(e)}, status=409)
            except RuntimeError as e:
                return self._json({"error": str(e)}, status=503)
            except Exception as e:
                return self._json({"error": str(e)}, status=502)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(n) if n else b"{}"
            return json.loads(raw.decode() or "{}")

        def _json(self, payload, status=200):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):  # keep the console quiet
            pass

    return Handler


def build_server(host, port, db_path, modem=None):
    db = dbmod.connect(db_path)
    app = App(db, modem=modem)
    return ThreadingHTTPServer((host, port), make_handler(app))


def _default_modem():
    """The real Linux binding when this platform has one. Its
    calls fail honestly (502s naming the modem) on a machine
    without ModemManager or the unit attached."""
    try:
        from .qmi_modem import MmClient
        return MmClient()
    except Exception:
        return None


def main():
    port = int(os.environ.get("STAXLINE_PORT", "8787"))
    host = os.environ.get("STAXLINE_HOST", "127.0.0.1")
    db_path = os.environ.get("STAXLINE_DB", "staxline.db")
    server = build_server(host, port, db_path,
                          modem=_default_modem())
    print(f"StaxLine at http://{host}:{port} (db: {db_path})")
    server.serve_forever()


if __name__ == "__main__":
    main()
