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
- [x] Expose touch selection and current/default state; verify native offline
  change, fit switch, copy and real process restart with reviewed screenshots.
- [x] Pass final-head Windows/reference and Android/native CI, inspect artifact
  provenance, review and merge the focused PR. Refresh status/forecast.

B06.1 delivered in [PR #26](https://github.com/Sussic/Pyfa-android/pull/26),
merge `7f08c3d8`, tested head `90688456`. [Windows/reference CI](https://github.com/Sussic/Pyfa-android/actions/runs/36116275320)
and [Android/native CI](https://github.com/Sussic/Pyfa-android/actions/runs/36116275344)
pass. The [receipt](../evidence/b06-1-native.json) retains provenance and limits;
four mode screenshots were reviewed. Exact next child: B06.2 strategic-cruiser
subsystems.

## B06.2 selected scope and audit

Selected 2026-09-25 on `codex/b06-2-subsystems` from master `c102ae09`.
The pinned desktop fitting view sends subsystem market additions through
`CalcAddLocalModuleCommand`. That command replaces an occupied subsystem type
through `CalcReplaceLocalModuleCommand`; removals run the original local remove
command. EOS owns the type restriction, subsystem bonuses and slot counts;
`Fit.fill` adds/removes only vacancies after recalculation. The existing bridge
already stores subsystem vacancies and decodes their slot but deliberately
blocks their ordinary editor. B06.2 adds a dedicated typed editor and must
preserve exact module order, legality and non-subsystem state/charge behavior
when available slots change.

The original command audit now repeats one Tengu sequence with 14 states in
fresh processes and enumerates 12 choices for each of the four T3 hulls (none
for Vexor). Removing the offensive subsystem retains a charged, ACTIVE Heavy
Missile Launcher II despite its HIGH slot and launcher hardpoint totals falling
to zero; EOS marks it illegal and restores legality on re-add. Saved/copy replay
must retain that visible invalid fit instead of discarding the launcher or
fabricating a legal state.

- [x] Export a focused pinned desktop add/replace/remove/reversal matrix for a
  strategic cruiser, with source/data/settings, raw values, slots and tolerances.
- [x] Implement strict subsystem choices/edits, atomic rejection and durable
  graph replay; compare all original states and fresh-process copies on host.
- [x] Verify touch controls, dynamic slots, warnings and offline process restart
  in native instrumentation; inspect changed screenshots and package contents.
- [x] Pass final-head Windows/reference and Android/native gates; review and
  merge the focused PR, retain evidence and refresh status/forecast.

[PR #27](https://github.com/Sussic/Pyfa-android/pull/27) merged as `8e4b085e`,
tested head `b1473e47`; [Windows/reference CI](https://github.com/Sussic/Pyfa-android/actions/runs/36127361579)
passed in 25m49s and [Android/native CI](https://github.com/Sussic/Pyfa-android/actions/runs/36127361376)
passed in 27m51s. Fourteen native raw states, 48 choices, six protocol guards,
three new/37 restored fits and real offline restart passed. All six new
screenshots were reviewed. The [receipt](../evidence/b06-2-native.json) and
[raw report](../evidence/b06-2-subsystems-native.json) retain artifact and
matching CI/merge-tree provenance. Next child: B06.3 structure controls.
