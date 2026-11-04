#!/usr/bin/env python3
"""The drafter pass, runnable by hand (the launcher will run
it on a loop with the modem worker):

    python3 scripts/run_drafter.py --db staxline.db \
        --model-url http://127.0.0.1:8080

For every conversation waiting on a reply, the local model
drafts one and files it HELD, with its context pack saved.
Nothing is sent — approval is a separate, human act.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from staxline import db as dbmod  # noqa: E402
from staxline.context_pack import fargo_tattoo_shop  # noqa: E402
from staxline.drafting import draft_all_pending  # noqa: E402
from staxline.model import LlamaCppClient  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="staxline.db")
    ap.add_argument("--model-url", default="http://127.0.0.1:8080")
    args = ap.parse_args()
    db = dbmod.connect(args.db)
    model = LlamaCppClient(args.model_url)
    ids = draft_all_pending(db, model, fargo_tattoo_shop())
    print(f"held drafts filed: {ids}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
