#!/usr/bin/env python3
"""M0a plumbing-proof runner (docs/PLAN.md M0a, docs/M0A-RUNBOOK.md).

Usage:
  python3 scripts/run_m0a.py --port COM5 --probe-only
  python3 scripts/run_m0a.py --port COM5 --greeting greeting.wav

Without a real greeting WAV it generates a test TONE and says so
in the evidence — a tone proves audio flows; it is not a voice
greeting and the evidence file records which was used.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from staxline import db as dbmod  # noqa: E402
from staxline.audio import NullAudio, SoundDeviceAudio, tone_wav  # noqa: E402
from staxline.modem import Modem, SerialTransport, run_m0a_call  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="AT serial port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--db", default="staxline.db")
    ap.add_argument("--out", default="m0a-evidence")
    ap.add_argument("--greeting", help="WAV to play as the greeting")
    ap.add_argument("--record-seconds", type=int, default=10)
    ap.add_argument("--probe-only", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    modem = Modem(SerialTransport(args.port, args.baud))
    info = modem.probe()
    print("PROBE:", json.dumps(info))
    if args.probe_only:
        return

    greeting = args.greeting
    greeting_kind = "recorded-voice"
    if not greeting:
        greeting = str(tone_wav(out / "greeting-tone.wav"))
        greeting_kind = "test-tone"
        print("WARNING: no --greeting given; using a test TONE.")

    try:
        audio = SoundDeviceAudio()
    except Exception as e:  # sounddevice missing: be honest
        print(f"WARNING: no real audio device layer ({e}); "
              "falling back to NullAudio — AT plumbing and files "
              "only, NO real call audio will flow.")
        audio = NullAudio()

    db = dbmod.connect(args.db)
    print("ARMED: call the modem's number now (120s window)...")
    call = run_m0a_call(modem, audio, db, greeting,
                        args.record_seconds, out)
    call["greeting_kind"] = greeting_kind
    (out / "m0a-result.json").write_text(json.dumps(call, indent=1))
    print("M0A RESULT:", json.dumps(call, indent=1))


if __name__ == "__main__":
    main()
