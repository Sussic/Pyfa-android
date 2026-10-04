# Android project status

Updated: 2026-10-04. **C02 delivered; C03.1 active.**

The authorized goal continues sequential ready, approved work through review,
local verification and fork delivery. Preserve completed W02 setup; no hosted
workflow dispatch, delegation, releases, phone installs or billing changes.

## Current outcome

`codex/c03-targeting-attributes`, selected from master `b88713b3`; no open PR.
C03.1 implements F07.01–F07.30 targeting/navigation and all21 cargo holds using
serialized EOS and the independently pinned original wx view. C03.2 retains full
item inspection. [Task](tasks/C03-targeting-attributes.md) owns the matrices,
source review and failure history; [roadmap](ROADMAP.md) owns delivered scope.

Candidate `bfbbe157`, full run `20261004-042857-bfbbe157-2dd1cc`, stopped after61
passing reference/host gates. All fresh desktop exports and host calculations,
GC/history/copy/restart checks passed. `headless:targeting` completed its two engine
processes but its validator subprocess exceeded the unchanged60-second deadline.
Raw logs/partial proof are retained; build/native gates have not begun in this run.

Selected **C03.1.2 validator metadata indexing** is implemented: one diagnostic
summary falls from13.68 to1.61 profiled seconds;30 million repeated prefix checks
were the hotspot. All16 original validators plus prefix-equivalence regression
pass in21.5 seconds within the unchanged60-second deadline. Twelve exact-source
guards pass, rejecting assertion/deadline/fixture/engine/app changes. Commit and
validate reuse of61 completed gates through the existing launcher/reporter; rerun
the failed gate and all remaining build/native/screenshot requirements.

Keyboard repair C03.1.1 passes5 build gates,5 geometry validators and focused
native run `c031-keyboard-focused-20261004-042420` with3 hash-verified reviewed
screenshots, including recreation and keyboard dismissal. Earlier full run
`20261003-150233-9badd3ec-e6ca98` paused on `aefc6faf` after78 gates when visual QA
found status-bar overlap. Those native results are historical after the app fix.
Exact next: diagnose/fix validator cost, prove unchanged61 inputs, then finish
115 required gates/75 native executions/325 fits and215 screenshot reviews.

## Delivered work

W02 and B09.1 [PR #33](https://github.com/Sussic/Pyfa-android/pull/33) remain closed;
B09.2 [receipt](evidence/b09-2-native.json) preserves history disposition. C01 is
closed through [resources](evidence/c01-1-native.json),
[capacitor](evidence/c01-2-native.json), [defenses](evidence/c01-3-1-native.json) and
[tank](evidence/c01-3-2-native.json). C02 [PR #40](https://github.com/Sussic/Pyfa-android/pull/40)
passed109 gates/71 native executions/268 fits/191 screenshot reviews; its
[receipt](evidence/c02-native.json) binds actual commits and retained proof.
Earlier A/B milestones remain closed in their task/evidence files and ROADMAP.

## Execution and limits

Use the installed [local launcher](LOCAL-VERIFICATION.md),
`build/windows-env.ps1` and ignored `build/WINDOWS-CHECKPOINT.md`. Never edit the
tracked candidate during a run. Preserve every inherited gate and A10 requirement.
Kotlin/Compose + Chaquopy + serialized EOS remain within accepted A10 limits;
[scope](SCOPE.md), [architecture](ARCHITECTURE.md) and [evidence rules](DEVELOPMENT.md)
apply. Both ABIs are packaged; API36 x86_64 native proof is separate from ARM64,
older-API, signing/upgrade and user-usability acceptance. Full parity is unproven.
