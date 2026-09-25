# B06 — Hull-specific configuration

## Outcome and boundaries

Deliver F02.06–F02.08 using pinned EOS and the existing Kotlin/Compose,
Chaquopy, serialized bridge and offline graph store. B04 already creates empty
ship/structure fits and edits ordinary/service modules. B06 completes the
hull-specific mode, subsystem and structure interactions. B09 retains undo/redo;
D04 retains structure system-security choices. Full parity remains open.

| Child | Owned behavior | Acceptance outcome |
| --- | --- | --- |
| B06.1 | Tactical and supported other ship modes | Exact hull-specific choices; original mode-change/reversal and independent stats; strict typed edit, atomic store, touch UI and fresh-process reopen. |
| B06.2 | Strategic-cruiser subsystems | Original add/replace/remove ordering and variable slots; reconcile legality, charges/states and bonuses, with durable native evidence. |
| B06.3 | Structure-specific service/restriction/bonus behavior | Independent structure fixture and native service-slot controls, including boundaries already started in B04. |

## B06.1 selected scope and audit

Selected 2026-09-25 on `codex/b06-1-hull-modes` from delivered master
`5991fe99`. The pinned `shipModeChange` menu reads `fit.ship.modes` and selects
one of that hull's mode items. Its command replaces `fit.mode`, flushes,
recalculates, fills and commits; its inverse restores the prior item. EOS
`Ship.validateModeItem` supplies a default only for tactical destroyers and
Anhinga. The current bridge creates that default but does not include the
chosen mode in its declarative stored graph, so B06.1 must retain it across
copy/restart and reject cross-hull choices rather than accept EOS fallback.

- [x] Execute original pinned mode choices and switch/reversal;
  record source/data/settings, raw values, units and justified tolerance.
- [x] Add strict mode choice/edit protocol and graph persistence with atomic
  rejection and fresh-process host cases.
- [ ] Expose touch selection and current/default state; verify native offline
  change, fit switch, copy and real process restart with reviewed screenshots.
- [ ] Pass final-head Windows/reference and Android/native CI, inspect artifact
  provenance, review and merge the focused PR. Refresh status/forecast.
