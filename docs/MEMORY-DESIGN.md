# StaxLine — Memory design

One SQLite database (`staxline.db`, WAL mode) holds everything:
records the shop works with, and the plain-language memories the
agent thinks with. No second database, no vector store, no cloud
sync. If a fact isn't in this file, the system doesn't know it.

## Records (the working data)

- `contacts` — people: name, number(s), notes, first/last contact.
- `conversations` / `messages` — every SMS thread, with honest
  delivery state per message (queued, sent, failed, received).
- `calls` — every call: direction, duration, answered by
  (human/agent/missed), recording reference, transcript.
- `appointments` — the one authoritative local calendar behind
  the Calendar tab.
- `drafts` — held agent replies awaiting staff approval, with
  the context the agent used.
- `activity` — the audit trail: what the agent did, what the
  system did (wakes, sleeps, self-checks), what staff approved.
  Activity is append-only.

## Memories (what the agent believes)

A memory is one plain-language statement about a contact, the
shop, or how the shop works — e.g. "Maria prefers Saturday
mornings", "First-time clients are asked for a reference photo".

Each memory row carries:

- `subject` — contact id, `shop`, or `policy`.
- `text` — the statement, in plain words, readable by staff.
- `source_kind` / `source_ref` — where it came from: a message,
  a call transcript, a staff statement, a calendar booking.
  A memory with no source does not get created.
- `review_state` — `draft` (agent-proposed, not yet trusted),
  `approved` (staff confirmed), or `disabled`.
- `supersedes` — corrections create a new memory that supersedes
  the old one. The old row stays in history but is never used.
- Timestamps and who created it (agent or which staff member).

Rules:

- The agent may propose memories freely; it acts on `draft`
  memories only for low-stakes context, and staff review them in
  the side card's Memory view (approve / correct / forget).
- **Forgetting is real:** forgetting a memory hard-deletes it and
  adds a tombstone (a hash of the statement) so the agent does
  not silently re-learn the same claim from old transcripts.
- Staff can read every memory the agent holds. There is no hidden
  state — if the agent believes it, it's on this screen.

## Retrieval (what the agent sees, and when)

At each decision point (incoming SMS, ringing call, draft
generation) the model worker builds a **context pack**:

1. Shop identity + Soul/behavior settings (small, always in).
2. The contact's record and `approved` memories about them.
3. Recent conversation/call history with that contact.
4. FTS5 full-text matches from memories and messages for the
   current message's terms.
5. Today's calendar, when the conversation is about booking.

Ranked: approved before draft, recent before old, exact contact
before shop-wide. The pack is token-budgeted oldest-first out,
and the pack used for any sent/held draft is saved with the draft
— so a human approving it can see *why* the agent wrote that.

## What memory is not

- Not a transcript dump: transcripts are records; memories are
  the distilled claims staff can correct.
- Not shared between shops: each install is one shop's world.
- Not synced anywhere. Backup = the database file itself,
  snapshotted to the unit's flash by the launcher.
