# D04.1 Structure system security

## Bounded behavior

Structure services exposes the original four system-security choices: High
Security, Low Security, Null Security and W-Space. Ships are unavailable. EOS
owns all resulting rig modifiers; Kotlin does not recalculate bonuses. This
slice does not add pilot security, environmental effects or shared profiles.

`system_security_details(fit_id)` returns version, fit ID, current revision,
`is_structure`, current `system` enum name and ordered `{id,label}` choices.
Choices are empty for ships. The read does not persist or advance history.
`set_system_security {fit_id,system}` uses the ordinary session/revision envelope
and atomic graph publication, with undo/redo and restart support. Unknown names,
wrong types, stale requests and ship edits are rejected. A same-choice request
changes neither saved fit content nor history; the existing ordinary transaction
still publishes and advances revision. The UI avoids submitting the current choice.

## Source fidelity and persistence boundary

Source: `gui/builtinContextMenus/fitSystemSecurity.py`,
`gui/fitCommands/calc/fitSystemSecurity.py`,
`gui/fitCommands/gui/fitSystemSecurity.py`, `eos/saveddata/fit.py`, and EOS effect
6672 (`structureCombatRigSecurityModification`). The original getter determines
the checked/no-op state. The calculation assigns the selected enum; publication
flushes and recalculates without filling empty modules. The surrounding graph
transaction owns durable commit and failure recovery.

Current FitSpec already requires an explicit system-security enum and numeric
pilot security. Capture now reads live system security instead of retaining the
old spec value, leaving the pilot input untouched. ORM-refreshed integer enum
values are accepted. The original getter's nullable default remains queryable as
Null Security; unexpected raw None during durable capture is rejected rather
than silently converting inherited state to an explicit saved choice. No saved
schema expansion or nullable-input support is claimed.

## Verification boundary

Synthetic Fortizar with Standup L-Set Target Acquisition Array I, ONLINE, all-5
skills, exercises actual security-modified scan resolution and targeting range.
Available pinned logical database SHA-256:
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
Independent source comparison and host/runtime/compile results are recorded in
the current artifact receipt. Instrumentation compilation is not device execution.
The source is reconstructed public base plus exported dirty work, not a claim of
an untouched pinned Git checkout. Ten frozen inspector fixtures and Android
runtime/physical-device qualification remain owner-deferred. C03.2 is not rerun.
