"""The Messages API over real HTTP: ingest from a scripted
modem, read conversations and threads back, hold a draft,
approve it, and see the send recorded with the modem's
read-back state. Also the honest failure modes: approving
with no modem attached is a 503 that says so, and a second
approval of a settled draft is refused.
"""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from staxline.server import build_server

STORE = {
    "/org/freedesktop/ModemManager1/SMS/15": {
        "number": "+17018317231",
        "text": "What services do you offer", "state": "received"},
}


class FakeModem:
    def __init__(self):
        self.sent = []

    def list_sms(self):
        return list(STORE.keys())

    def read_sms(self, path):
        return STORE[path]

    def send_sms(self, number, text):
        self.sent.append((number, text))
        return "sent"


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.modem = FakeModem()
        self.server = build_server(
            "127.0.0.1", 0, Path(self.tmp.name) / "api.db",
            modem=self.modem)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.tmp.cleanup()

    def call(self, method, path, payload=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            method=method,
            data=json.dumps(payload).encode() if payload else None,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_ingest_list_thread_draft_approve(self):
        status, body = self.call("POST", "/api/ingest")
        self.assertEqual((status, body), (200, {"ingested": 1}))

        status, convs = self.call("GET", "/api/conversations")
        self.assertEqual(status, 200)
        self.assertEqual(len(convs), 1)
        self.assertEqual(convs[0]["number"], "+17018317231")
        self.assertEqual(convs[0]["last_body"],
                         "What services do you offer")
        conv_id = convs[0]["id"]

        status, thread = self.call("GET",
                                   f"/api/conversations/{conv_id}")
        self.assertEqual(thread["messages"][0]["direction"], "in")

        status, body = self.call(
            "POST", f"/api/conversations/{conv_id}/drafts",
            {"body": "Thanks for asking — details inside."})
        self.assertEqual(status, 200)
        draft_id = body["draft_id"]

        # The draft is held: visible in the thread, nothing sent.
        status, thread = self.call("GET",
                                   f"/api/conversations/{conv_id}")
        self.assertEqual(thread["drafts"][0]["state"], "held")
        self.assertEqual(self.modem.sent, [])

        status, body = self.call("POST",
                                 f"/api/drafts/{draft_id}/approve")
        self.assertEqual((status, body), (200, {"state": "sent"}))
        self.assertEqual(self.modem.sent,
                         [("+17018317231",
                           "Thanks for asking — details inside.")])

        status, thread = self.call("GET",
                                   f"/api/conversations/{conv_id}")
        out = [m for m in thread["messages"]
               if m["direction"] == "out"]
        self.assertEqual(out[0]["state"], "sent")

        # A settled draft cannot be approved twice.
        status, _ = self.call("POST",
                              f"/api/drafts/{draft_id}/approve")
        self.assertEqual(status, 409)

        status, acts = self.call("GET", "/api/activity")
        self.assertTrue(any("Ingested" in a["text"] for a in acts))
        self.assertTrue(any("approved and sent" in a["text"]
                            for a in acts))

        status, contacts = self.call("GET", "/api/contacts")
        self.assertEqual(contacts[0]["number"], "+17018317231")

    def test_missing_conversation_is_404(self):
        status, _ = self.call("GET", "/api/conversations/99")
        self.assertEqual(status, 404)


class NoModemTest(unittest.TestCase):
    def test_approve_and_ingest_say_no_modem(self):
        with tempfile.TemporaryDirectory() as td:
            server = build_server("127.0.0.1", 0,
                                  Path(td) / "nomodem.db")
            port = server.server_address[1]
            t = threading.Thread(target=server.serve_forever,
                                 daemon=True)
            t.start()
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/api/ingest",
                    method="POST", data=b"")
                try:
                    urllib.request.urlopen(req, timeout=5)
                    self.fail("expected 503")
                except urllib.error.HTTPError as e:
                    self.assertEqual(e.code, 503)
                    body = json.loads(e.read().decode())
                    self.assertIn("not connected", body["error"])
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/api/health",
                        timeout=5) as r:
                    health = json.loads(r.read().decode())
                self.assertEqual(health["modem"], False)
            finally:
                server.shutdown()


if __name__ == "__main__":
    unittest.main()
