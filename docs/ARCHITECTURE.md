# StaxLine — Architecture

Four layers, each replaceable, each small. The discipline: the
web layer never blocks the phone, the model never touches the
modem directly, and there is exactly one database.

## Processes (all on the customer's host)

```text
┌─ launcher (Python) ──────────────────────────────────────┐
│  starts/stops the three workers, owns the tray/status,   │
│  restarts a dead worker and logs why                     │
├──────────────────────────────────────────────────────────┤
│  app server   stdlib HTTP, serves UI + local API         │
│  modem worker pyserial AT + USB audio (calls, SMS)       │
│  model worker liquid-audio / llama.cpp (voice + text)    │
└──────────────────────────────────────────────────────────┘
        │ localhost queues/HTTP        │ one file
        └──────────────┬───────────────┴─ staxline.db (SQLite)
```

The launcher also owns the **power policy** (`docs/POWER-AND-WAKE.md`):
it applies/maintains the Shop Mode profile, runs the daily power
self-check, keeps the heartbeat that detects sleep gaps, and runs
reconcile-on-wake before anything else starts answering.

Why separate workers: a model hiccup must never drop a ringing
phone, and a modem reset must never take the UI down. The modem
worker owns the call state machine; the app server owns records;
the model worker owns inference. They exchange plain messages
(JSON lines over localhost), so any worker can be rewritten in
another language later without touching the others — this is how
the Rust StaxCloud modem behavior can be adopted piece by piece
if the AT path ever proves insufficient on Linux.

## Runtime

- Python 3.12+, embeddable distribution on Windows (ships inside
  the installer; the customer never installs Python).
- Core has **zero third-party dependencies** (stdlib `http.server`
  based) so the base install can never break on a package index,
  a version conflict, or a missing wheel.
- Optional dependencies live with their worker: `pyserial`
  (modem), `liquid-audio`/torch (voice tier), a bundled
  `llama.cpp` binary (text tier). Each worker declares its own
  requirements; the launcher degrades honestly — if the voice
  tier can't load, the UI says so and SMS/text still work.

## UI layer

- Static files in `staxline/static/`, served by the app server.
  Vanilla JS + CSS in v1: no build step, no CDN, fully offline.
- Layout: the surface is a **card**. Bottom tab bar, **icon-only**:
  Messages · Phone · Contacts · Calendar (inline SVG icons, small
  traditional tattoo set). A **side card** slides in for Soul,
  agent conversation, memory, behavior, activity, and model
  settings.
- Design tokens: warm ivory background, charcoal text/structure,
  oxblood as the single restrained accent; plain, spacious
  screens, one list/grid and one primary action per screen.
- The same static UI is what the Android shell and iOS PWA load —
  there is one UI, three wrappers (browser, Android WebView,
  iOS home-screen). See `docs/REMOTE-ACCESS.md`.
- Server-sent events (stdlib-friendly) push new calls/messages
  into open UI sessions on the LAN; no polling loops.

## Modem layer

- Enumerate the unit by USB VID/PID, open its AT port
  (pyserial), read IMEI (`AT+CGSN`) for the license tie.
- Calls: unsolicited ring indications → answer/hangup AT flow;
  voice audio through the modem's USB audio endpoint (the 16k
  PCM path verified feasible on this hardware 2026-11-01).
- SMS: PDU/text handling with delivery state tracked honestly —
  a send is "sent" when the carrier path confirms it, and the
  conversation history records what actually happened.
- SIM: explicit business-SIM selection where a host has more
  than one modem; process-death recovery must never re-send
  (outbox rows carry idempotency keys and a sent-state journal).
- Linux note: ModemManager can fight a serial owner for the
  device; the installer/launcher detects it and the docs carry
  the resolution (the StaxCloud track learned this on the Dell).

## Inference layer

- Voice tier: **LFM2-Audio-1.5B** (Liquid's `liquid-audio`)
  speech-to-speech for the call loop.
- Text tier: **LFM2-1.2B GGUF** via a bundled llama.cpp server
  for SMS drafts, tool calls, and summarization into memory.
- A capability probe at first run (RAM, CPU, load test) picks
  the tier the host can actually carry and records the result;
  the UI shows the active tier plainly. Reference floor:
  Pi 5-class performance must remain viable for the text tier.
- All inference is local. The only network the system needs is
  the cellular network itself.

## Data

One SQLite file (WAL mode), schema in `docs/MEMORY-DESIGN.md`.
Backups: the launcher snapshots the DB (and settings) to the
unit's flash on a schedule — the unit doubles as the backup
target — and offers one-click export. If the host dies, a new
host + the same unit restores the shop.
