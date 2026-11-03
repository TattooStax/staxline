# Working on StaxLine

Rules and pointed skills for any agent (or human) developing in
this repository. The plan in `docs/` is the direction of record.

## Standing rules

- **Local-first is the product.** No cloud dependency may enter
  the runtime path: no hosted inference, no account server, no
  telemetry phone-home. If a design needs the internet for
  anything except the cellular network itself, it is wrong here.
- **Prove it at the receiving end.** A feature is done when its
  effect is read back where it lands — the call heard at both
  ends, the text arrived, the record in the database, the phone
  showing the UI. Code that merely runs is not done. (Skill:
  `verify_by_direct_read`.)
- **Held drafts by default.** Customer-facing sends follow the
  owner's standing rules: scripted routine replies may send,
  everything else waits for staff approval. Never promise a
  price; the booking link is the availability answer.
- **Human-first phone.** AI pickup is an owner setting, off by
  default. A human can always take over a call.
- **One database.** All state lives in `staxline.db` (SQLite).
  No side stores, no competing schemas.
- **Sleep is a feature area.** Any change to the modem, model,
  or launcher must state its behavior when the host is asleep
  and when it wakes. See `docs/POWER-AND-WAKE.md`.
- **File-size ratchet.** Files may shrink freely; growth past the
  recorded baseline fails CI unless the baseline is deliberately
  updated in the same change with a stated reason. Hard cap
  1,000 lines. See `.file-size-ratchet.json` and
  `scripts/check-file-size-ratchet.sh`.
- **Comments explain WHY, in the present tense.** No provenance
  labels, ticket archaeology, or history in comments — that
  lives in git.

## Pointed skills

These are the playbooks this project runs under (owner's custom
skill library; ask the owner for the current text if you don't
have them):

- `verify_by_direct_read` — evidence discipline for every claim
  of done (see above).
- `owner_delegated_execution` — execute delegated work in the
  stated order with baked-in fallbacks; reserve only
  account-holder steps and genuine reordering decisions for the
  owner.
- `frontend_design`, `ui_ux_pro_max`, and the `better_*` review
  suite (accessibility, layout, typography, color, writing) —
  for UI work, against the real screens, not mockups. The UI
  must stay inside the design law in `docs/PLAN.md`: card
  surface, icon-only bottom tabs (Messages, Phone, Contacts,
  Calendar), side card for Soul/agent/memory/settings, ivory /
  charcoal / oxblood, one primary action per screen.
- `local_tattoo_design` — only for the tattoo-studio pilot
  content, not for general product code.
