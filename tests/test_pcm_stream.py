"""The M0b speaking path, proven with fakes.

Two things are pinned here. First, the stream's contract: one
frame per pump, speech in order, silence the moment the queue
empties — the silence is load-bearing (a starved transmit path
looped a frame into a buzz on the live call this design
answers). Second, the m0b flow end to end against a scripted
modem and a real database: answer via QMI only, greeting
queued, caller captured to a real WAV, row persisted.
"""
import tempfile
import unittest
from pathlib import Path

from staxline import db as dbmod
from staxline.audio import PcmStream, tone_wav, write_wav
from staxline.qmi_modem import FakeQmiVoice, LinuxModem, MmClient
from staxline.qmi_modem import run_m0b_call


class FakeFd:
    def __init__(self, read_chunks=()):
        self.writes = []
        self._reads = list(read_chunks)

    def read(self, _n):
        return self._reads.pop(0) if self._reads else b""

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)


class StreamTests(unittest.TestCase):
    def test_silence_frames_when_queue_empty(self):
        fd = FakeFd()
        s = PcmStream(fd)
        for _ in range(5):
            s.pump_once()
        self.assertEqual(len(fd.writes), 5)
        for frame in fd.writes:
            self.assertEqual(len(frame), s.frame_bytes)
            self.assertEqual(frame, b"\x00" * s.frame_bytes)

    def test_speech_in_order_then_silence_resumes(self):
        fd = FakeFd()
        s = PcmStream(fd)
        speech = b"\x01" * (s.frame_bytes * 2) + b"\x02" * 10
        s.queue_pcm(speech)
        s.pump_once()
        s.pump_once()
        s.pump_once()
        s.pump_once()
        self.assertEqual(fd.writes[0], b"\x01" * s.frame_bytes)
        self.assertEqual(fd.writes[1], b"\x01" * s.frame_bytes)
        self.assertTrue(fd.writes[2].startswith(b"\x02" * 10))
        self.assertEqual(fd.writes[2][10:], b"\x00" * (s.frame_bytes
                                                      - 10))
        self.assertEqual(fd.writes[3], b"\x00" * s.frame_bytes)

    def test_capture_accumulates(self):
        fd = FakeFd(read_chunks=[b"\x05" * 100, b"", b"\x06" * 50])
        s = PcmStream(fd)
        for _ in range(3):
            s.pump_once()
        self.assertEqual(bytes(s.captured),
                         b"\x05" * 100 + b"\x06" * 50)

    def test_queue_wav_rejects_wrong_rate(self):
        fd = FakeFd()
        s = PcmStream(fd)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.wav"
            write_wav(p, b"\x00\x00" * 800, rate=8000)
            with self.assertRaises(ValueError):
                s.queue_wav(p)


class M0bFlowTests(unittest.TestCase):
    def test_flow_answers_streams_and_persists(self):
        def runner(args):
            joined = " ".join(args)
            if "--voice-list-calls" in joined:
                return (0, "/org/freedesktop/ModemManager1/Call/1\n",
                        "")
            if "--output-keyvalue" in joined and "--call=" in joined:
                return (0, "call.properties.state : ringing-in\n"
                           "call.properties.number : +17018317231\n",
                        "")
            if "--hangup" in joined:
                return (0, "successfully hung up", "")
            return (1, "", "unscripted " + joined)

        voice = FakeQmiVoice()
        modem = LinuxModem(mm=MmClient(runner=runner), voice=voice)
        fd = FakeFd(read_chunks=[b"\x07" * 640])
        stream = PcmStream(fd)

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            greeting = tone_wav(td / "greeting.wav", seconds=0.1)
            db = dbmod.connect(td / "test.db")
            real_run = stream.run
            stream.run = lambda seconds: (
                stream.pump_once(), stream.pump_once())
            try:
                call = run_m0b_call(modem, stream, db, greeting, 0.1,
                                    td)
            finally:
                stream.run = real_run
            self.assertEqual(call["outcome"], "answered")
            self.assertEqual(call["answered_by"], "m0b-stream")
            self.assertEqual(len(voice.answered), 1)
            rec = Path(call["recording_path"])
            self.assertTrue(rec.exists())
            self.assertGreater(rec.stat().st_size, 44)
            rows = db.execute("SELECT COUNT(*) FROM calls").fetchone()
            self.assertEqual(rows[0], 1)
            acts = db.execute(
                "SELECT text FROM activity WHERE kind='m0b'"
            ).fetchall()
            self.assertEqual(len(acts), 1)
            self.assertIn("+17018317231", acts[0][0])


if __name__ == "__main__":
    unittest.main()
