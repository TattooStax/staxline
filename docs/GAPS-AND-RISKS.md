# StaxLine — Gaps and risks

Ranked by how likely they are to hurt a real customer. Each has
the mitigation in the plan; none are hand-waved.

1. **Host sleep kills voice.** The #1 risk — a closed laptop is a
   dead phone line. Full treatment in `docs/POWER-AND-WAKE.md`:
   prevention profile, wake-on-ring, scheduled wake, reconcile
   on wake, and a sleep test in setup so the owner sees their
   machine's real behavior before a customer does.

2. **The number problem is the adoption problem.** Shops already
   have a number their clients know. Porting it to a new SIM is
   slow and can fail; asking them to change numbers is a
   dealbreaker. Plan: launch on a new dedicated SIM number and
   bridge with carrier call-forwarding from the existing number
   (the shop's current line forwards to StaxLine when they want
   the agent on). Porting support is a post-pilot feature, not a
   launch blocker — but sales copy must never pretend it's
   nothing.

3. **Windows driver friction.** The SIM7600 presents multiple USB
   functions (AT port, audio, network). On a clean Windows
   machine the installer must land SIMCom's drivers in the right
   order or the owner meets Device Manager. Mitigation: signed
   driver package inside a signed installer, a first-run hardware
   check that names exactly what's missing, and the owner's own
   known-good machine classes tested first (M0/M3 gates).

4. **LFM Open License commercial terms.** LFM weights are not
   Apache-licensed. Shipping them on a sold product needs the
   commercial terms read and cleared *before* the first sale —
   a legal check, tracked as a pre-M5 blocker. Fallback if terms
   fail: ship the runtime, and models are provisioned under
   whatever mechanism the license allows.

5. **USB power and random shop hardware.** A modem drawing peaks
   from a weak USB port on an old laptop browns out and resets
   mid-call. Mitigation: capability probe warns on repeated modem
   resets; setup guide steers to a rear/motherboard port or a
   powered hub; the appliance variant (fixed known hardware)
   exists partly to kill this class.

6. **10DLC / A2P registration for business SMS.** US carriers
   increasingly require A2P registration for application-driven
   texting; a raw consumer SIM texting customers can be filtered.
   Mitigation: honest guidance at setup (sole-proprietor tier
   where it fits, volume expectations set low and human-like),
   and product copy that never promises bulk/marketing texting.
   This product is a front desk, not a broadcast tool.

7. **Call recording and consent law.** Recording/consent rules
   vary by state (one-party vs two-party). Mitigation: the agent
   announces itself and the recording at pickup ("This is the
   shop's assistant; this call may be recorded"), recordings are
   a per-shop setting defaulting to the safer posture, and
   transcripts remain if recording is off.

8. **Not an emergency or life-safety line.** The shop line must
   never be presented as a 911-capable phone. The agent's
   playbook routes emergencies to "call 911" and the setup
   checklist says the shop keeps a normal phone for emergencies.

9. **Support burden on non-technical owners.** Every failure
   above arrives as "it doesn't work." Mitigation: the Activity
   feed is written in plain words, the daily self-check catches
   drift before customers do, and a one-button "diagnostics
   bundle" (logs + state, no customer message content by default)
   the owner can send support. Support cost, not parts, is the
   margin risk at $300 — the pilot (M5) measures it before scale.

10. **Repackaging rules.** The unit is a branded case around a
    Waveshare board: FCC ID and serial labels stay intact and
    visible, copy says "contains a SIM7600G-H module," never that
    we manufactured the modem. An OEM/white-label conversation
    with Waveshare is the clean route if volume justifies it.

11. **Host death = shop memory death.** If the shop's PC dies,
    their records die with it unless backed up. Mitigation:
    scheduled DB snapshots to the unit's own flash (the unit is
    the backup), plus one-click export in setup. Restore = new
    host + the same unit.
