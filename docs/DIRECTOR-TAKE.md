# StaxLine — Director's Take (Round 1)

Independent planning review, 2026-11-03. Formed from the
commissioning brief first, then judged against Stax's draft plan
(`docs/PLAN.md`, `ARCHITECTURE.md`, `MEMORY-DESIGN.md`,
`REMOTE-ACCESS.md`, `POWER-AND-WAKE.md`, `GAPS-AND-RISKS.md`).
Where this take and the draft disagree, this take is the position
Stax should edit toward or explicitly rebut — not average the two.

## Verdict

The product shape is right and should be frozen: a one-time-buy
local phone system where the modem board is simultaneously the
telephony, the installer medium, and the license key is a real
differentiator that no cloud receptionist can copy without
becoming a different company. Salons/tattoo first is correct —
the owner has lived credibility and two pilot sites in his own
building.

But the draft plan is calmest about the two things most likely
to kill it: (1) whether an end-to-end audio model produces
acceptable call latency on the CPU-only commodity laptops shops
actually own, and (2) the first-hour experience — unsigned-feeling
driver installs and the "but my clients know my old number"
conversation. Neither is a reason to stop. Both must be promoted
from background assumptions to gated proofs, earlier than the
draft has them. Details and orders below.

## Recommended stack

- **Runtime: Python 3.12, launcher + three isolated workers —
  confirmed.** Python is *glue*, never DSP: the audio path must
  ride native libraries (the modem's USB audio endpoint, a native
  audio capture/playback lib), and inference runs in its own
  process. The plan's worker isolation is not an optimisation, it
  is the load-bearing wall. If a model crash can take down a
  ringing phone, the architecture has failed regardless of
  language.
- **App server: stdlib HTTP — confirmed; FastAPI rejected.**
  FastAPI buys nothing at this scale and imports a dependency
  tree into a product whose entire install story is "it just
  runs off the stick." Zero-dependency core is a feature. Keep it.
- **UI: one static vanilla JS/CSS surface, no build step —
  confirmed; htmx and Preact/Svelte both rejected for v1.**
  htmx's server-rendering model fights the offline/LAN/multiple-
  wrappers design; a framework build step is a tax every future
  edit pays forever. Vanilla + SSE is enough for four tabs and a
  drawer. If the UI ever outgrows it, that will be visible in the
  ratchet, not anticipated today.
- **Inference: llama.cpp (LFM2-1.2B GGUF) for text — confirmed.
  LFM2-Audio via `liquid-audio` for voice — accepted as the bet,
  rejected as an assumption.** Nobody in this project has yet
  measured speech-to-speech latency for that model on a mid-range
  CPU-only Windows laptop, and a phone call forgives roughly a
  second of response latency, not three. Therefore: the cascaded
  fallback (small STT → LFM2 text → small TTS) is **promoted from
  footnote to a designed Tier 2 from day one**, because a large
  share of real shop PCs will land on it. The plan currently
  mentions the cascade only as "only if the audio tier can't
  run" — that is backwards. Design both tiers; let the capability
  probe choose.
- **Modem path — Windows: serial AT via pyserial + USB audio,
  confirmed** (there is no other option; ModemManager does not
  exist there). **Linux: the same AT path, and I am explicitly
  forbidding a second Linux modem stack in v1.** The production
  Rust/ModemManager code in StaxCloud is a behavioural reference
  and an escape hatch, nothing more. Two modem stacks means two
  call state machines, two bug surfaces, and a support matrix a
  one-person product cannot carry. Note the honest gap this
  creates: voice feasibility was verified 2026-11-01 through
  ModemManager on Linux. The Windows AT + USB-audio voice path
  is *unproven* — which is exactly why it is M0 (below).
- **Memory: one SQLite file, FTS5, plain-language memories with
  source/review state/supersede/tombstone — confirmed**, with
  one hard rule change in the section on disagreements below.
  No vector store in v1 is correct; FTS5 + contact-scoped
  retrieval is the right size for one shop's world.
- **Pi: floor, not base — confirmed, and make it enforceable.**
  "Pi 5-class is the reference minimum" only disciplines anything
  if each milestone records its performance numbers on the
  weakest reference machine in the building. Add that line to
  every milestone's exit criteria or delete the claim.

## The TWA / PWA question, plainly

Stax's prior is correct and the draft's answer is correct in its
conclusion: **a real TWA is impossible without public
infrastructure** — Digital Asset Links must be served over HTTPS
from a public domain bound to the app signing key. Asking for a
TWA with nobody's infrastructure is asking for a thing that does
not exist. Stop wanting it.

What ships:

- **Android: the sideloaded WebView-shell APK.** It rides the
  unit's flash, installs in the setup wizard via a QR code to the
  page the host itself serves, points at the host on the shop
  LAN, and pairs with a one-time code shown on the host screen.
  This is the primary mobile path and it is good.
- **iOS: a browser bookmark in v1. Not a CA-profile PWA.** I am
  overruling the draft here (see disagreements). The owner opens
  the LAN address in Safari, saves it, enters the pairing code
  once. It works; it does not install to the home screen with a
  service worker. Say exactly that.
- **Onboarding step (the only one):** one wizard, run on the
  host, ending with the phone in the owner's hand showing live
  shop data and a "your phone is connected" check. If onboarding
  needs a second session, it has failed its design goal.

Out-of-LAN access stays what the draft says: owner's own
WireGuard, documented as an advanced option, never a relay of
ours. That limit is the product's promise, not its apology.

## Milestones — M0 judged, split, and kept first

Stax's instinct is right: the acceptance call *is* the product's
proof, and nothing hardens before it. But as written, M0 stacks
three unproven things into one gate — the Windows AT voice path,
the USB audio plumbing, and an end-to-end audio model's live
conversation quality. If it fails, you learn nothing about which
layer failed. Split it:

- **M0a — Plumbing proof (days, not weeks).** Windows host,
  actual dongle, actual installer-path drivers. A real incoming
  call: host rings, agent answers, plays a fixed recorded
  greeting, records the caller's speech, transcribes it with
  whatever is on hand, hangs up cleanly. Call log + recording
  read back from the database. **Pass criteria, recorded:** rings
  before answer, time-to-audio after pickup, no dropped audio.
  No LLM in this gate.
- **M0b — The acceptance call (the draft's M0, kept whole).**
  Same setup, live agent conversation: greeting, hours question,
  booking intent, transcript saved and read back at both ends.
  **Add two pass criteria the draft lacks:** measured response
  latency per turn (recorded, not vibes — this number decides
  whether Tier 1 voice survives), and the from-sleep pass the
  draft already added (kept — it was the right addition).
  Also: M0b runs on a *clean, non-dev Windows machine* through
  the real driver install, not on a machine where the drivers
  were already coaxed into place by hand.
- **M1 — SMS chain.** Unchanged from the draft; it is the right
  second proof and the cheapest daily value in the product.
- **M1.5 — Number bridge proof (new, pulled forward).** Before
  any pilot: a real shop number forwarding to a StaxLine SIM,
  measuring added ring delay and the voicemail race end to end.
  The draft leaves the number strategy as sales guidance; it is
  actually a technical behaviour (forwarding latency eats the
  wake window) and it must be measured, not asserted.
- **M2 — Four tabs real.** Unchanged, with one addition: the
  capability probe's output becomes a **published minimum host
  spec** at this gate (see cuts).
- **M3 — The unit.** Composite device + signed installer + IMEI
  license. **Gate change:** the LFM license check (gap #5 below)
  must be closed *before* money is spent here, not "pre-M5."
- **M4 — Remote shells.** Android APK as designed; iOS reduced to
  the bookmark path per this take.
- **M5 — Two-shop pilot, batch of five.** Unchanged. Pilot exit
  criteria must include measured support minutes per shop per
  week — that number, not parts cost, decides whether $300 is a
  price or a subsidy.

## Top 5 gaps / risks, ranked, with the mitigation I order

1. **Voice latency and quality on real shop hardware.** The
   single largest technical unknown in the product; the draft's
   gap list does not name it at all, which is itself the finding.
   *Order:* benchmark before M2 design hardens — LFM2-Audio on a
   representative mid-range CPU-only laptop, latency per turn
   recorded; Tier 2 cascade designed in parallel regardless of
   the result; minimum host spec published at M2.
2. **The number problem.** Agree with the draft that it is the
   adoption problem; disagree that it is mainly a sales-copy
   problem. *Order:* call-forwarding is the launch story ("keep
   your number — your current line forwards to StaxLine when you
   want the agent on"), proven technically at M1.5 including the
   ring-delay measurement. Porting stays post-pilot.
3. **Windows driver and installer friction on clean machines.**
   A non-technical owner's first ten minutes decide the product's
   reputation, and SIM7600 multi-function USB on a clean Windows
   install is the roughest ten minutes we ship. *Order:* M0/M3
   gates run on clean borrowed machines, never dev machines;
   buy the code-signing certificate early — its lead time is a
   schedule risk hiding inside a purchase order, and the signed
   prompt is half the product's trust story.
4. **Host sleep and power.** The draft's treatment is genuinely
   good — the best doc in the set. My one correction: wake-on-
   ring is an OEM lottery (Modern Standby especially) and must
   never be load-bearing. *Order:* Shop Mode (prevention) is the
   only *supported* posture and is worded that way in product
   copy; wake-on-ring is a bonus that the Sleep Test measures
   per machine; a machine that fails the sleep test gets Shop
   Mode as its answer, not a shrug.
5. **LFM Open License commercial terms.** This can invalidate
   the ship-weights-on-flash model outright, and it costs almost
   nothing to resolve now versus real money after hardware is
   built. *Order:* read the terms and, if redistribution at
   commercial scale is not clearly permitted, get the answer from
   Liquid in writing **before M3 spend**. The draft's fallback
   ("provisioned under whatever mechanism the license allows")
   is acceptable only as a fallback, not as the plan.

Demoted from the draft's list, deliberately: **10DLC/A2P** is
real but launch behaviour is low-volume and human-shaped; the
draft's honest-guidance mitigation suffices for v1. **Support
burden** is real but unmeasurable until the pilot — it becomes a
number at M5, not a design input now. **USB brownout** and
**host death** are adequately handled in the draft as written.

Unknowns I am flagging as checks, not asserting answers:
`liquid-audio`'s Windows/CPU behaviour and installed size (torch
is not "lightweight" by any honest measure — the installer-size
and cold-load budgets must be recorded, and a cold model load in
the answer path after a wake would blow the ring window; the
model must be resident before the phone can ring, which feeds
the RAM floor); whether iOS accepts any locally-constrained CA
behaviour that would change the iOS call below; carrier
forwarding ring delay on the actual carriers the pilot shops use.

## Cuts to the owner's framing

- **Cut "PWA for iOS" from the pitch and the plan's promises.**
  v1 iOS is a browser bookmark on shop Wi-Fi. Promising an
  installed PWA via a CA profile sets up the least technical
  customers for the most technical setup step in the product.
- **Cut trades from all v1 framing.** Beachhead verticals only.
  Trades calls carry emergency-dispatch expectations ("my house
  is flooding") that poison the agent playbook and the consent/
  liability posture. Trades is an expansion decision made with
  pilot evidence, not a launch adjective.
- **Cut the unqualified "runs on a computer you already own."**
  Replace with "runs on your shop computer" plus a published
  minimum spec from M2. The unqualified version manufactures
  returns and one-star mornings on 4 GB laptops from 2016.
- **Cut MMS from v1 scope, explicitly.** The architecture doc
  lists SMS/MMS handling; on Windows over AT, MMS is a swamp,
  and StaxCloud needed a dedicated daemon for it on Linux.
  v1 is voice + SMS. Pictures from clients matter to tattoo
  shops — they arrive as "text us a photo" via the booking-link
  path and MMS lands post-pilot with evidence of demand.
- **Cut WireGuard from the v1 documents beyond one footnote.**
  Every paragraph spent on remote-access tunnels is a paragraph
  recruiting StaxLine into the networking-support business.

## Where I agree with Stax's draft

- The overall shape: composite USB unit, host-runs-everything,
  board-as-license, records-readable-without-a-valid-board.
  The license design's refusal to hold customer data hostage is
  exactly right and should survive every future edit.
- Python + stdlib core + worker isolation; one static UI; one
  SQLite database; FTS5 over vectors; AT-first modem path with
  StaxCloud as behavioural reference. All confirmed above.
- `POWER-AND-WAKE.md` as a whole: the SMS-survives/voice-doesn't
  asymmetry, prevention-first layering, reconcile-on-wake
  honesty ("never pretend the system was live when it wasn't"),
  and the Sleep Test inside setup are the strongest thinking in
  the draft. The M0-passes-twice amendment (awake + from sleep)
  is correct and stays.
- The memory rules: no source, no memory; corrections supersede
  rather than overwrite; forgetting is a real delete with a
  tombstone against silent re-learning; the context pack saved
  with the draft so a human sees *why*. This is buildable as
  written.
- The gap list's existence and its honesty about number
  strategy, consent law, the not-a-911-line rule, and repackaging
  labels. Most drafts omit all four.

## Where I disagree, and the doc changes I order

1. **`REMOTE-ACCESS.md` — demote the local CA.** Move the CA
   profile from "primary path" to an explicitly advanced,
   optional, post-v1 possibility. Grounds: it asks the least
   technical users to perform the most trust-sensitive action in
   consumer computing (installing a root CA — which iOS presents
   with warnings, buries the trust toggle, and which, if the host
   is ever compromised, is a general-purpose mint for trusted
   certificates, not a StaxLine-scoped one). v1 text: bookmark
   path is the iOS product; the HTTP pairing token's LAN
   sniffability is stated as an accepted v1 risk. Also demote the
   shell's Wake-on-LAN from a designed feature to a nice-to-have
   line — it is garnish on the power design, not a layer of it.
2. **`MEMORY-DESIGN.md` — voice gets approved memories only.**
   The draft lets the agent act on `draft` memories for
   "low-stakes context." On a live call there is no human in the
   loop and no low-stakes — a wrong draft memory spoken to a
   customer is a sent message. Rule change: call context packs
   contain `approved` memories only; `draft` memories may inform
   *held* SMS drafts, where a human reads before anything sends.
   One sentence in the doc, one filter in the pack builder.
   Add also: a memory created from a call cites the transcript
   and timestamp as its source — "a memory with no source does
   not get created" needs the call case spelled out.
3. **`PLAN.md` — fix the decisions list and M0.** The decisions
   are numbered out of order (sleep is item 8, printed before
   item 7, Pi) — fix the numbering; a direction-of-record doc
   with scrambled numbering invites scrambled reading. Split M0
   into M0a/M0b and add M1.5 per the milestones above; add the
   latency and minimum-spec criteria; change the license flag in
   decision 6 from "tracked in GAPS" to "closed before M3."
   Decision 6 should also name Tier 2 cascade as a designed tier,
   not a contingency.
4. **`ARCHITECTURE.md` — three additions.** (a) An explicit ban:
   no second (ModemManager) modem stack in v1. (b) A budget
   table to be filled by measurement, not adjectives: installed
   size, cold-start-to-ready time, resident RAM with voice model
   loaded, per-turn voice latency — the word "lightweight" is
   banned until those four numbers exist. (c) The model-resident
   requirement: the voice model is loaded and warm before the
   line is armed; wake/resume behaviour must state that the model
   survives S3 in RAM and what happens (honest "warming up"
   state, calls reconcile) when it doesn't.
5. **`GAPS-AND-RISKS.md` — re-rank.** Insert "voice performance
   on commodity hardware" at #1 or #2 (it is currently absent);
   raise the license item's deadline language to pre-M3; add
   "carrier forwarding adds ring delay, compounding the wake
   window" to the number item; add model cold-start as a named
   sub-risk under USB/hardware or its own line. The current #1
   (sleep) stays top-three — the re-rank is about what was
   missing, not about demoting what was there.
6. **`POWER-AND-WAKE.md` — one wording order.** Everywhere
   Layer 2 is described as a "safety net," add the draft's own
   honest sentence about Modern Standby next to it, not two
   paragraphs later. A reader who stops early must not walk away
   believing wake-on-ring is dependable. The doc already contains
   the truth; this is about its placement.

## Bottom line

Build it in the draft's shape, with M0 split, Tier 2 real, the
CA demoted, voice memories approved-only, and the license answer
in hand before hardware money moves. The plan's bones are good —
its main defect is optimism about other people's computers, and
every change above is that defect being corrected in a specific
place.

— Director, Round 1, 2026-11-03
