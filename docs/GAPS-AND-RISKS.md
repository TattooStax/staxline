# StaxLine — Gaps and risks

Ranked by how likely they are to hurt a real customer.
Re-ranked 2026-11-03 after the director's round-1 take (the
voice-performance item was missing entirely from the first
draft — that absence was itself a finding).

1. **Voice latency and quality on real shop hardware.** The
   largest technical unknown in the product. Nobody has measured
   LFM2-Audio's speech-to-speech latency on a mid-range CPU-only
   Windows laptop, and a caller forgives roughly a second of
   response latency, not three. Sub-risk: a cold model load
   inside the answer path blows the ring window outright — the
   voice model must be resident before the line is armed (see
   `docs/ARCHITECTURE.md`). Mitigation ordered: benchmark before
   M2 design hardens, per-turn latency recorded at M0b, Tier 2
   cascade designed in parallel regardless of the result, and a
   published minimum host spec at M2.

2. **The number problem is the adoption problem.** Shops already
   have a number their clients know. Porting it to a new SIM is
   slow and can fail; asking them to change numbers is a
   dealbreaker. Launch story: carrier call-forwarding from the
   existing number ("keep your number — your line forwards to
   StaxLine when you want the agent on"). But forwarding is also
   a technical behaviour: **forwarding adds ring delay, which
   compounds the wake window** in `docs/POWER-AND-WAKE.md` —
   hence the M1.5 proof measuring it end to end, on the actual
   carriers the pilot shops use. Porting support is post-pilot.

3. **Host sleep kills voice.** A closed laptop is a dead phone
   line. Full treatment in `docs/POWER-AND-WAKE.md`: Shop Mode
   prevention profile (the only *supported* posture),
   wake-on-ring as a measured bonus rather than a promise,
   scheduled wake, reconcile-on-wake honesty, and a sleep test
   in setup so the owner sees their machine's real behaviour
   before a customer does.

4. **Windows driver and installer friction on clean machines.**
   The SIM7600 presents multiple USB functions (AT port, audio,
   network). On a clean Windows machine the installer must land
   SIMCom's drivers in the right order or the owner meets Device
   Manager in their first ten minutes — the ten minutes that
   decide the product's reputation. Mitigation: signed driver
   package inside a signed installer, a first-run hardware check
   that names exactly what's missing, and M0/M3 gates run on
   clean borrowed machines, never dev machines. **Buy the
   code-signing certificate early** — its lead time is a
   schedule risk hiding inside a purchase order. First contact
   with the real unit already revised the modem plan once —
   its USB serial AT ports do not answer at all, so Linux runs
   on ModemManager and the Windows COM-port AT question is now
   the sharpest unknown in M0a (evidence:
   `docs/evidence/2026-11-03-victus-live-test.md`).
9b. **Carrier service chatter lands in the modem's SMS store.**
    The M1 chain's first live ingest (2026-11-03) pulled
    visual-voicemail sync messages (shortcode 127) and a carrier
    APN-provisioning notice (shortcode 6700) in alongside real
    customer texts — the modem store does not distinguish them.
    Ingest needs a classification step: known carrier/service
    patterns file as system records (genuinely useful — the VVM
    sync message is how the carrier announces a voicemail) but
    never surface as customer conversations in Messages.
10. **USB power is a product requirement, not a bench detail.**
    The modem brown-outs on an ordinary laptop USB port under
    combined data + voice load (kernel-proven re-enumeration,
    2026-11-03): the composite unit's hub is **powered**, or
    host-port power is a published minimum-spec line with a
    setup-wizard power check. A customer on a weak port would
    live the failure as "the box randomly dies during calls."

5. **LFM Open License commercial terms — ANSWERED
   (2026-10-30).** The owner accepted the LFM Open License
   v1.0 in writing on the InkStax track: free commercial use
   up to $10M annual revenue, enterprise agreement above that.
   LFM weights may ship on the product under those terms; the
   pre-M3 action is reduced to recording the acceptance with
   the product's legal notes and re-checking the ceiling if
   the business ever approaches it.

6. **USB power and random shop hardware.** A modem drawing peaks
   from a weak USB port on an old laptop browns out and resets
   mid-call. Mitigation: capability probe warns on repeated modem
   resets; setup guide steers to a rear/motherboard port or a
   powered hub; the appliance variant (fixed known hardware)
   exists partly to kill this class.

7. **Host death = shop memory death.** If the shop's PC dies,
   their records die with it unless backed up. Mitigation:
   scheduled DB snapshots to the unit's own flash (the unit is
   the backup), plus one-click export in setup. Restore = new
   host + the same unit.

8. **Call recording and consent law.** Recording/consent rules
   vary by state (one-party vs two-party). Mitigation: the agent
   announces itself and the recording at pickup ("This is the
   shop's assistant; this call may be recorded"), recordings are
   a per-shop setting defaulting to the safer posture, and
   transcripts remain if recording is off.

9. **Not an emergency or life-safety line.** The shop line must
   never be presented as a 911-capable phone. The agent's
   playbook routes emergencies to "call 911" and the setup
   checklist says the shop keeps a normal phone for emergencies.

10. **Repackaging rules.** The unit is a branded case around a
    Waveshare board: FCC ID and serial labels stay intact and
    visible, copy says "contains a SIM7600G-H module," never that
    we manufactured the modem. An OEM/white-label conversation
    with Waveshare is the clean route if volume justifies it.

11. **10DLC / A2P registration for business SMS.** Real, and
    deliberately ranked here rather than higher (director's
    call): launch behaviour is low-volume and human-shaped.
    Mitigation: honest setup guidance (sole-proprietor tier
    where it fits), and product copy that never promises
    bulk/marketing texting. This product is a front desk, not a
    broadcast tool.

12. **Support burden on non-technical owners.** Real but
    unmeasurable until the pilot, so it is a metric, not a
    design input: the pilot (M5) records support minutes per
    shop per week, and that number decides the $300 question.
    In the meantime: an Activity feed in plain words, a daily
    self-check that catches drift before customers do, and a
    one-button diagnostics bundle (logs + state, no customer
    message content by default).
