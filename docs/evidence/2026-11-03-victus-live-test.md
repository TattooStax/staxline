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

## Pending at the time of writing

- **Voice round 2:** instrumented harness armed (audio port
  held open from arm time); awaiting the owner's second call.
- **MMS end to end:** daemon restarted on the corrected
  network path; awaiting a fresh picture from the owner (the
  first picture's retrieval retries had already expired).
