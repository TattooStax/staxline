# StaxLine (working name)

A one-time-buy, entirely local AI phone system for small appointment
businesses — tattoo studios, nail salons, hair salons, barbershops
first; trades later.

**The product in one paragraph:** a branded USB unit (a Waveshare
SIM7600G-H cellular modem in a printed case, combined with the
installer on built-in flash) plugs into a computer the shop already
owns. The app runs on that computer. An on-device agent (Liquid AI
LFM family) answers calls and talks, handles SMS, and holds drafts
for staff approval. No cloud AI, no subscription, no required
backend. The physical board is also the license: the app is tied to
that unit's modem.

**Status: planning + walking skeleton.** The plan in `docs/` is the
direction of record. The only code is a zero-dependency Python
server serving the UI shell, so the shape can be run and seen.
No telephony, inference, or modem feature is implemented yet, and
nothing here should be read as if it were. The first milestone is
a proof, not a feature: one real phone call answered by the agent
through the dongle on a Windows host (see `docs/PLAN.md`).

## Start here

- [`docs/PLAN.md`](docs/PLAN.md) — product, decisions, milestones
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — runtime, UI,
  modem, and inference layers
- [`docs/MEMORY-DESIGN.md`](docs/MEMORY-DESIGN.md) — how local
  records and agent memory work
- [`docs/REMOTE-ACCESS.md`](docs/REMOTE-ACCESS.md) — Android and
  iOS access without anyone's cloud (the TWA question, answered)
- [`docs/POWER-AND-WAKE.md`](docs/POWER-AND-WAKE.md) — how the
  system survives the host computer falling asleep
- [`docs/GAPS-AND-RISKS.md`](docs/GAPS-AND-RISKS.md) — the known
  unknowns, ranked
- [`docs/DIRECTOR-TAKE.md`](docs/DIRECTOR-TAKE.md) — the director's
  independent take on this plan
- [`AGENTS.md`](AGENTS.md) — working rules and the skills pointed
  at this project

## Run the skeleton

```sh
python3 -m staxline          # serves http://127.0.0.1:8787
python3 -m unittest discover # smoke tests
```

## Sibling project

`TattooStax/inkPilot` is the Android single-APK direction for the
same studio problems. StaxLine is the separate host + USB-modem
product. They share ideas and discipline (local-first, held drafts,
plain-language memory, the file-size ratchet); they are not the
same codebase.

License: GPL-3.0 (see `LICENSE`), matching the lineage of the
SMS/modem work this builds on.
