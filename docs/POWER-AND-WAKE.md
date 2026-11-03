# StaxLine — Power, sleep, and wake

A phone system on somebody else's laptop has one mortal enemy:
the computer going to sleep. This document is the design for that
problem. It is layered — no single layer is trusted alone.

## The asymmetry that drives everything

- **SMS tolerates sleep.** Texting is store-and-forward: if the
  host is asleep, messages wait at the carrier / on the modem and
  arrive when the machine wakes. A text answered in five minutes
  instead of five seconds is still answered. Nothing is lost.
- **Voice does not tolerate sleep.** A ringing call waits ~20–30
  seconds, then the caller reaches carrier voicemail or hangs up.
  If the host cannot wake and answer inside that window, the call
  is missed. **Voice sets the power policy; SMS just benefits.**

## Layer 1 — Prevent (the primary defense)

The installer, with the owner's explicit consent, applies a
"Shop Mode" power profile while the system is armed:

- On AC power: system sleep = **Never**; display may sleep freely
  (a dark screen answers calls fine).
- USB selective suspend = **Off** for the modem's USB functions
  (a suspended modem port cannot hear a ring).
- Lid-close action while plugged in = **Do nothing**.
- Wake timers = **Allowed** (needed by Layer 3).
- On battery: the profile relaxes (we do not drain a laptop to
  keep a phone line alive) — and the UI says so loudly: "Running
  on battery: the phone system is not protected." Battery is for
  outages, not for operation.

The setting is a visible toggle in the side card (Behavior), not
a hidden installer trick. A **daily self-check** re-reads the OS
power settings and warns in Activity if they no longer match —
Windows updates and helpful relatives both change these settings,
and silent drift is how phone systems die.

## Layer 2 — Wake on ring (the safety net)

Prevention can fail (someone unplugs the laptop, a setting gets
reset), so the modem is also armed as a wake source:

- Installer enables USB remote wakeup for the modem's composite
  device — "Allow this device to wake the computer" — and the
  modem's ring/SMS indications assert the USB remote-wake signal.
- From S3 sleep this typically resumes a machine in ~2–10
  seconds. Processes freeze in RAM during S3 and resume intact,
  so the model stays loaded — there is no model-reload delay in
  the answer path. The modem worker's call flow must tolerate
  resuming mid-ring: the network holds the call while the host
  wakes; the flow answers as soon as the worker is alive, not on
  a fixed ring count.
- **Modern Standby (S0 low-power idle) is the known-weak case:**
  on many laptops, USB wake behavior in Modern Standby is
  OEM-dependent and sometimes simply doesn't fire. The setup
  wizard detects the machine's standby model and reports it
  plainly ("This laptop uses Modern Standby — sleep protection
  is best-effort; Shop Mode keeps it awake instead").
- **The voicemail race:** if the carrier's voicemail picks up at
  20 seconds and the host needs 10 to wake, the margin is thin.
  Setup guidance tells the owner to extend the carrier ring time
  or disable carrier voicemail on the shop line, so the agent —
  not the carrier — owns the greeting.

## Layer 3 — Scheduled wake

- A daily wake timer (Windows Task Scheduler "wake the computer
  to run this task" / Linux `rtcwake` + systemd timer) wakes the
  host before opening time: run the power self-check, reconcile
  (Layer 4), warm the model, and post the morning status to
  Activity ("Shop line ready, 2 texts waiting").
- A nightly maintenance window does backups to the unit's flash
  while nobody is calling.

## Layer 4 — Reconcile on wake (honesty after the fact)

If the machine slept anyway, the system says what happened:

- The launcher keeps heartbeat timestamps; a gap longer than a
  few minutes is recorded as a sleep event with start/end times.
- On wake, the modem worker queries the modem/SIM for stored
  messages and the modem's call log, merges anything that
  arrived while asleep into the real conversation history with
  its true arrival time, and drafts a "sorry we missed your
  call" text for each missed call (a held draft per the standing
  rules — the owner enables auto-send for this scripted reply if
  they want it).
- Activity shows one plain line: "Computer slept 11:42 PM–7:58
  AM. 3 texts arrived, 1 call missed." Never pretend the system
  was live when it wasn't.

## Layer 5 — The sleep test (proof, in setup)

The setup wizard ends with a **Sleep Test**, same prove-it shape
as the acceptance call:

1. Wizard arms Shop Mode off, puts the machine to sleep.
2. Owner calls the shop line from their cell phone.
3. Pass = the machine wakes and the agent answers; the result is
   read back in the wizard and logged.

A machine that fails the sleep test isn't rejected — Shop Mode
(Layer 1) is the supported posture — but the owner sees the real
result for their hardware before a customer ever does.

## The honest recommendation

The most reliable StaxLine host is a computer that exists to run
it: a spare mini-PC, an old desktop, or the later Pi appliance
variant — always on, nothing else to do. A working laptop that
also gets closed, carried home, and borrowed is supported, and
Layers 1–4 are built for it, but the setup wizard says this out
loud. Sleep is the #1 reliability risk in this product; the
design treats it that way rather than discovering it in support
calls.
