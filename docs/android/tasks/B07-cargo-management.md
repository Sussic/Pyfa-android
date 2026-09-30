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

## B07.2 selected — 2026-09-27

Branch `codex/b07-2-cargo-actions` starts from delivered master `062e8e09`.
Deliver selected-stack quantity/removal (including zero-to-remove), original
ammunition presets, fill boundaries and selected variation merging. Audit original
GUI/context commands as well as EOS edits so target order, no-ops, history and
quantity behavior are retained. Acceptance requires independent command/raw-value
fixtures and repeat, atomic malformed/stale/write-failure behavior, durable copy
and fresh restart, native touch and screenshot review, and final-head CI/PR merge.
B07.3 retains fitted module/charge transfers; B09 retains undo/redo.

## B07.2 implementation and review

The new serialized cargo actions preserve selected order, zero-to-remove without
recent promotion, explicit removal history, x8 scan probes/x1000 other ammunition,
original base-volume fill truncation, variation family filtering and stack merges.
Touch controls expose multi-selection, a shared quantity, presets, fill and choices.
Independent original commands repeat five cases/37 states. Three focused host
tests pass exact cargo/history/menu choices, synthetic null/zero/negative volume
guards, stale/malformed rejection, overflow/partial-edit rollback, failed saves,
copy and 11-fit fresh restart. Kotlin/main and instrumentation compilation pass.
Positive existing-stack fill was added during review; the refreshed fixture/repeat
and affected host checks pass. Both final local APKs, lint and package inspection
pass (160 sources, pinned dataset, licenses, ARM64/x86_64). Native
execution/screenshots and final-head CI remain.

The original market ammunition preset has no crystal exception: Multifrequency S
adds 1000. F04.02's exception remains in scope for the fitted charge transfer audit
in B07.3; it is not silently applied to this distinct market action. B07.2 retains
all inherited native/host checks and adds actual touch sequences, typed options,
raw histories/cargo values, ten new/copy fits and a separate process restart.

Reproduce with the installed reference/headless Python environments respectively:
`python -I tools/android_reference/cargo_actions.py --source <pinned-checkout> --database <verified-eve.db> --output <new-external-directory> --check tools/android_reference/fixtures/cargo-actions.json`
and `python -I tools/android_headless/check_cargo_actions.py --source <pinned-checkout> --database <verified-eve.db> --output <new-external-directory>`.
`android/ci/check-cargo-actions.py` runs the two native phases after the inherited
cargo-stack gate. Counts and prepared checks are not evidence of native success.

Head `7ef87f71` passes Windows/reference run 36284141825 in 25m26s, including
the repeated five-case/37-state fixture and three focused tests. Native run
36284141813 passes inherited phases through B07.1, then fails B07.2 preparation:
the hidden non-ammunition preset case used one browser Back tap and remained in
search results; a later cargo Back assertion found no node. The retained failure
screen confirms that navigation state. The test now explicitly leaves selected
item, search results and market root, and asserts cargo visibility after actions.
The two reached cargo screens (selected quantity and 1000-crystal preset) were
reviewed; remaining native states, restart and final screenshots are unverified.

Head `afe469ef` passes Windows/reference run 36286236788 in 26m35s. Native run
36286236863 passes inherited phases and the new preparation actions, then fails
the restart library comparison (`root.data expected 11, actual 1`). B07.2's phase
flag was omitted from `DiagnosticTestRunner`, which selected ephemeral diagnostic
storage for both processes. The flag is now registered alongside existing durable
phases, with enabled/opened-existing persistence and 47/57 fit-count entry guards.
Corrected instrumentation Kotlin compilation passes in 1m10s.
This strengthens the existing durable-restart gate; product storage is unchanged.
The one-day artifact expired before the September 30 resume, so its screenshots
and raw report cannot be reviewed. The failure is retained in CI logs; a corrected
native run is required for durable results and final screenshot review.

## B07.2 delivered — 2026-09-30

[PR #30](https://github.com/Sussic/Pyfa-android/pull/30) merged as `83f1df74`,
tested head `c3e14b29`, with the same tree `3aa6a705` as CI checkout `de7e98ac`.
[Windows/reference](https://github.com/Sussic/Pyfa-android/actions/runs/36645030741)
passes in 27m24s; [Android/native](https://github.com/Sussic/Pyfa-android/actions/runs/36645030743)
passes in 40m23s. Five original cases/37 states, three focused host tests, all
inherited gates, ten new/copy and 57 restored fits, eight protocol guards, both
APKs/lint/signature/data/licenses/ABIs pass. All six final cargo screens plus
affected existing market/charge/stack screens were reviewed; artifact digest and
tested tree match. Seventeen deliberate report corruptions are rejected.
[Receipt](../evidence/b07-2-native.json) and [raw report](../evidence/b07-2-cargo-actions-native.json)
retain exact evidence and device limits. B07.3 is ready; B07 remains active.

## B07.3 selected — 2026-09-30

Branch `codex/b07-3-fitted-transfers` starts from delivered master `3ab2e3a3`.
Deliver selected fitted module/charge move/copy to cargo and fitting from cargo,
preserving original swap, quantity, legality, state and charge semantics. Audit
the fitted-ammunition crystal exception as well as module transfers. Independent
original command fixtures/repeat, raw values/history, atomic invalid/write-failure
handling, copies/fresh restart, native touch/screenshots and final-head CI/merge
are required. Register the new durable test phase explicitly in the runner.
B09 retains undo/redo; later addition editors retain their inventory rows.

### B07.3 reference findings and atomic-rejection decision

Original transfer commands copy/move full EOS magazine counts, even when cargo
contains fewer charges; replacement returns unloaded or surplus charges and takes
available additional charges. Laser/mining crystals and scripts transfer one in
the audited cases. Market presets remain x1000 for crystals. Original transfer
commands permit structure modules in cargo despite the market action restriction.

The unchanged desktop oracle exposes a failure defect: moving a cargo module into
an incompatible empty slot can remove it, undo the batch, then call `undoAll` again
and double the stack while returning false. Rejected commands may also reorder
stacks through removal/re-addition. Android must retain the required atomic graph
rejection rather than reproduce failed-edit quantity corruption. Keep the raw
desktop failure in the fixture; check Android rejection against the independently
recorded preceding state, including unchanged quantities and history. Successful
transfers compare desktop values; cargo display order is not transfer semantics
(desktop sorts it in CargoView). This is a recorded correctness correction, not
an omitted parity check or an altered independent expected quantity.

### B07.3 implementation and focused verification

Build 25 adds revision-bound transfer details and typed move/copy operations with
selected-module batches, optional swaps, charge reconciliation and state fallback.
The touch editor preserves selection through recreation and clears stale choices
on fit/revision changes. The new native phase is explicitly registered for durable
storage and starts with 57 inherited fits; 28 new/copy fits must restore as 85.

Independent original commands repeat 14 cases/80 states: loaded move/copy, swaps,
magazine adjustment and shortage, incompatible targets, full charge magazines,
laser/mining crystals, scripts, structures, rigs, subsystems and selected modules.
Four focused host tests pass these successful states, independently recorded
pre-failure values, malformed/stale requests, overflow, partial-edit rollback,
failed writes, copies and 29-fit process restart without desktop/network imports,
plus native fixture setup through real bridge operations. Main and instrumentation
Kotlin compilation, both APKs, lint and package inspection pass, including the last
UI callback guard (1m08s build/lint). Native execution, six screenshot
reviews, final-head full CI, review and merge remain required; prepared checks are
not evidence of native success.
