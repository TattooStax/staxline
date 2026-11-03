#!/usr/bin/env python3
"""File-size ratchet for inkPilot.

Compares every tracked text file's line count against the baseline
in .file-size-ratchet.json at the repository root.

- A file at or below its baseline passes.
- A file above its baseline fails, unless the baseline was updated
  in the same change (run with --update to do that deliberately).
- A file not yet in the baseline is reported as new and passes;
  --update records it.
- No file may exceed the hard cap (default 1,000 lines) unless it
  is recorded in the baseline's exceptions. Files listed as
  legacy_over_cap may only shrink, never grow.

Exit code 0 = ratchet holds, 1 = violation.
"""
import json
import subprocess
import sys
from pathlib import Path

BASELINE_NAME = ".file-size-ratchet.json"
DEFAULT_CAP = 1000


def tracked_files(root):
    out = subprocess.run(
        ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line.strip()]


def line_count(path):
    """Return line count for a text file, or None for binary/missing."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:
        return None
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def load_baseline(path):
    if path.exists():
        return json.loads(path.read_text())
    return {"version": 1, "cap_lines": DEFAULT_CAP, "files": {}, "exceptions": {}}


def main():
    update = "--update" in sys.argv[1:]
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    )
    baseline_path = root / BASELINE_NAME
    baseline = load_baseline(baseline_path)
    cap = int(baseline.get("cap_lines", DEFAULT_CAP))
    base_files = baseline.get("files", {})
    exceptions = baseline.get("exceptions", {})

    current = {}
    binaries = []
    for rel in tracked_files(root):
        if rel == BASELINE_NAME:
            continue  # the baseline cannot ratchet itself
        count = line_count(root / rel)
        if count is None:
            binaries.append(rel)
        else:
            current[rel] = count

    failures = []
    news = []
    for rel, count in sorted(current.items()):
        base = base_files.get(rel)
        if base is None:
            news.append(rel)
            base = count  # a new file cannot violate its own first size
        if count > base:
            failures.append(
                f"GREW: {rel}: {base} -> {count} lines "
                f"(run --update and justify, or split the file)"
            )
        legacy = exceptions.get(rel, {}).get("kind") == "legacy_over_cap"
        if count > cap and rel not in exceptions:
            failures.append(
                f"OVER CAP: {rel}: {count} lines > cap {cap} "
                f"(split it, or record an explicit exception)"
            )
        if legacy and count > int(exceptions[rel]["lines"]):
            failures.append(
                f"LEGACY OVER-CAP GREW: {rel}: "
                f"{exceptions[rel]['lines']} -> {count} lines (may only shrink)"
            )

    if update:
        new_exceptions = {}
        for rel, count in sorted(current.items()):
            if count > cap:
                kind = (
                    exceptions.get(rel, {}).get("kind")
                    if rel in exceptions
                    else "over_cap"
                )
                new_exceptions[rel] = {"lines": count, "kind": kind or "over_cap"}
        data = {
            "version": 1,
            "cap_lines": cap,
            "note": (
                "Baseline for the inkPilot file-size ratchet. Files may shrink "
                "freely; growth past these counts fails CI unless this file is "
                "deliberately updated in the same change with a stated reason. "
                "See docs/FILE-SIZE-RATCHET.md."
            ),
            "files": {rel: current[rel] for rel in sorted(current)},
            "binary_files": sorted(binaries),
            "exceptions": new_exceptions,
        }
        baseline_path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"Baseline updated: {len(current)} text files, "
              f"{len(binaries)} binary files, {len(new_exceptions)} over-cap exceptions.")
        return 0

    for rel in news:
        print(f"NEW (not yet in baseline): {rel}: {current[rel]} lines")
    if failures:
        print("File-size ratchet FAILED:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    print(f"File-size ratchet OK: {len(current)} text files at or below baseline, "
          f"cap {cap} lines.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
