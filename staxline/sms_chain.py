"""The M1 SMS chain (docs/PLAN.md): modem -> records -> held
draft -> approval -> send, with the delivery state at every
step read back from the modem rather than assumed.

Two honesty rules shaped this module, both earned on the
2026-11-03 live session:

- The modem's SMS store holds our own sent messages alongside
  received ones, so ingest takes only `received` state — an
  inbox that files our own replies as customer messages is
  lying by layout.
- A send is recorded with the state the modem reports after
  the send (sent / failed / still sending), never with the
  state the sender intended.

Drafts are held by default (repo law): the agent proposes,
a human approves, only then does anything leave the modem.
"""
from . import db as dbmod

# Carrier/service traffic shares the modem's SMS store with
# customer texts (GAPS #9b, live evidence 2026-11-03): visual-
# voicemail sync arrives from shortcode 127 with a //VVM:
# prefix, provisioning notices come from shortcodes like 6700.
# These are filed as service records — the VVM sync is real
# signal (a voicemail exists) — but they are not customer
# conversations and never surface as one.
SERVICE_NUMBERS = {"127", "6700"}
SERVICE_PREFIXES = ("//VVM:",)


def classify_sms(number, text):
    """'carrier' for carrier/service traffic, else 'customer'.
    Conservative by design: anything unrecognized is a customer
    message, because hiding a real customer is the worse error."""
    if number in SERVICE_NUMBERS:
        return "carrier"
    if text and text.startswith(SERVICE_PREFIXES):
        return "carrier"
    return "customer"


def ingest_sms(modem, db, scope="shop"):
    """Take every not-yet-recorded received SMS off the modem:
    customer messages into contacts / conversations / messages,
    carrier traffic into service records. Idempotent: re-running
    ingests nothing twice. Returns the new customer messages as
    dicts (number, text, modem_ref)."""
    fresh = []
    service = 0
    staff = 0
    for path in modem.list_sms():
        if dbmod.message_seen(db, path):
            continue
        msg = modem.read_sms(path)
        if msg.get("state") != "received":
            continue  # our own sends live in the same store
        if not msg.get("number"):
            continue
        if classify_sms(msg["number"], msg.get("text")) == "carrier":
            dbmod.add_service_sms(db, msg["number"],
                                  msg.get("text"), path)
            service += 1
            continue
        if dbmod.staff_for(db, msg["number"]) is not None:
            # A registered staff number is an instruction
            # channel, never a customer thread: the sender's
            # identity decides before a word is read.
            dbmod.add_staff_inbox(db, msg["number"],
                                  msg.get("text"))
            staff += 1
            continue
        contact_id = dbmod.upsert_contact(db, msg["number"],
                                          scope=scope)
        conv_id = dbmod.get_or_create_conversation(db, contact_id,
                                                   scope=scope)
        dbmod.add_message(db, conv_id, "in", msg.get("text"),
                          "received", modem_ref=path)
        fresh.append({"number": msg["number"],
                      "text": msg.get("text"), "modem_ref": path})
    if fresh or service or staff:
        dbmod.log_activity(
            db, "sms",
            f"Ingested {len(fresh)} new message(s), filed "
            f"{service} carrier/service record(s) and routed "
            f"{staff} staff instruction(s) from the modem.")
    return fresh


def hold_draft(modem, db, number, body, context_pack=None,
               scope="shop"):
    """File an agent-proposed reply as a held draft. Nothing is
    sent; the draft waits for staff approval in the UI. The
    context pack travels with the draft so the approver sees
    what the agent was thinking with."""
    contact_id = dbmod.upsert_contact(db, number, scope=scope)
    conv_id = dbmod.get_or_create_conversation(db, contact_id,
                                               scope=scope)
    return dbmod.add_draft(db, conv_id, body,
                           context_pack=context_pack)


def approve_and_send(modem, db, draft_id):
    """The approval gate, in code: a held draft is sent only
    through here. Sends via the modem, records the outgoing
    message with the modem's read-back state, and settles the
    draft (sent / failed) to match. Returns the read-back
    state."""
    row = db.execute(
        "SELECT d.body, d.state, c.number FROM drafts d "
        "JOIN conversations v ON v.id = d.conversation_id "
        "JOIN contacts c ON c.id = v.contact_id WHERE d.id = ?",
        (draft_id,)).fetchone()
    if row is None:
        raise ValueError(f"no draft {draft_id}")
    body, state, number = row
    if state != "held":
        raise ValueError(f"draft {draft_id} is {state}, not held")
    if dbmod.sending_frozen(db):
        raise ValueError("lockdown is on: customer sending is "
                         "frozen until an admin texts RESUME")
    readback = modem.send_sms(number, body)
    conv_id = db.execute(
        "SELECT conversation_id FROM drafts WHERE id = ?",
        (draft_id,)).fetchone()[0]
    dbmod.add_message(db, conv_id, "out", body,
                      readback or "unknown")
    dbmod.set_draft_state(db, draft_id,
                          "sent" if readback == "sent" else "failed")
    dbmod.log_activity(
        db, "sms",
        f"Draft {draft_id} approved and sent to {number}: "
        f"modem reports {readback}.")
    return readback
