# B07 — Cargo management

Deliver F04.01–F04.05 on the pinned desktop reference and retained
Kotlin/Compose, Chaquopy and serialized EOS architecture. Selected 2026-09-26
on `codex/b07-1-cargo-stacks` from delivered master `8388f236`. The audit found
that original calculation commands merge stacks by item ID and alter amounts,
while context commands separately calculate ammo presets/fill-to-capacity and
module/charge transfers. The saved Android fit graph currently has no cargo
field. B09 owns undo/redo, including cargo actions.

| Child | Outcome | Acceptance boundary |
| --- | --- | --- |
| B07.1 | Cargo stacks and quantities | Persist cargo in declarative fit graph; add/remove/change stack amounts; show EOS used/capacity values; compare original commands and native copy/restart. |
| B07.2 | Selected-stack actions, presets, fill and variations | Match original multi-selection quantity/removal (including zero-to-remove), x8/x1000 ammunition presets, fill capacity and selected variation quantity merges. |
| B07.3 | Fitted transfers | Move/copy modules and charges between fit and cargo with original swap, charge and legality behavior. |

- [x] Audit original stack, quantity, ammunition preset, fill-capacity,
  fitted-module transfer and variation command boundaries; split children.
- [ ] For each child, export independent desktop cases/raw values and compare
  focused host behavior, rejection, failed saves, copy and fresh restart.
- [ ] Verify touch controls, volumes/quantities, package and offline restart in
  native instrumentation; inspect changed screenshots.
- [ ] Pass final-head Windows/reference and Android/native gates per child,
  review/merge focused PRs, retain evidence and update status/forecast.

## B07.1 active evidence

The original pinned cargo commands repeat two hull cases/17 states in fresh
processes, including same-item merging, partial and full removal, precise EOS
volume, over-capacity Vexor and charge cargo on zero-capacity Astrahus. Three
focused host checks pass all states, rejection, old graph replay, failed-save
recovery and fresh copy/restart. The new typed query and touch editor add cargo
to the durable graph without altering EOS formulas. Local Kotlin/native-test
compilation, debug/test APK assembly, lint and package inspection pass. Native
offline execution, screenshots and final-head CI remain.

Review tightened native evidence: the Vexor touch removal now sends the exact
10,000-unit reference request (clamped by EOS), structure removal uses the
remove-stack control, and all three new fits retain complete cargo states for
fresh-process comparison. Local instrumented Kotlin compilation passes. Final-head
CI remains required. F04.01 is only partially covered by B07.1: the desktop
`GuiChangeCargosAmountCommand` applies one quantity to multiple selected stacks
and removes them at zero. B07.2 explicitly retains these selection capabilities
alongside its selected variations; B07 cannot close without them.
