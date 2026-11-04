import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from staxline.server import build_server


class SmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = build_server(
            "127.0.0.1", 0, Path(cls.tmp.name) / "smoke.db")
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def get(self, path):
        with urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}{path}", timeout=5) as r:
            return r.status, r.read().decode()

    def test_health(self):
        status, body = self.get("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["app"], "staxline")

    def test_ui_shell_has_four_tabs(self):
        status, body = self.get("/")
        self.assertEqual(status, 200)
        for tab in ("messages", "phone", "contacts", "calendar"):
            self.assertIn(f'data-tab="{tab}"', body)


if __name__ == "__main__":
    unittest.main()
