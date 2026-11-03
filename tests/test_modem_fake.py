"""The M0a state machine, proven against a scripted fake modem.

This proves the harness logic — probe parsing, ring/CLIP
handling, answer/record/hangup order, and the database read-back.
It does NOT prove anything about real hardware; that is M0a's
live run (docs/M0A-RUNBOOK.md), and these tests must never be
cited as a hardware result.
"""
import tempfile
import unittest
from pathlib import Path

from staxline import db as dbmod
from staxline.audio import NullAudio, tone_wav
from staxline.modem import Modem, run_m0a_call

RESPONSES = {
    "AT": ["OK"],
    "ATI": ["SIMCOM_SIM7600G-H", "OK"],
    "AT+CGSN": ["860000000000001", "OK"],  # synthetic test IMEI
    "AT+CPIN?": ["+CPIN: READY", "OK"],
    "AT+CSQ": ["+CSQ: 17,99", "OK"],
    "ATA": ["OK"],
    "ATH": [],
}


class FakeTransport:
    def __init__(self):
        self.writes = []
        self._queue = ['RING', '+CLIP: "15551234567",145', "RING"]

    def write_line(self, line):
        self.writes.append(line)
        self._queue.extend(RESPONSES.get(line, ["OK"]))

    def read_line(self, timeout=1.0):
        return self._queue.pop(0) if self._queue else None

    def close(self):
        pass


class ModemFakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = dbmod.connect(self.dir / "test.db")
        self.modem = Modem(FakeTransport())

    def tearDown(self):
        self.tmp.cleanup()

    def test_probe_reads_identity(self):
        info = self.modem.probe()
        self.assertIn("SIMCOM_SIM7600G-H", info["model"])
        self.assertIn("860000000000001", info["imei"])

    def test_m0a_call_end_to_end(self):
        greeting = tone_wav(self.dir / "greeting.wav", seconds=0.5)
        call = run_m0a_call(
            self.modem, NullAudio(), self.db, greeting,
            record_seconds=1, out_dir=self.dir,
            transcriber=lambda p: "fake transcript")
        self.assertEqual(call["number"], "15551234567")
        self.assertEqual(call["rings_before_answer"], 2)
        self.assertEqual(call["outcome"], "answered")
        self.assertIn("ATA", self.modem.t.writes)
        self.assertIn("ATH", self.modem.t.writes)
        rec = Path(call["recording_path"])
        self.assertTrue(rec.exists() and rec.stat().st_size > 1000)
        rows = self.db.execute(
            "SELECT number, outcome, transcript FROM calls").fetchall()
        self.assertEqual(rows, [("15551234567", "answered",
                                 "fake transcript")])
        acts = self.db.execute("SELECT kind FROM activity").fetchall()
        self.assertEqual(acts, [("m0a",)])


if __name__ == "__main__":
    unittest.main()
