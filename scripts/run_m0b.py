#!/usr/bin/env python3
"""M0b speaking-path runner (Linux): answer one call on the
real modem, stream a greeting, capture the caller, hang up.

    python3 scripts/run_m0b.py --probe          # read-only
    python3 scripts/run_m0b.py --answer-once    # armed: one call

The default greeting is the melody test signal (three distinct
tones) — if the caller hears the notes, transmit audio flows;
if they hear a steady buzz, the path is starving. It is a test
signal, not a voice; pass --greeting <wav> (16-bit, 16 kHz) to
stream a real greeting instead. Runs as root on the bench: the
modem's audio endpoint and QMI device are root-owned there.
"""
import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from staxline import db as dbmod  # noqa: E402
from staxline.audio import OsPcmFd, PcmStream, melody_wav  # noqa: E402
from staxline.qmi_modem import LinuxModem, run_m0b_call  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="read-only modem probe and exit")
    ap.add_argument("--answer-once", action="store_true",
                    help="arm for exactly one call")
    ap.add_argument("--greeting", default=None,
                    help="16-bit 16 kHz WAV to stream "
                         "(default: the melody test signal)")
    ap.add_argument("--audio-dev", default="/dev/ttyUSB4")
    ap.add_argument("--record-seconds", type=float, default=20.0)
    ap.add_argument("--wait-seconds", type=float, default=600.0)
    ap.add_argument("--db", default="staxline.db")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    modem = LinuxModem()
    if args.probe:
        print(modem.probe())
        return 0
    if not args.answer_once:
        ap.error("choose --probe or --answer-once")

    greeting = args.greeting
    if greeting is None:
        tmp = Path(tempfile.mkdtemp(prefix="staxline-m0b-"))
        greeting = str(melody_wav(tmp / "test-melody.wav"))
        print(f"test signal: {greeting}")

    class TimedModem:
        """Applies the arm window to the stock wait."""
        def __init__(self, inner):
            self.inner = inner

        def wait_for_call(self):
            return self.inner.wait_for_call(timeout=args.wait_seconds)

        def __getattr__(self, name):
            return getattr(self.inner, name)

    fd = OsPcmFd(args.audio_dev)
    stream = PcmStream(fd)
    db = dbmod.connect(args.db)
    try:
        call = run_m0b_call(TimedModem(modem), stream, db, greeting,
                            args.record_seconds, Path(args.out_dir))
        print(f"call saved: id={call['id']} "
              f"recording={call['recording_path']}")
    finally:
        fd.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
