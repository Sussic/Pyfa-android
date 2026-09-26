# B07 — Cargo management

Deliver F04.01–F04.05 on the pinned desktop reference and retained
Kotlin/Compose, Chaquopy and serialized EOS architecture. Selected 2026-09-26
on `codex/b07-1-cargo-stacks` from delivered master `8388f236`. The audit found
that original calculation commands merge stacks by item ID and alter amounts,
while context commands separately calculate ammo presets/fill-to-capacity and
module/charge transfers. At selection, the saved Android fit graph had no cargo
field; B07.1 now persists it. B09 owns undo/redo, including cargo actions.

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

## B07.1 preparation and corrections

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

Head `47730b9e` passed Windows/reference CI (36273104083, 27m13s), while native
run 36273104092 passed the inherited suites and cargo preparation, then failed
the new restart assertion: JSONObject serializes integral doubles as integers.
The correction uses the existing typed report wrapper, retaining exact numeric-kind
metadata across serialization alongside the value comparison. Six cargo screens
from the failed run were inspected; quantity actions now clear keyboard focus and
use numeric input. A corrected final-head native run is still required.

Head `78e06c26` passed Windows/reference CI (36275744985, 25m18s). All native
instrumented phases, including typed cargo restart, passed in run 36275744990;
its report validator then failed by applying the desktop-only absent-gun mapping
to two already-native null values. The validator now compares native records
exactly, retaining the mapping only for independent desktop comparisons. Local
validation of both retained phases passes all 17 states, three new/47 restored
fits and six protocol guards; twelve deliberate report corruptions are rejected,
including null replaced by zero and changed restart numeric-kind metadata.
Final-head CI and delivery remain required.

## B07.1 delivered — 2026-09-27

[PR #29](https://github.com/Sussic/Pyfa-android/pull/29) merged as `fd80b2fc`,
tested head `bc06de79`, with the same tree `2437d335` as CI checkout `5a5711f5`.
[Windows/reference](https://github.com/Sussic/Pyfa-android/actions/runs/36277865653)
passes in 25m24s; [Android/native](https://github.com/Sussic/Pyfa-android/actions/runs/36277865678)
passes in 35m37s. Both original cases/17 states, three focused host tests,
all inherited gates, both APKs/lint/signature/data/licenses/ABIs, three new/47
restored fits, six protocol guards and twelve corruption probes pass. All six
final cargo screenshots were reviewed; artifact digest and tested tree match.
[Receipt](../evidence/b07-1-native.json) and [raw report](../evidence/b07-1-cargo-stacks-native.json)
retain evidence. B07.2 is the exact next task; the parent remains active.
