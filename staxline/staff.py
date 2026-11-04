"""Staff by text: the SMS-first pilot (docs/REMOTE-ACCESS.md).

The registered admin pilots the whole system from the text
line — updates go out, commands come back, and no screen or
open port stands between the human and the agent. Every rule
here is deterministic code: the router checks the sender's
role against the command before anything acts, and the model
is never asked who may do what.

Proof scales with stakes, per the design: reads ride on the
number alone; an approval is bound to content (the alert shows
the exact draft text, and OK sends that text, nothing else);
sensitive commands (RESUME) take the admin role and the PIN
when one is set. Staff replies are operational traffic and are
never blocked by lockdown — lockdown freezes customer sends,
and a freeze the admin cannot lift by text would be a trap.
"""
import hashlib

from . import db as dbmod
from .sms_chain import approve_and_send

HELP = ("Commands: STATUS · DRAFTS · OK [n] · LOCKDOWN · "
        "RESUME [pin] · REMEMBER: <fact> · anything else is "
        "filed as a note.")


def _reply(db, modem, number, text):
    state = modem.send_sms(number, text)
    dbmod.log_activity(db, "staff",
                       f"Staff reply to {number}: {state}.")
    return text


def _status(db):
    held = db.execute(
        "SELECT COUNT(*) FROM drafts WHERE state = 'held'"
    ).fetchone()[0]
    convs = db.execute(
        "SELECT COUNT(*) FROM conversations").fetchone()[0]
    frozen = "ON" if dbmod.sending_frozen(db) else "off"
    return (f"StaxLine status: {held} draft(s) held, "
            f"{convs} conversation(s), lockdown {frozen}.")


def _drafts_list(db):
    rows = db.execute(
        "SELECT d.id, c.number, d.body FROM drafts d "
        "JOIN conversations v ON v.id = d.conversation_id "
        "JOIN contacts c ON c.id = v.contact_id "
        "WHERE d.state = 'held' ORDER BY d.id").fetchall()
    if not rows:
        return "No drafts held."
    lines = ["Held drafts:"]
    for did, number, body in rows[:5]:
        lines.append(f"#{did} to {number}: {body[:90]}")
    lines.append("Reply OK to send the oldest, or OK <n>.")
    return "\n".join(lines)


def _approve(db, modem, number, staff, arg):
    if staff["role"] not in ("lead", "admin"):
        return ("Approvals need a lead or admin number. "
                "Your note was filed.")
    if arg:
        try:
            draft_id = int(arg.lstrip("#"))
        except ValueError:
            return f"No draft called '{arg}'. " + _drafts_list(db)
    else:
        row = db.execute(
            "SELECT id FROM drafts WHERE state = 'held' "
            "ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return "No drafts held."
        draft_id = row[0]
    try:
        state = approve_and_send(modem, db, draft_id)
    except ValueError as e:
        return f"Draft {draft_id} not sent: {e}"
    return f"Draft {draft_id} sent (modem: {state})."


def _resume(db, staff, arg):
    if staff["role"] != "admin":
        return "RESUME is admin-only."
    if staff["pin_hash"]:
        given = (hashlib.sha256(arg.encode()).hexdigest()
                 if arg else "")
        if given != staff["pin_hash"]:
            return "RESUME needs your PIN: RESUME <pin>."
    dbmod.set_kv(db, "lockdown", "0")
    dbmod.log_activity(db, "staff", "Lockdown lifted by admin.")
    return "Lockdown lifted. Sending is live."


def handle_staff_text(db, modem, number, text):
    """Route one staff text and answer it. Returns the reply
    text (also sent). Customer numbers never reach this
    function — ingest routes by registration, not by content."""
    staff = dbmod.staff_for(db, number)
    if staff is None:
        return None
    body = (text or "").strip()
    upper = body.upper()
    dbmod.log_activity(
        db, "staff", f"Staff instruction from {number} "
        f"({staff['role']}): {body[:80]}")

    if upper == "STATUS":
        reply = _status(db)
    elif upper == "DRAFTS":
        reply = _drafts_list(db)
    elif upper == "OK" or upper.startswith("OK "):
        reply = _approve(db, modem, number, staff,
                         body[2:].strip())
    elif upper == "LOCKDOWN":
        if staff["role"] in ("lead", "admin"):
            dbmod.set_kv(db, "lockdown", "1")
            dbmod.log_activity(db, "staff",
                               "Lockdown set: customer sending "
                               "frozen.")
            reply = ("Lockdown on. No customer messages will "
                     "send until an admin texts RESUME.")
        else:
            reply = "LOCKDOWN needs a lead or admin number."
    elif upper == "RESUME" or upper.startswith("RESUME "):
        reply = _resume(db, staff, body[6:].strip())
    elif upper.startswith("REMEMBER:"):
        fact = body[len("REMEMBER:"):].strip()
        if fact:
            dbmod.add_memory(
                db, "shop", fact, source_kind="staff statement",
                source_ref=number, scope=staff["scope"],
                review_state="approved", created_by=number)
            reply = "Remembered."
        else:
            reply = "REMEMBER: needs the fact after the colon."
    else:
        dbmod.log_activity(db, "staff",
                           f"Staff note from {number}: "
                           f"{body[:120]}")
        reply = "Noted. " + HELP
    return _reply(db, modem, number, reply)


def process_staff_inbox(db, modem):
    """Handle every unhandled staff instruction, in order.
    Returns how many were handled."""
    rows = db.execute(
        "SELECT id, number, text FROM staff_inbox "
        "WHERE handled = 0 ORDER BY id").fetchall()
    for row_id, number, text in rows:
        handle_staff_text(db, modem, number, text)
        db.execute("UPDATE staff_inbox SET handled = 1 "
                   "WHERE id = ?", (row_id,))
        db.commit()
    return len(rows)


def alert_admins(db, modem, text):
    """The outbound half of the text line: the system speaks
    first when something needs the admin (docs/REMOTE-ACCESS.md
    — updates go out too)."""
    sent = 0
    for number in dbmod.staff_numbers(db, role="admin"):
        modem.send_sms(number, text)
        sent += 1
    if sent:
        dbmod.log_activity(db, "staff",
                           f"Alert sent to {sent} admin(s).")
    return sent


def draft_alert(db, draft_id):
    """The alert text for a held draft. The full draft body is
    in the alert because approval is bound to content: the
    admin's OK approves exactly these words."""
    row = db.execute(
        "SELECT d.body, c.number FROM drafts d "
        "JOIN conversations v ON v.id = d.conversation_id "
        "JOIN contacts c ON c.id = v.contact_id WHERE d.id = ?",
        (draft_id,)).fetchone()
    if row is None:
        return None
    body, number = row
    return (f"New draft #{draft_id} for {number}:\n{body}\n"
            f"Reply OK to send it, DRAFTS to see all.")
