#!/bin/sh
# File-size ratchet check. See docs/FILE-SIZE-RATCHET.md.
# Usage: scripts/check-file-size-ratchet.sh [--update]
exec python3 "$(dirname "$0")/check-file-size-ratchet.py" "$@"
