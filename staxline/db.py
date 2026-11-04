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
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY,
    subject TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'shop',
    text TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_ref TEXT,
    review_state TEXT NOT NULL DEFAULT 'draft',
    supersedes INTEGER,
    created_by TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_tombstones (
    hash TEXT PRIMARY KEY,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS staff (
    contact_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'shop',
    pin_hash TEXT,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS staff_inbox (
    id INTEGER PRIMARY KEY,
    number TEXT NOT NULL,
    text TEXT,
    created_at REAL NOT NULL,
    handled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT
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
    # check_same_thread=False because the app server serves
    # requests on handler threads; callers serialize access
    # (server.App's lock), so sharing one connection is safe
    # by construction rather than by thread affinity.
    db = sqlite3.connect(str(Path(path)), check_same_thread=False)
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


def add_memory(db, subject, text, source_kind, source_ref=None,
               scope="shop", review_state="draft",
               created_by="agent", supersedes=None):
    """A memory is only created with a source (design law: a
    memory with no source does not get created) — the parameter
    is required, not optional."""
    cur = db.execute(
        "INSERT INTO memories (subject, scope, text, source_kind, "
        "source_ref, review_state, supersedes, created_by, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (subject, scope, text, source_kind, source_ref,
         review_state, supersedes, created_by, time.time()))
    db.commit()
    return cur.lastrowid


def memories_for(db, subject, scope="shop", states=("approved",)):
    """Memories usable for a subject: theirs plus shop-wide,
    in the given review states, newest last."""
    marks = ",".join("?" for _ in states)
    rows = db.execute(
        f"SELECT id, subject, scope, text, review_state FROM "
        f"memories WHERE review_state IN ({marks}) AND "
        f"(subject = ? OR subject = 'shop') AND "
        f"(scope = ? OR scope = 'shop') AND "
        f"id NOT IN (SELECT supersedes FROM memories "
        f"WHERE supersedes IS NOT NULL) "
        f"ORDER BY created_at",
        (*states, subject, scope)).fetchall()
    return [{"id": r[0], "subject": r[1], "scope": r[2],
             "text": r[3], "review_state": r[4]} for r in rows]


def register_staff(db, number, role, scope="shop", pin=None):
    """A person becomes staff by their number being registered
    with a role (docs/REMOTE-ACCESS.md). Identity is the number;
    the PIN, when set, gates only the sensitive commands, so it
    is stored hashed — the database is not a credential store."""
    import hashlib
    contact_id = upsert_contact(db, number, scope=scope)
    pin_hash = (hashlib.sha256(pin.encode()).hexdigest()
                if pin else None)
    db.execute(
        "INSERT INTO staff (contact_id, role, scope, pin_hash) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(contact_id) DO UPDATE "
        "SET role = excluded.role, scope = excluded.scope, "
        "pin_hash = excluded.pin_hash, active = 1",
        (contact_id, role, scope, pin_hash))
    db.commit()
    return contact_id


def staff_for(db, number):
    """The staff record for a sender number, or None — the one
    lookup that decides whether an inbound text is an
    instruction or a customer conversation."""
    row = db.execute(
        "SELECT s.role, s.scope, s.pin_hash FROM staff s "
        "JOIN contacts c ON c.id = s.contact_id "
        "WHERE c.number = ? AND s.active = 1",
        (number,)).fetchone()
    if row is None:
        return None
    return {"role": row[0], "scope": row[1], "pin_hash": row[2]}


def staff_numbers(db, role=None):
    q = ("SELECT c.number FROM staff s JOIN contacts c "
         "ON c.id = s.contact_id WHERE s.active = 1")
    args = ()
    if role:
        q += " AND s.role = ?"
        args = (role,)
    return [r[0] for r in db.execute(q, args).fetchall()]


def add_staff_inbox(db, number, text):
    cur = db.execute(
        "INSERT INTO staff_inbox (number, text, created_at) "
        "VALUES (?, ?, ?)", (number, text, time.time()))
    db.commit()
    return cur.lastrowid


def get_kv(db, key, default=None):
    row = db.execute("SELECT value FROM kv WHERE key = ?",
                     (key,)).fetchone()
    return row[0] if row else default


def set_kv(db, key, value):
    db.execute(
        "INSERT INTO kv (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value))
    db.commit()


def sending_frozen(db):
    """Lockdown is a stored flag, not a mode in someone's head:
    the send path checks it on every send, so a lockdown texted
    from a driveway holds even if the host reboots."""
    return get_kv(db, "lockdown", "0") == "1"


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
