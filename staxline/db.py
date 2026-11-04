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
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    name TEXT,
    number TEXT NOT NULL UNIQUE,
    notes TEXT,
    scope TEXT NOT NULL DEFAULT 'shop',
    first_contact_at REAL,
    last_contact_at REAL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    scope TEXT NOT NULL DEFAULT 'shop',
    created_at REAL NOT NULL,
    last_message_at REAL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL
        REFERENCES conversations(id),
    direction TEXT NOT NULL,
    body TEXT,
    state TEXT NOT NULL,
    modem_ref TEXT UNIQUE,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS service_sms (
    id INTEGER PRIMARY KEY,
    number TEXT,
    body TEXT,
    modem_ref TEXT UNIQUE,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    conversation_id INTEGER NOT NULL
        REFERENCES conversations(id),
    body TEXT NOT NULL,
    context_pack TEXT,
    state TEXT NOT NULL DEFAULT 'held',
    created_at REAL NOT NULL
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


def upsert_contact(db, number, scope="shop"):
    """One contact per number; first sight stamps first contact,
    every sight refreshes last contact. Returns the contact id."""
    now = time.time()
    row = db.execute("SELECT id FROM contacts WHERE number = ?",
                     (number,)).fetchone()
    if row:
        db.execute("UPDATE contacts SET last_contact_at = ? "
                   "WHERE id = ?", (now, row[0]))
        db.commit()
        return row[0]
    cur = db.execute(
        "INSERT INTO contacts (number, scope, first_contact_at, "
        "last_contact_at) VALUES (?, ?, ?, ?)",
        (number, scope, now, now))
    db.commit()
    return cur.lastrowid


def get_or_create_conversation(db, contact_id, scope="shop"):
    row = db.execute(
        "SELECT id FROM conversations WHERE contact_id = ? "
        "AND scope = ?", (contact_id, scope)).fetchone()
    if row:
        return row[0]
    cur = db.execute(
        "INSERT INTO conversations (contact_id, scope, created_at) "
        "VALUES (?, ?, ?)", (contact_id, scope, time.time()))
    db.commit()
    return cur.lastrowid


def add_message(db, conversation_id, direction, body, state,
                modem_ref=None):
    now = time.time()
    cur = db.execute(
        "INSERT INTO messages (conversation_id, direction, body, "
        "state, modem_ref, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (conversation_id, direction, body, state, modem_ref, now))
    db.execute("UPDATE conversations SET last_message_at = ? "
               "WHERE id = ?", (now, conversation_id))
    db.commit()
    return cur.lastrowid


def message_seen(db, modem_ref):
    """Dedupe by the modem-side reference: the modem keeps its
    own copy of every SMS, and ingest must never double-record
    what a previous pass already took in. Service messages
    count as seen too — they are filed, just not as customer
    conversations."""
    if db.execute("SELECT 1 FROM messages WHERE modem_ref = ?",
                  (modem_ref,)).fetchone() is not None:
        return True
    return db.execute("SELECT 1 FROM service_sms "
                      "WHERE modem_ref = ?",
                      (modem_ref,)).fetchone() is not None


def add_service_sms(db, number, body, modem_ref):
    cur = db.execute(
        "INSERT INTO service_sms (number, body, modem_ref, "
        "created_at) VALUES (?, ?, ?, ?)",
        (number, body, modem_ref, time.time()))
    db.commit()
    return cur.lastrowid


def add_draft(db, conversation_id, body, context_pack=None):
    cur = db.execute(
        "INSERT INTO drafts (conversation_id, body, context_pack, "
        "state, created_at) VALUES (?, ?, ?, 'held', ?)",
        (conversation_id, body, context_pack, time.time()))
    db.commit()
    return cur.lastrowid


def set_draft_state(db, draft_id, state):
    db.execute("UPDATE drafts SET state = ? WHERE id = ?",
               (state, draft_id))
    db.commit()
