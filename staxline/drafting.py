"""Drafting: the model turns a new customer message into a
HELD draft (docs/PLAN.md milestone M1 — SMS in, contact,
memory, held draft, approval, send). Drafting never sends
anything; the approval gate in sms_chain is the only way a
draft leaves the shop. The pack used is saved with the draft,
so the human approving it sees what the model saw.
"""
from . import db as dbmod
from .context_pack import SYSTEM, build_pack
from .model import strip_think


def conversations_needing_drafts(db):
    """Conversations whose last message is inbound and which
    have no held draft waiting — the drafter's work queue."""
    rows = db.execute(
        "SELECT v.id FROM conversations v "
        "WHERE (SELECT m.direction FROM messages m "
        "       WHERE m.conversation_id = v.id "
        "       ORDER BY m.id DESC LIMIT 1) = 'in' "
        "AND NOT EXISTS (SELECT 1 FROM drafts d "
        "       WHERE d.conversation_id = v.id "
        "       AND d.state = 'held')").fetchall()
    return [r[0] for r in rows]


def draft_reply(db, model, conversation_id, shop):
    """Draft one reply and file it held. Returns the draft id,
    or None when the conversation is not waiting on a reply or
    the model produced nothing usable."""
    if conversation_id not in conversations_needing_drafts(db):
        return None
    pack = build_pack(db, conversation_id, shop)
    result = model.complete(SYSTEM, pack)
    # The strip lives here, at the drafting boundary, not only
    # in one client: any backend's output passes this point
    # before it can become a customer-facing draft.
    text = strip_think(result.get("text") or "")
    if not text:
        dbmod.log_activity(
            db, "draft",
            f"Model returned an empty draft for conversation "
            f"{conversation_id}; nothing filed.")
        return None
    draft_id = dbmod.add_draft(db, conversation_id, text,
                               context_pack=pack)
    dbmod.log_activity(
        db, "draft",
        f"Draft {draft_id} held for conversation "
        f"{conversation_id} (model latency "
        f"{result.get('latency_s', 0):.1f}s, "
        f"{result.get('completion_tokens')} tokens out).")
    return draft_id


def draft_all_pending(db, model, shop):
    """One drafter pass. Returns the new draft ids."""
    return [d for d in (draft_reply(db, model, cid, shop)
                        for cid in conversations_needing_drafts(db))
            if d is not None]
