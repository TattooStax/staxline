"""The one database (docs/MEMORY-DESIGN.md).

SQLite, WAL mode. This module owns the schema and small helpers;
nothing else in the codebase writes SQL. M0a uses `calls` and
`activity`; the rest of the schema lands with its milestones.
"""
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    direction TEXT NOT NULL,
    number TEXT,
    started_at REAL NOT NULL,
    answered_at REAL,
    ended_at REAL,
    answered_by TEXT,
    rings_before_answer INTEGER,
    time_to_audio_ms INTEGER,
    recording_path TEXT,
    transcript TEXT,
    outcome TEXT
);
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    at REAL NOT NULL,
    kind TEXT NOT NULL,
    text TEXT NOT NULL
);
"""


def connect(path):
    db = sqlite3.connect(str(Path(path)))
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def log_activity(db, kind, text):
    db.execute("INSERT INTO activity (at, kind, text) VALUES (?, ?, ?)",
               (time.time(), kind, text))
    db.commit()


def record_call(db, call):
    keys = [k for k in call if k != "id"]
    cur = db.execute(
        f"INSERT INTO calls ({', '.join(keys)}) "
        f"VALUES ({', '.join('?' for _ in keys)})",
        [call[k] for k in keys])
    db.commit()
    return cur.lastrowid
