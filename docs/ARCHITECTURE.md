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

One modem worker, one call state machine — but the *transport*
under it is per-platform, because the hardware forced the issue
on first contact (live session, 2026-11-03, evidence in
`docs/evidence/2026-11-03-victus-live-test.md`):

- **Linux transport: ModemManager (D-Bus).** The actual unit's
  USB serial AT ports do not answer: after a clean reset and
  registration, both AT-labelled ports stayed silent to every
  AT form while the GPS port streamed and ModemManager/QMI
  controlled the modem fully. Serial AT is therefore not the
  Linux path on this hardware. The D-Bus path is also the one
  already proven in production by StaxCloud.
- **Windows transport: COM-port AT via SIMCom's drivers —
  UNPROVEN.** Whether the same module answers AT under the
  Windows driver composition is exactly what M0a on Windows
  exists to answer. Until it does, no Windows claim is made.
- The license tie reads the IMEI from whichever transport is
  live (ModemManager property / `AT+CGSN`).
- Calls: ring → answer → audio over the modem's USB audio
  function (16k PCM). Live status (2026-11-03, owner's modem):
  **dial-out + PCM both ways + DTMF + hangup proven** on a real
  call; **inbound answer PROVEN the same night** — not through
  ModemManager (the firmware rejects its QMI answer request,
  error 41 `InvalidQosId`, call terminating in the same
  instant), but through a **direct QMI `answer_call`** issued
  by the modem worker's own client via qmi-proxy: the owner's
  call went `ringing-in → active` (ModemManager's journal
  concurs) and held for the observation window. The Linux
  modem worker therefore speaks QMI directly for voice, with
  ModemManager retained for registration/SMS/data duties.
  One artifact to design around: with no TX audio being fed,
  the voice path starves and loops a frame (an audible ~85 Hz
  buzz, and sparse RX bursts) — the agent streams from the
  first frame in the real loop, and M0b's speaking call is
  the confirmation.
- **Voicemail is a preserved record, not a carrier black
  hole** (owner requirement 2026-11-03): the agent answering
  and recording locally is the primary path; a **carrier
  retrieval leg** — dial the voicemail number on wake and on a
  schedule, DTMF-navigate, record, transcribe, file with
  `source: carrier-voicemail` — covers the hours the unit was
  asleep or down, so a caller's message is never stranded in a
  mailbox nobody checks. Its primitives (dial, PCM, DTMF) are
  the ones already proven; the mailbox PIN is a setup-wizard
  item.
- SMS: delivery state tracked honestly — a send is "sent" when
  the carrier path confirms it, and the conversation history
  records what actually happened. Two-way SMS was proven live
  on the owner's modem 2026-11-03 (out: state read back `sent`;
  in: the owner's reply read back off the modem).
- **MMS is required** (owner directive 2026-11-03, superseding
  the director's v1 cut — client picture messages are core to
  the beachhead verticals, tattoo reference photos above all).
  Linux path: `mmsd-tng` against ModemManager, plus the part
  that is easy to miss — **the bearer's network settings must
  be applied to the host** (address, route, carrier DNS): a
  modem-level "connected" bearer does nothing for the host by
  itself. In StaxCloud production this is the `staxbox-mms`
  NetworkManager connection from the install artifacts; the
  product installer owns the equivalent. First live evidence:
  an MMS notification reached the daemon the moment the owner
  sent a picture; retrieval only became possible after the
  cellular interface was configured by hand and the carrier's
  MMSC name resolved through the bearer's own DNS64.
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
- **The voice model is resident before the line is armed.** It
  loads at system start, not at first ring — a cold load inside
  the answer path would blow the ring window. The model survives
  S3 sleep in RAM; if a resume ever finds it gone, the line
  reports an honest "warming up" state and missed calls
  reconcile per `docs/POWER-AND-WAKE.md`, Layer 4.
- All inference is local. The only network the system needs is
  the cellular network itself.

## The budget table (filled by measurement, not adjectives)

"Lightweight" is banned as a claim until these four numbers
exist for the weakest reference machine, and they are re-recorded
at every milestone (see `docs/PLAN.md`, standing rules):

| Measure | Value |
|---|---|
| Installed size (app + models) | _unmeasured_ |
| Cold start to ready | _unmeasured_ |
| Resident RAM, voice model loaded | _unmeasured_ |
| Per-turn voice latency (Tier 1 / Tier 2) | _unmeasured_ |

## Data

One SQLite file (WAL mode), schema in `docs/MEMORY-DESIGN.md`.
Backups: the launcher snapshots the DB (and settings) to the
unit's flash on a schedule — the unit doubles as the backup
target — and offers one-click export. If the host dies, a new
host + the same unit restores the shop.
