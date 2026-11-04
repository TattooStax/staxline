# StaxLine — Remote access without anyone's infrastructure

The owner's question: can the owner reach the system from their
phone — a TWA on Android, a PWA on iOS — **without relying on
anybody's infrastructure**? The plain answer shapes the design:

## Why not a TWA

A Trusted Web Activity is a Chrome feature that wraps a PWA in an
Android app. To run without the browser URL bar, it must verify
**Digital Asset Links**: a file served over HTTPS from a public
domain the developer controls, matched against the app's signing
key. No public domain + HTTPS endpoint, no trusted TWA — it
degrades to a Custom Tab with a URL bar, and it's still pointing
at an address that has to resolve from the phone.

A TWA therefore *requires* public infrastructure by design: a
domain, a CA-issued certificate, and DNS. That contradicts the
product's promise (works with no one's cloud). **No TWA.**

## The problem both platforms share

PWA installation and service workers require a **secure context**:
HTTPS with a certificate the phone trusts, or `localhost`.
The host's LAN address (e.g. `http://192.168.1.50:8787`) is
neither — so a naïve LAN PWA won't install and gets no service
worker. Android and iOS both enforce this; it's a browser rule,
not a vendor lock-in.

## What ships instead

**Android — a WebView shell APK (primary path).**

- A tiny native shell app (little more than a WebView + the
  host's address) that loads the exact same static UI from the
  host on the shop LAN. No Play Store, no asset links, no domain.
- Distributed the same way as everything else in this product:
  the APK rides the unit's flash / the Windows installer, and the
  owner sideloads it once (the setup wizard walks it, QR code to
  the local download page the host itself serves).
- A WebView app is not bound by the PWA secure-context rules; it
  can talk to the LAN host over HTTP on the shop's own network.
- Nice-to-have, not a power layer: the shell can send a
  Wake-on-LAN magic packet at the host before loading the UI.
  It is garnish on `docs/POWER-AND-WAKE.md`, never a substitute
  for Shop Mode.

**iOS — Safari bookmark (the v1 product).**

- iOS has no sideloading path for customers, so the browser is
  the route: the owner opens the host's LAN address in Safari,
  saves the bookmark, enters the pairing code once. It works;
  it does not install to the home screen with a service worker.
  v1 says exactly that.
- **Post-v1, advanced, optional:** a host-generated local CA
  profile would give the PWA a secure context on the LAN. It is
  deliberately *not* the v1 path (director's ruling): installing
  a root CA is the most trust-sensitive action in consumer
  computing — iOS presents it with warnings and buries the trust
  toggle, and a compromised host would hold a general-purpose
  certificate mint, not a StaxLine-scoped one. The least
  technical users must not be handed the most technical step.

**Desktop/other phones — plain browser on the LAN**, same
address. One UI, three wrappers.

## Scope, honestly — reaching it from across town

The full UI above is **LAN access**: the phone must be on the
shop's Wi-Fi (or the host's hotspot). Reaching it from across
town with no third-party infrastructure runs into the bootstrap
problem, stated plainly because it decides the design: a phone
on cellular and a host behind the shop router are both behind
NATs with changing addresses, so they can only find each other
if one side has a stable reachable address or a public service
introduces them. Every "just works from anywhere" product runs
that introduction service — that service *is* the third-party
infrastructure. StaxLine's answer is layered:

1. **The number is the remote (below).** The shop line itself
   is reachable from anywhere on Earth by design of the phone
   network. Staff direct the agent by texting and calling it —
   no internet, no app, no relay. This carries *operation*
   (notify, approve, query, command), not the full UI.
2. **Full UI via the owner's own WireGuard**, when the shop
   connection offers a reachable address (a public IPv4 with
   one forwarded port, or working IPv6). Keys live on the two
   devices; the setup wizard tests which case the shop is in
   and says honestly when neither is available.
3. **LAN**, as above, always available in the shop.

There is no relay, no account, and no server of ours in any of
these paths — that's the point of the product, and its limit is
stated rather than hidden.

## The text line is the primary interface (owner ruling, 2026-11-03)

The web UI is **not** the product's front door. Tonight's live
test made the reason physical: reaching even a LAN page from
the owner's phone failed on a host firewall — and a shipping
product cannot ask a shop owner to open ports, both because
most won't know how and because an open port is attack surface
the product shouldn't create. So the ruling: **the registered
admin must be able to pilot the whole system by SMS** — drafts
to approve, updates pushed out, commands in — the same way the
owner talks to his own agent today: a conversation, in both
directions, over the text line between the human and the
agent. The web UI remains as in-shop tooling on the host's own
screen (and the LAN for those who want it), but nothing
essential may live only behind it. Any feature that can't be
driven from the text line isn't finished.

## Staff contacts: identity by number (owner design, 2026-11-03)

Staff are **registered contacts**: a person becomes staff by
their mobile number being saved as one, with a role — `admin`
(the owner / whoever runs the unit), `lead`, `staff`. The
business chooses how many numbers to register: one admin number
only, or the whole crew. Defaults ship sensible; nobody has to
configure a permissions matrix.

Because the line itself distinguishes senders, a message from a
registered number is a *staff instruction*, and a message from
any other number is a *customer conversation*. The agent never
has to guess which kind of conversation it is in — and that
classification is also what the per-artist scope keys off: a
text from an artist's registered number is their scope.

**Permissions are enforced by the router, never by the model.**
A deterministic layer checks role → capability before anything
acts; the small local model is never asked to judge who may do
what (it would be the weakest link). The model only receives
"the sender is staff, role: lead" as context for tone and
scope. Default bundle:

- All staff: get alerts for their scope, claim a conversation
  (the agent goes quiet on it), file notes/memories by texting
  them, query status.
- Lead: plus approve held drafts, open/close shop modes
  (walk-ins today, after-hours), broadcast a note to staff.
- Admin: plus register/remove staff numbers, lockdown (all
  sending stops), de-register a lost phone, change the
  step-up PIN.

**Number identity, honestly hardened.** Caller/sender numbers
can be spoofed, so the stakes decide the proof: low-stakes
reads (status, summaries) ride on the number alone; approvals
are bound to content — the alert shows the exact draft text,
and "OK" approves *that text*, nothing else; sensitive commands
(lockdown undo, staff changes, PIN) require the step-up PIN.
Every staff command lands in Activity with the number it came
from.

**What the staff channel gives the shop:**

- *Run the shop from a pocket.* Approve drafts from anywhere;
  morning brief (today's bookings, held drafts, yesterday's
  misses) pushed to staff numbers; end-of-day recap the same
  way. Absence of the morning brief is itself the alarm that
  the host is down.
- *Routing with a human in reach.* A hot lead texts in; the
  agent alerts the artist whose scope fits; the artist claims
  it or sends it back; the agent never double-handles a
  claimed thread.
- *Presence.* Staff text IN / OUT / OPEN; the agent knows who
  is in, which powers honest walk-in behavior and routing.
- *The fastest memory capture there is.* "REMEMBER: …" /
  "CORRECT: …" from a staff number is the highest-trust memory
  source (staff statement) — no app to open, no screen to find.
- *Safety nets.* LOCKDOWN from any lead/admin number freezes
  outbound instantly; a lost staff phone is de-registered from
  another registered number.
- *Zero install for staff.* The interface is the messaging app
  already on their phones; onboarding is "save this number,
  text HELLO."

The same identity works on the voice side: a call from a
registered number reaches owner mode (PIN-gated) — hear today's
voicemails, hear a held draft read aloud, approve by keypad —
for the drive between shops.

## Security posture on the LAN

- The local API requires a pairing token: first connection from
  a new device shows a short code on the host's screen, entered
  once on the phone. No token, no data — a customer on shop Wi-Fi
  must not be able to open the front desk.
- Accepted v1 risk, stated plainly: on plain HTTP the pairing
  token and session traffic are sniffable by another device on
  the same LAN. The shop LAN is the trust boundary in v1; shops
  with untrusted guest Wi-Fi should keep the host on a private
  SSID/VLAN (a setup-checklist line, not a feature).
- The CA profile and token flows are one-time setup steps; the
  wizard verifies each with a live check ("your phone is
  connected") before setup completes.
