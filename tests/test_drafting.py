"""Drafting with a scripted model: the pack carries the bound
rules, the thread, and labeled memories; the reply lands as a
held draft with the pack saved beside it; nothing sends; a
conversation already holding a draft is not re-drafted; an
outbound-last conversation is not drafted at all.
"""
import tempfile
import unittest
from pathlib import Path

from staxline import db as dbmod
from staxline.context_pack import build_pack, fargo_tattoo_shop
from staxline.drafting import draft_all_pending
from staxline.model import FakeModelClient, strip_think


def seed(db):
    cid = dbmod.upsert_contact(db, "+17018317231")
    conv = dbmod.get_or_create_conversation(db, cid)
    dbmod.add_message(db, conv, "in",
                      "How much for a small forearm piece?",
                      "received")
    dbmod.add_memory(db, str(cid), "Prefers Saturday mornings",
                     source_kind="staff statement",
                     review_state="approved")
    dbmod.add_memory(db, str(cid), "Mentioned a cover-up once",
                     source_kind="message", review_state="draft")
    return conv


class PackTests(unittest.TestCase):
    def test_pack_binds_rules_and_labels_memories(self):
        with tempfile.TemporaryDirectory() as td:
            db = dbmod.connect(Path(td) / "d.db")
            conv = seed(db)
            pack = build_pack(db, conv, fargo_tattoo_shop())
            self.assertIn("never state a definite price", pack)
            self.assertIn("Leni will confirm her pricing", pack)
            self.assertIn("the link is the entire answer", pack)
            self.assertIn("(confirmed) Prefers Saturday", pack)
            self.assertIn("(unconfirmed", pack)
            self.assertIn("How much for a small forearm", pack)
            self.assertIn("squareup.com/appointments", pack)


class DraftingTests(unittest.TestCase):
    def test_draft_is_held_with_pack_and_model_saw_it(self):
        with tempfile.TemporaryDirectory() as td:
            db = dbmod.connect(Path(td) / "d.db")
            conv = seed(db)
            model = FakeModelClient(["Rough estimate inside."])
            ids = draft_all_pending(db, model, fargo_tattoo_shop())
            self.assertEqual(len(ids), 1)
            row = db.execute(
                "SELECT body, state, context_pack FROM drafts "
                "WHERE id = ?", (ids[0],)).fetchone()
            self.assertEqual(row[0], "Rough estimate inside.")
            self.assertEqual(row[1], "held")
            self.assertIn("RULES (binding)", row[2])
            self.assertEqual(len(model.seen), 1)
            # A second pass files nothing: the draft is waiting.
            self.assertEqual(
                draft_all_pending(db, model, fargo_tattoo_shop()),
                [])

    def test_outbound_last_conversation_is_not_drafted(self):
        with tempfile.TemporaryDirectory() as td:
            db = dbmod.connect(Path(td) / "d.db")
            cid = dbmod.upsert_contact(db, "+17015550123")
            conv = dbmod.get_or_create_conversation(db, cid)
            dbmod.add_message(db, conv, "in", "Hi", "received")
            dbmod.add_message(db, conv, "out", "Hello!", "sent")
            model = FakeModelClient(["unused"])
            self.assertEqual(
                draft_all_pending(db, model, fargo_tattoo_shop()),
                [])
            self.assertEqual(model.seen, [])

    def test_think_blocks_never_reach_a_draft(self):
        self.assertEqual(
            strip_think("<think>long reasoning</think>Real reply"),
            "Real reply")
        with tempfile.TemporaryDirectory() as td:
            db = dbmod.connect(Path(td) / "d.db")
            seed(db)
            model = FakeModelClient(
                ["<think>x</think>Clean customer words"])
            ids = draft_all_pending(db, model, fargo_tattoo_shop())
            body = db.execute("SELECT body FROM drafts WHERE id = ?",
                              (ids[0],)).fetchone()[0]
            self.assertEqual(body, "Clean customer words")


if __name__ == "__main__":
    unittest.main()
