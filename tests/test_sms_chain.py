"""The M1 SMS chain against a scripted modem and a real
database: ingest files received messages only (the modem store
also holds our own sends), ingest never double-records, drafts
are held until approved, and a sent draft records the modem's
read-back state — including when that state is failure.
"""
import tempfile
import unittest
from pathlib import Path

from staxline import db as dbmod
from staxline.qmi_modem import MmClient
from staxline.sms_chain import (approve_and_send, hold_draft,
                                ingest_sms)

STORE = {
    "/org/freedesktop/ModemManager1/SMS/15": {
        "number": "+17018317231",
        "text": "What services do you offer", "state": "received"},
    "/org/freedesktop/ModemManager1/SMS/16": {
        "number": "+17018317231",
        "text": "Our own reply filed by the modem",
        "state": "sent"},
    "/org/freedesktop/ModemManager1/SMS/17": {
        "number": "+17015550123",
        "text": "Do you have Saturday openings?",
        "state": "received"},
}


class ChainModem:
    """MmClient-shaped double over the scripted store."""

    def __init__(self, store, send_state="sent"):
        self.store = store
        self.send_state = send_state
        self.sent = []

    def list_sms(self):
        return list(self.store.keys())

    def read_sms(self, path):
        return self.store[path]

    def send_sms(self, number, text):
        self.sent.append((number, text))
        return self.send_state


def fresh_db(td):
    return dbmod.connect(Path(td) / "chain.db")


class IngestTests(unittest.TestCase):
    def test_ingest_files_received_only(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            fresh = ingest_sms(ChainModem(STORE), db)
            self.assertEqual(len(fresh), 2)
            texts = {m["text"] for m in fresh}
            self.assertIn("What services do you offer", texts)
            self.assertIn("Do you have Saturday openings?", texts)
            n = db.execute("SELECT COUNT(*) FROM contacts")
            self.assertEqual(n.fetchone()[0], 2)
            n = db.execute("SELECT COUNT(*) FROM messages "
                           "WHERE direction='in'")
            self.assertEqual(n.fetchone()[0], 2)

    def test_ingest_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = ChainModem(STORE)
            ingest_sms(modem, db)
            self.assertEqual(ingest_sms(modem, db), [])
            n = db.execute("SELECT COUNT(*) FROM messages")
            self.assertEqual(n.fetchone()[0], 2)

    def test_threads_share_one_conversation_per_contact(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            store = dict(STORE)
            store["/org/freedesktop/ModemManager1/SMS/18"] = {
                "number": "+17018317231", "text": "And prices?",
                "state": "received"}
            ingest_sms(ChainModem(store), db)
            rows = db.execute(
                "SELECT conversation_id, COUNT(*) FROM messages "
                "GROUP BY conversation_id").fetchall()
            self.assertEqual(sorted(c for _, c in rows), [1, 2])


class CarrierClassificationTests(unittest.TestCase):
    CARRIER = {
        "/org/freedesktop/ModemManager1/SMS/21": {
            "number": "127",
            "text": "//VVM:SYNC:ev=NM;id=1;c=1",
            "state": "received"},
        "/org/freedesktop/ModemManager1/SMS/22": {
            "number": "6700",
            "text": "Need help setting up data and picture "
                    "messaging? Head to u.ultra.me/androidapn",
            "state": "received"},
        "/org/freedesktop/ModemManager1/SMS/23": {
            "number": "+17018317231",
            "text": "A real customer text",
            "state": "received"},
    }

    def test_carrier_traffic_files_as_service_not_conversation(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            fresh = ingest_sms(ChainModem(self.CARRIER), db)
            self.assertEqual(len(fresh), 1)
            self.assertEqual(fresh[0]["text"],
                             "A real customer text")
            n = db.execute("SELECT COUNT(*) FROM service_sms")
            self.assertEqual(n.fetchone()[0], 2)
            n = db.execute("SELECT COUNT(*) FROM messages")
            self.assertEqual(n.fetchone()[0], 1)
            n = db.execute("SELECT COUNT(*) FROM contacts")
            self.assertEqual(n.fetchone()[0], 1)

    def test_carrier_filing_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = ChainModem(self.CARRIER)
            ingest_sms(modem, db)
            ingest_sms(modem, db)
            n = db.execute("SELECT COUNT(*) FROM service_sms")
            self.assertEqual(n.fetchone()[0], 2)


class DraftGateTests(unittest.TestCase):
    def test_draft_is_held_and_nothing_sends(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = ChainModem(STORE)
            draft_id = hold_draft(modem, db, "+17018317231",
                                  "Thanks for asking!")
            state = db.execute("SELECT state FROM drafts "
                               "WHERE id = ?",
                               (draft_id,)).fetchone()[0]
            self.assertEqual(state, "held")
            self.assertEqual(modem.sent, [])

    def test_approve_sends_and_records_readback(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = ChainModem(STORE)
            draft_id = hold_draft(modem, db, "+17018317231",
                                  "Booking link inside")
            self.assertEqual(approve_and_send(modem, db, draft_id),
                             "sent")
            self.assertEqual(modem.sent,
                             [("+17018317231", "Booking link inside")])
            row = db.execute(
                "SELECT direction, state FROM messages "
                "WHERE direction='out'").fetchone()
            self.assertEqual(row, ("out", "sent"))
            state = db.execute("SELECT state FROM drafts "
                               "WHERE id = ?",
                               (draft_id,)).fetchone()[0]
            self.assertEqual(state, "sent")

    def test_failed_readback_is_recorded_as_failed(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = ChainModem(STORE, send_state="unknown")
            draft_id = hold_draft(modem, db, "+17018317231", "Hi")
            approve_and_send(modem, db, draft_id)
            state = db.execute("SELECT state FROM drafts "
                               "WHERE id = ?",
                               (draft_id,)).fetchone()[0]
            self.assertEqual(state, "failed")
            row = db.execute(
                "SELECT state FROM messages WHERE direction='out'"
            ).fetchone()
            self.assertEqual(row[0], "unknown")

    def test_double_approval_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = ChainModem(STORE)
            draft_id = hold_draft(modem, db, "+17018317231", "Hi")
            approve_and_send(modem, db, draft_id)
            with self.assertRaises(ValueError):
                approve_and_send(modem, db, draft_id)
            self.assertEqual(len(modem.sent), 1)


if __name__ == "__main__":
    unittest.main()
