"""Staff by text (SMS-first pilot): identity by registration —
a staff text never becomes a customer thread; the router's
role checks hold; approval by reply sends the exact alerted
text and settles on the modem's read-back; lockdown freezes
customer sends while staff replies keep flowing; REMEMBER
files an approved memory sourced to the staff statement.
"""
import tempfile
import unittest
from pathlib import Path

from staxline import db as dbmod
from staxline.sms_chain import (approve_and_send, hold_draft,
                                ingest_sms)
from staxline.staff import (alert_admins, draft_alert,
                            handle_staff_text, process_staff_inbox)

ADMIN = "+17018317231"
HELPER = "+17015550199"
CUSTOMER = "+17015550123"


class StaffModem:
    def __init__(self, store=None, send_state="sent"):
        self.store = store or {}
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
    db = dbmod.connect(Path(td) / "staff.db")
    dbmod.register_staff(db, ADMIN, "admin", pin="1234")
    dbmod.register_staff(db, HELPER, "staff")
    return db


class RoutingTests(unittest.TestCase):
    def test_staff_text_never_becomes_a_customer_thread(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            store = {"/SMS/1": {"number": ADMIN, "text": "STATUS",
                                "state": "received"},
                     "/SMS/2": {"number": CUSTOMER, "text": "Hi!",
                                "state": "received"}}
            fresh = ingest_sms(StaffModem(store), db)
            self.assertEqual([m["number"] for m in fresh],
                             [CUSTOMER])
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM staff_inbox"
                           ).fetchone()[0], 1)
            self.assertEqual(
                db.execute("SELECT COUNT(*) FROM conversations"
                           ).fetchone()[0], 1)

    def test_status_answers_and_inbox_drains(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = StaffModem({"/SMS/1": {
                "number": ADMIN, "text": "STATUS",
                "state": "received"}})
            ingest_sms(modem, db)
            self.assertEqual(process_staff_inbox(db, modem), 1)
            self.assertEqual(
                db.execute("SELECT handled FROM staff_inbox"
                           ).fetchone()[0], 1)
            self.assertTrue(any(
                "status" in t.lower() for _, t in modem.sent))


class ApprovalTests(unittest.TestCase):
    def test_ok_sends_the_alerted_text(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = StaffModem()
            draft_id = hold_draft(modem, db, CUSTOMER,
                                  "We can do Tuesday.")
            alert = draft_alert(db, draft_id)
            self.assertIn("We can do Tuesday.", alert)
            handle_staff_text(db, modem, ADMIN, "OK")
            self.assertIn((CUSTOMER, "We can do Tuesday."),
                          modem.sent)
            self.assertEqual(
                db.execute("SELECT state FROM drafts WHERE id = ?",
                           (draft_id,)).fetchone()[0], "sent")

    def test_staff_role_cannot_approve(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = StaffModem()
            draft_id = hold_draft(modem, db, CUSTOMER, "Draft.")
            reply = handle_staff_text(db, modem, HELPER, "OK")
            self.assertIn("lead or admin", reply)
            self.assertEqual(
                db.execute("SELECT state FROM drafts WHERE id = ?",
                           (draft_id,)).fetchone()[0], "held")
            self.assertNotIn((CUSTOMER, "Draft."), modem.sent)


class LockdownTests(unittest.TestCase):
    def test_lockdown_freezes_customers_not_staff(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = StaffModem()
            draft_id = hold_draft(modem, db, CUSTOMER, "Words.")
            handle_staff_text(db, modem, ADMIN, "LOCKDOWN")
            with self.assertRaises(ValueError):
                approve_and_send(modem, db, draft_id)
            # Staff replies still flow during the freeze.
            reply = handle_staff_text(db, modem, ADMIN, "STATUS")
            self.assertIn("lockdown ON", reply)
            # Plain RESUME is refused while a PIN is set.
            reply = handle_staff_text(db, modem, ADMIN, "RESUME")
            self.assertIn("PIN", reply)
            self.assertTrue(dbmod.sending_frozen(db))
            handle_staff_text(db, modem, ADMIN, "RESUME 1234")
            self.assertFalse(dbmod.sending_frozen(db))
            self.assertEqual(
                approve_and_send(modem, db, draft_id), "sent")


class MemoryAndAlertTests(unittest.TestCase):
    def test_remember_files_an_approved_staff_memory(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = StaffModem()
            handle_staff_text(db, modem, ADMIN,
                              "REMEMBER: We close early Fridays "
                              "in December")
            row = db.execute(
                "SELECT text, source_kind, review_state FROM "
                "memories").fetchone()
            self.assertEqual(row[0],
                             "We close early Fridays in December")
            self.assertEqual(row[1], "staff statement")
            self.assertEqual(row[2], "approved")

    def test_alert_admins_reaches_admins_only(self):
        with tempfile.TemporaryDirectory() as td:
            db = fresh_db(td)
            modem = StaffModem()
            self.assertEqual(alert_admins(db, modem, "Heads up"), 1)
            self.assertEqual(modem.sent, [(ADMIN, "Heads up")])


if __name__ == "__main__":
    unittest.main()
