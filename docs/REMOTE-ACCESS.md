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
- Bonus: the shell can send **Wake-on-LAN** — when the owner opens
  the app and the host is asleep, the phone fires a magic packet
  at the host's MAC before loading the UI (see
  `docs/POWER-AND-WAKE.md`, Layer 2/3).

**iOS — PWA with a one-time local CA (primary path).**

- iOS has no sideloading path for customers, so the web app is
  the only route. To give it a secure context, the host generates
  a **local certificate authority** at install time; the setup
  wizard has the owner install that CA profile on the iPhone once
  (a standard iOS settings flow, ~1 minute), after which the host
  serves the UI over HTTPS *on the LAN* with a locally-issued
  certificate the phone trusts. Add-to-Home-Screen then works
  like any PWA.
- The CA's private key never leaves the host. Nothing is fetched
  from the internet at any point.
- **Fallback:** skip the CA and use a plain browser bookmark over
  HTTP — the UI still works in Safari; it just doesn't install
  to the home screen or run a service worker. Setup offers both,
  honestly labeled.

**Desktop/other phones — plain browser on the LAN**, same HTTPS
(or HTTP fallback) address. One UI, three wrappers.

## Scope, honestly

This is **LAN access**: the phone must be on the shop's Wi-Fi
(or the host's hotspot). Reaching the system from home or the
road would require a tunnel or VPN — the supported answer there
is the owner's own self-hosted WireGuard, documented as an
advanced option, never a StaxLine cloud. There is no relay, no
account, and no server of ours in the path — that's the point of
the product, and its limit is stated rather than hidden.

## Security posture on the LAN

- The local API requires a pairing token: first connection from
  a new device shows a short code on the host's screen, entered
  once on the phone. No token, no data — a customer on shop Wi-Fi
  must not be able to open the front desk.
- The CA profile and token flows are one-time setup steps; the
  wizard verifies each with a live check ("your phone is
  connected") before setup completes.
