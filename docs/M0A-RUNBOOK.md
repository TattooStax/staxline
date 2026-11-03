# M0a runbook — the plumbing proof

M0a proves one thing: on a real Windows host, through the real
dongle, a real incoming call can be answered by this code, play
audio to the caller, record the caller's speech, hang up
cleanly, and leave a call log + recording that read back from
the database. No model, no agent — if this layer fails, nothing
above it matters (see `docs/PLAN.md`).

The harness is `scripts/run_m0a.py`; its state machine is proven
against a simulated modem in `tests/test_modem_fake.py`. Those
tests prove the *logic*. Only a live run on hardware proves the
*plumbing* — never cite one as the other.

## Before the test window

- [ ] Modem with an active SIM whose number the tester knows.
- [ ] Host: Windows machine. Install the SIMCom USB drivers the
      installer way (not hand-coaxed — a clean-machine install
      is part of the gate at M0b; for early M0a runs, note any
      manual steps taken, they become installer requirements).
- [ ] `pip install pyserial sounddevice soundfile` on the host
      (the future installer provisions these; for M0a it's a
      hand step, recorded as such).
- [ ] Identify the modem's AT port (Device Manager → Ports) and
      its USB audio device (Sound settings / `sounddevice`
      query). Note both in the evidence.
- [ ] A greeting WAV (any short recording) or accept the test
      tone — the evidence records which was used.

## The production-modem warning (read before borrowing hardware)

The only modem currently on hand is the SIM7600G-H in the Dell
(staxcore), and it is not spare: it carries the live StaxCloud
shop line **701-491-3276** (texts land through it today).

- Unplugging it takes that line down for the whole test window.
  Pick the window deliberately (after hours), and tell anyone
  who relies on the line.
- Testing in place on the Dell is a *Linux* proof only: the AT
  ports there are owned by ModemManager/StaxCloud services,
  which must be paused first — and it does not satisfy the
  Windows gate. It is still useful as a first smoke of the AT
  path against the real modem.
- The Windows gate requires the modem on a Windows host. That
  is the run that counts as M0a.

## Run

1. Probe (read-only): `python scripts/run_m0a.py --port <PORT>
   --probe-only` → model, IMEI, SIM READY, signal. If the probe
   fails, stop: drivers/port are wrong, and that failure is the
   day's finding.
2. Arm: `python scripts/run_m0a.py --port <PORT> --greeting
   <FILE.wav> --record-seconds 10`.
3. Tester calls the modem's number from a cell phone, speaks a
   few words after the greeting, stays on until the harness
   hangs up (~record window), and notes: rings heard, whether
   the greeting was audible, any dropouts.
4. Read back the evidence: `m0a-evidence/m0a-result.json`, the
   recording WAV (play it — the caller's speech must be on it),
   and the `calls` row in `staxline.db`.

## Pass criteria (recorded, not vibes)

- [ ] Rings before answer recorded and ≤ 2.
- [ ] Time-to-answer recorded; tester heard the greeting
      clearly at the cell.
- [ ] Recording contains the caller's actual speech, no long
      dropouts.
- [ ] Call row + activity row read back from the database.
- [ ] Any manual driver/install steps written into the evidence
      (they are M3 installer requirements).

## After (if the production modem was borrowed)

- [ ] Modem back in the Dell; StaxCloud Inbox banner reads
      "Business modem connected" again before the window is
      declared over.
- [ ] Evidence + deviations committed to the repo or filed in
      the dev notes the same day.
