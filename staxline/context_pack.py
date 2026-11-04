"""Context packs: what the model is shown when it drafts.

The shape follows docs/MEMORY-DESIGN.md, and one rule of
phrasing follows the LFM3 separation test (2026-10-31): a pack
that lists facts plus a prohibition and leaves the chain to
inference gets the inference wrong — the same model answered
correctly once the packet BOUND each fact to its consequence.
So rules here are written as bindings ("a walk-in question is
Leni's work at Leni's rates"), never as facts floating near a
warning.
"""
from . import db as dbmod

SYSTEM = (
    "You are the messaging assistant for a small shop, drafting "
    "a reply for a staff member to approve. Write only the reply "
    "text: plain, friendly, short — a text message, not an "
    "email. No greeting signature, no placeholders. Follow every "
    "rule in the pack exactly; where a rule binds a fact to an "
    "action, do the action."
)


def build_pack(db, conversation_id, shop):
    """Assemble the pack for drafting the next reply in a
    conversation. `shop` is a dict: name, rules (list of bound
    rule strings), booking_link. Memories: approved pack in as
    facts; draft-state memories about this contact pack in too
    (a held draft gets human eyes before sending — design law),
    labeled unconfirmed so the draft can hedge on them."""
    head = db.execute(
        "SELECT c.id, c.name, c.number, v.scope FROM "
        "conversations v JOIN contacts c ON c.id = v.contact_id "
        "WHERE v.id = ?", (conversation_id,)).fetchone()
    if head is None:
        raise ValueError(f"no conversation {conversation_id}")
    contact_id, name, number, scope = head
    memories = dbmod.memories_for(
        db, str(contact_id), scope=scope,
        states=("approved", "draft"))
    msgs = db.execute(
        "SELECT direction, body FROM messages "
        "WHERE conversation_id = ? ORDER BY id DESC LIMIT 12",
        (conversation_id,)).fetchall()[::-1]

    lines = [f"SHOP: {shop['name']}", "", "RULES (binding):"]
    for i, rule in enumerate(shop["rules"], 1):
        lines.append(f"{i}. {rule}")
    if shop.get("booking_link"):
        lines.append(f"Booking link: {shop['booking_link']}")
    lines += ["", f"CUSTOMER: {name or number} ({number})"]
    if memories:
        lines.append("WHAT THE SHOP KNOWS ABOUT THIS CUSTOMER:")
        for m in memories:
            tag = ("confirmed" if m["review_state"] == "approved"
                   else "unconfirmed — hedge or ask, do not assert")
            lines.append(f"- ({tag}) {m['text']}")
    lines += ["", "CONVERSATION SO FAR:"]
    for direction, body in msgs:
        who = "Customer" if direction == "in" else "Shop"
        lines.append(f"{who}: {body}")
    lines += ["", "TASK: Write the shop's next reply to the "
                  "customer's last message."]
    return "\n".join(lines)


def fargo_tattoo_shop():
    """The pilot shop's seed facts, as bound rules (pilot
    content — the installer writes a shop's own rules into its
    settings; these are Fargo Tattoo's, from the owner's
    approved studio knowledge and his 2026-11-03 decisions)."""
    return {
        "name": "Fargo Tattoo (private studio, Fargo ND)",
        "booking_link":
            "https://squareup.com/appointments/book/"
            "L7VAHB1TPFGN2/start",
        "rules": [
            "PRICE — SHAWN: never state a definite price. The "
            "published rate is $120/hour. Any figure must be "
            "framed as an estimate, with the reason: the final "
            "price depends on size, placement, and detail.",
            "PRICE — LENI: never quote any price or rate for "
            "Leni's work. Leni sets her own rates; if a price "
            "for her work is asked, say Leni will confirm her "
            "pricing herself.",
            "AVAILABILITY: never say a day or time is open, "
            "booked, or full. If the customer asks about booking "
            "or availability, the reply gives the booking link "
            "— on availability, the link is the entire answer.",
            "WALK-INS: walk-ins run every OTHER Saturday "
            "starting Saturday Nov 7, noon–7pm, for smaller "
            "pieces (under about 45 minutes), first come first "
            "served, and Leni works them — so a walk-in question "
            "is Leni's work at Leni's rates, which you must not "
            "quote (rule 2).",
            "ARTIST FIT: fine line, black & grey, realism, and "
            "minimalist work is Shawn. Bold color and "
            "neo-traditional work is Leni. If the style is "
            "unclear, ask what style they are picturing before "
            "routing.",
            "CONSULTS: a consultation costs $40.",
            "IDENTITY: you are the studio assistant, not Shawn "
            "and not Leni. Never claim to be either artist.",
        ],
    }
