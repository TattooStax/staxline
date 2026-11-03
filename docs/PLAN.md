# StaxLine — Plan

Direction of record. Written 2026-11-03 by Stax with an independent
director take alongside (`docs/DIRECTOR-TAKE.md`). Nothing in this
plan is implemented yet beyond the walking skeleton described in
the README.

## Product shape

- **Hardware:** one USB unit — Waveshare SIM7600G-H modem board in
  a branded printed case, built as a composite USB device: modem +
  small hub + flash (8–16 GB) carrying the signed Windows installer,
  drivers, and model files. No downloads required to set up.
- **Host:** the shop's own Windows computer (primary), Linux
  (secondary). The host runs everything; the unit is telephony +
  license + installer, not compute.
- **Price shape:** ~$300 one-time. The customer's only recurring
  cost is their own SIM plan.
- **Agent:** answers calls and talks (voice), handles SMS, drafts
  replies for staff approval (held drafts — nothing customer-facing
  sends itself outside the owner's standing rules), knows the
  shop's records and memory, all locally.
- **License tie:** the app reads the modem's IMEI and checks it
  against a signed per-unit license shipped on the unit's flash
  (Ed25519, verified offline). The board is the key (the iLok
  pattern), except the board is also the phone. If no valid board
  is present, telephony and the agent stop — the shop's records
  stay readable and exportable. A customer's data is never held
  hostage by a license check.

## Decisions already made

1. **Runtime: Python, kept lightweight.** Zero-dependency core
   (stdlib HTTP server) for the app shell and API; heavier work
   (inference, audio) runs in separate worker processes so the
   audio loop never waits on the web layer. Python is the
   installer-friendly choice on Windows (embeddable runtime, no
   system install) and the same code runs on Linux and Pi-class
   hosts. See `docs/ARCHITECTURE.md`.
2. **UI: one static web UI, everywhere.** Served by the host.
   Card-based surface in the StaxCloud/InkStax spirit; bottom tab
   bar is **icon-only** with four tabs — Messages, Phone, Contacts,
   Calendar. Soul, agent conversation, memory, behavior, activity,
   and model settings live in a **side card (drawer)**, not tabs.
   Warm ivory, charcoal, restrained oxblood; small traditional
   tattoo icons; one primary action per screen; details on tap.
   No build step in v1 (vanilla JS/CSS) — the whole UI must work
   offline from the host's disk.
3. **Remote access: no TWA, no one's cloud.** A true TWA requires
   a public domain with Digital Asset Links — that is somebody's
   infrastructure by definition. Instead: Android gets a small
   WebView-shell APK (sideloaded from the same USB installer) that
   points at the host on the shop LAN; iOS in v1 gets a Safari
   bookmark on the LAN (a local-CA installed PWA is an advanced,
   post-v1 option — the director overruled it as the primary
   path: the least technical users should not be asked to
   perform the most trust-sensitive setup step in consumer
   computing). Full reasoning in `docs/REMOTE-ACCESS.md`.
4. **Memory: one SQLite database.** Records and plain-language
   memories with sources, corrections, and review state; FTS5
   retrieval; no competing databases, no vector store in v1.
   See `docs/MEMORY-DESIGN.md`.
5. **Modem layer: AT-first, behavior borrowed.** The production
   StaxCloud modem layer is Rust over ModemManager D-Bus — Linux
   only, and Windows is the primary customer platform. StaxLine's
   modem layer speaks serial AT (cross-platform via pyserial) and
   uses the modem's USB audio device for call PCM, following the
   behavior proven on the Dell: ring/answer handling, the 16k PCM
   voice path (feasibility verified 2026-11-01), SMS/MMS handling,
   failure honesty. The StaxCloud code is the reference for *what
   correct looks like*, not a code dependency.
6. **Inference: two tiers.**
   - Voice tier: LFM2-Audio-1.5B via Liquid's `liquid-audio`
     package — one end-to-end audio model (speech in, speech out)
     for hosts that can carry it.
   - Text tier: LFM2-1.2B (GGUF) via llama.cpp for SMS drafts and
     tools.
   - **Tier 2 voice (designed, not a contingency):** cascaded
     small STT → LFM2 text → small TTS, for hosts that can't
     carry the audio model at call latency. Both voice tiers are
     designed from day one; the capability probe chooses. A call
     forgives about a second of response latency, not three —
     per-turn latency is measured at M0b and decides Tier 1's
     fate, not optimism.
   Model files ship on the unit's flash. **License gate:** LFM
   weights are under the LFM Open License, not Apache — the
   commercial terms for bundled distribution must be **closed
   before M3 spend** (director's order; see
   `docs/GAPS-AND-RISKS.md`).
7. **Sleep is designed for, not discovered.** The host falling
   asleep is the product's #1 reliability risk: texts survive it
   (store-and-forward), calls don't. The layered design — Shop
   Mode prevention profile, wake-on-ring, scheduled wake,
   reconcile-on-wake honesty, and a sleep test inside setup — is
   specified in `docs/POWER-AND-WAKE.md` and is part of the
   product from M0, not a patch for later.
8. **Pi is the floor, not the base.** LFM models are edge-first and
   run on Pi-class hardware (LFM2-1.2B Q4 ≈ 15 tok/s on a Pi 5).
   The customer's Windows laptop is the primary host because the
   dongle product exists to *not* sell a computer. But Pi 5-class
   performance is the reference minimum the design must stay
   honest on — it keeps the system lightweight by construction,
   and it makes a later Pi appliance variant a packaging exercise
   instead of a rewrite.

## Milestones

- **M0a — Plumbing proof.** Windows host, actual dongle, drivers
  installed the installer way. A real incoming call: host rings,
  agent answers, plays a fixed recorded greeting, records the
  caller's speech, transcribes it with whatever is on hand, hangs
  up cleanly. Call log + recording read back from the database.
  Pass criteria recorded: rings before answer, time-to-audio
  after pickup, no dropped audio. No LLM in this gate — M0 is
  split (director's order) so a failure names its layer.
- **M0b — The acceptance call.** Same setup, live agent
  conversation: greeting, hours question, booking intent,
  transcript saved and read back at both ends. Added pass
  criteria: **measured response latency per turn** (this number
  decides whether Tier 1 voice survives) and the **from-sleep
  pass** (the Sleep Test in `docs/POWER-AND-WAKE.md`). Runs on a
  clean, non-dev Windows machine through the real driver install.
  Nothing else hardens before M0b passes.
- **M1 — SMS chain.** Incoming SMS → identify/create contact →
  retrieve local memory → generate held draft locally → staff
  approval → carrier send → accurate native conversation history.
  (Same first chain as inkPilot, on this runtime.)
- **M1.5 — Number bridge proof.** A real shop number forwarding
  to a StaxLine SIM, with added ring delay and the voicemail race
  measured end to end. Forwarding latency eats the wake window,
  so this is a technical proof, not sales guidance.
- **M2 — The four tabs, real.** Messages, Phone, Contacts,
  Calendar working against the local database; side card with
  Soul/agent/memory/activity; memory review UI (correct, disable,
  forget). Exit includes the **published minimum host spec**,
  derived from the capability probe and M0b's latency numbers —
  "runs on a computer you already own" is never claimed without
  it.
- **M3 — The unit.** Composite-device build, signed installer from
  the unit's own flash, IMEI license tie, first-run setup that a
  non-technical owner can finish: SIM in, install, name the shop,
  teach it hours and services, test call. **Gate: the LFM license
  answer is in hand before money is spent here.**
- **M4 — Remote shells.** Android WebView APK pointing at the LAN
  host; iOS Safari bookmark path; both verified on real phones on
  a real shop LAN.
- **M5 — Two-shop pilot, then a batch of five.** Fargo Tattoo and
  one salon run it live for real customers; then five units sold
  to shops the owner knows. Pilot exit criteria include
  **measured support minutes per shop per week** — that number,
  not parts cost, decides whether $300 is a price or a subsidy.
  Sales beyond that wait for pilot evidence.

## Standing rules inherited from the owner's other tracks

- Prove-it: a thing is done when it's read back at the receiving
  end (the call heard, the text arrived, the record on disk) —
  never when the code merely runs.
- Human-first phone: AI pickup is a deliberate owner setting, off
  by default; a human can always take over.
- Held drafts for anything customer-facing outside scripted
  routine replies; never promise a price; the booking link is the
  availability answer.
- File-size ratchet from day one (see README of the ratchet in
  `docs/FILE-SIZE-RATCHET.md`-equivalent: `.file-size-ratchet.json`
  + `scripts/check-file-size-ratchet.sh`).
- Every milestone records its performance numbers (installed
  size, cold-start-to-ready, resident RAM with the voice model
  loaded, per-turn voice latency) on the weakest reference
  machine in the building. "Lightweight" and "Pi-class floor"
  are claims those numbers make, or they are not made.
