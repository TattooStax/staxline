#!/usr/bin/env python3
"""One staff pass, runnable by hand (the launcher loops it):
ingest the modem, then handle every waiting staff instruction
and answer it by text.

    python3 scripts/run_staff.py --db staxline.db

Register the first admin before the first pass (the setup
act):  python3 scripts/run_staff.py --register +1... admin
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from staxline import db as dbmod  # noqa: E402
from staxline.qmi_modem import LinuxModem  # noqa: E402
from staxline.sms_chain import ingest_sms  # noqa: E402
from staxline.staff import process_staff_inbox  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="staxline.db")
    ap.add_argument("--register", nargs=2,
                    metavar=("NUMBER", "ROLE"),
                    help="register a staff number and exit")
    ap.add_argument("--pin", default=None)
    args = ap.parse_args()
    db = dbmod.connect(args.db)
    if args.register:
        number, role = args.register
        dbmod.register_staff(db, number, role, pin=args.pin)
        print(f"registered {number} as {role}")
        return 0
    modem = LinuxModem()
    fresh = ingest_sms(modem, db)
    handled = process_staff_inbox(db, modem)
    print(f"ingested {len(fresh)} customer message(s); "
          f"handled {handled} staff instruction(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
