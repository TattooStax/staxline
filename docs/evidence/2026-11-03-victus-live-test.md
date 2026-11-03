# Live test evidence — 2026-11-03, the owner's Victus

Interim record of the first live session with the real modem
(the SIM7600G-H from the Fargo Tattoo box, moved by the owner
to his Victus laptop, Fedora). Times are CST; the Victus clock
runs ~2–3 minutes behind. Raw logs live on the Victus in
`~/staxline-test/` (not committed — they contain phone numbers).

## Proven

- **Modem live on the Victus:** USB 1e0e:9001 enumerated,
  ModemManager registered it on T-Mobile (home), signal 70%.
  Port map: ttyUSB1 = GPS (NMEA streaming), ttyUSB2/ttyUSB3 =
  AT (labelled), ttyUSB4 = audio, cdc-wdm0 = QMI.
- **SMS out:** a test text to the owner's Pixel was created and
  sent via ModemManager; state read back `sent`.
- **SMS in:** the owner's reply ("What services do you offer",
  from his Pixel number) was read back off the modem with
  content, number, and received state. **Two-way SMS: proven
  end to end on the real unit.**
- **Reply loop:** a second outbound text answering him also
  read back `sent`.
- **MMS notification path:** the owner's picture message
  produced an MMS retrieval attempt in mmsd-tng the moment it
  was sent — the push/notification leg works.

## Disproven / corrected assumptions

- **Serial AT does not answer on this unit.** Every AT form
  (`AT\r`, `AT\r\n`, lowercase, DTR/RTS asserted, 1–3 s reads)
  on ttyUSB2 and ttyUSB3 returned silence — before *and after*
  a modem reset + re-registration, in the same session where
  the GPS port streamed NMEA and QMI control worked fully.
  ttyUSB0 (diag) errors on write. Conclusion: on this
  firmware/composition, control is QMI/ModemManager-only over
  USB. The plan's AT-first decision was revised the same day
  (docs/PLAN.md #5, docs/ARCHITECTURE.md). Whether the module
  answers AT under the **Windows** driver composition is still
  unknown — that is now the sharpest open question for M0a.
- **A modem-level "connected" bearer is not a network.** The
  T-Mobile bearer connected at the modem (IPv6-only) but the
  host interface had no address, route, or DNS until applied
  by hand (address + default route + link DNS). Only then did
  the carrier MMSC name resolve through the bearer's own
  DNS64 (returning a NAT64 address). The product installer
  owns this step (in StaxCloud production it is the
  `staxbox-mms` NetworkManager connection).
- **Harness bug found by the test:** round 1's call script
  captured only stdout, discarding the answer command's error
  output — the "accept" never connected the call (the owner
  heard 6–7 rings and hung up). Fixed in round 2 (full result
  logging, state polling, ModemManager journal capture).

## Voice round 2 — the answer failure, named

The owner's second call (17:10 Victus) was captured with full
instrumentation. The ring was seen and confirmed, and the
answer command's result was logged verbatim:

```
couldn't accept the call: 'GDBus.Error:...Core.Failed:
Unhandled QMI protocol error (41): Couldn't accept call:
QMI protocol error (41): 'InvalidQosId''
```

ModemManager's journal shows the call going `ringing-in →
terminated (error)` in the same instant. **The QMI answer
request itself is rejected by the modem firmware, and the
call dies from the rejection** — in both rounds. The caller
was dropped to the carrier's voicemail. Inbound answering is
blocked on this: candidate routes are a newer ModemManager, a
lower-level qmicli answer, or a firmware note for this module.

## Voice dial-out — proven, including audio and DTMF

Immediately after, the modem **placed** a call to T-Mobile's
voicemail number (+1 805 637 7243): created, started, `active`
in ~2 s, and the USB audio captured **1,230,080 bytes of PCM
(67% nonzero, structured energy — the voicemail system's
voice)**, a DTMF digit was sent successfully mid-call
(`successfully send dtmf`), and the hangup was clean. So the
outbound voice path — dial, connect, two-way PCM, DTMF,
hangup — works end to end on this unit tonight. Only the
inbound *answer* direction is broken.

## Voicemail preservation (owner requirement, 2026-11-03)

The owner, after leaving a test voicemail: "Hopefully there's
a way for us to preserve those too because those are handy."
Adopted as a requirement, designed from tonight's evidence:

- **Primary:** the agent answers before the carrier does and
  records locally — a voicemail becomes a normal record with a
  transcription, beside the texts. (Gated on the answer fix.)
- **Retrieval leg (covers sleep/downtime — and the interim
  until answering works):** the unit dials the carrier
  voicemail on wake and on a schedule, navigates by DTMF,
  records the playback, and files it the same way, honestly
  labeled `source: carrier-voicemail`. Every primitive this
  needs was proven in the dial-out test above. Open items:
  the mailbox PIN for the line (unknown tonight), and menu
  brittleness (mitigated by keeping the raw audio, not just a
  transcription).

## Round 3 — the rig fell over: USB brown-out

A third harness was built to bypass ModemManager's answer
entirely: a direct QMI client through the protocol library
(libqmi GI bindings expose `ClientVoice.answer_call` even
though the `qmicli` tool ships no voice call actions;
ModemManager 1.24.2 was already current, so "update MM" was
never a real route). It armed cleanly — device opened via
qmi-proxy, VOICE client allocated — but **never saw a ring**:
before the owner's call arrived, the modem itself collapsed.
Kernel journal: the SimTech device re-enumerated as a new USB
device (all five ttyUSB ports re-attached). ModemManager
journal: a registration death-spiral (home → searching →
registering, repeatedly), ending at "No modems were found"
with the device still on the bus. The owner's call never
reached the modem; the carrier sent him to the (never
configured, Spanish-greeting) voicemail.

Diagnosis: **USB power brown-out.** This modem family pulls
current spikes a laptop USB port cannot reliably sustain,
worst when the data bearer and voice are active together —
exactly tonight's stacked test load. Its production life was
SMS-dominated and never stressed it. Bench fix: a powered
USB hub between host and modem. The QMI-direct answer remains
**untested** — neither proven nor disproven.

## Round 4 — THE ANSWER WORKS (QMI-direct)

After the replug (modem direct, registration held home with
zero flapping across a 90-second watch) and two harness
iterations — the first died on a wrong GI argument shape
(`get_all_call_info` takes `(input, timeout, cancellable,
callback)`; the signature was found by probing the binding
against the live modem, not by guessing) — the direct-QMI
harness answered the owner's call at 17:51:55 Victus:

- Ring detected the same second; call info fetched over the
  second QMI client (via qmi-proxy, alongside ModemManager);
  `answer_call` with call id 1 returned without error.
- **State went `ringing-in → active`** in both the harness
  log and ModemManager's journal, and held for the full
  18-second observation window before the harness hung up.
- **Inbound answering is therefore PROVEN on this unit** —
  through a direct QMI request, not ModemManager's (whose
  answer the firmware rejects with error 41).

The caller's experience, for the record: a loud continuous
buzz (the owner: "a big fart sound... it kept farting").
Leading explanation, consistent with all captures: **the
harness transmits nothing**, and the modem's voice path,
starved of TX audio, loops a frame — the captured RX slice
is sparse bursts (26.7 KB across 18 s, vs full-rate capture
on the outbound test) whose loud segments are strongly
periodic at ~85 Hz. In the product the agent streams audio
from the first frame, so TX never starves; a speaking-agent
call (M0b) is the test that confirms this reading.

## Pending at the time of writing

- **MMS end to end:** daemon restarted on the corrected
  network path with debug logging; awaiting a fresh picture
  from the owner (the first picture's retrieval retries had
  already expired, and its downloaded payload failed to
  decode — the debug run exists to capture why).
- **Tonight's voicemail capture** was fetched, verified
  (38.4 s WAV), and delivered to the owner for his own
  listen-check; not machine-transcribed.
- **Modem restore:** the unit goes back to the Dell when the
  owner closes the session; StaxCloud line health ("Business
  modem connected") is verified then.
