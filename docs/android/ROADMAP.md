# Android task queue

This file owns task status. Start with the first ready task whose dependencies are
done. Only one task is active by default. States: `ready`, `queued`, `active`,
`blocked`, `done`. A queued task becomes ready when its listed dependencies are
verified. Completed setup documentation is not an implementation milestone.

Each row is a bounded outcome with a minimum acceptance check, not a license to
omit related Pyfa behavior. Before implementing a row, expand it with the
[task template](../../.github/ISSUE_TEMPLATE/android-task.md) in the PR, issue or a
task brief. If it cannot fit one focused review, split it into child tasks first.
A02 will refine feature coverage and add missed behaviors; it cannot reduce scope.
Early dependency requirements are ordering constraints, not claims of feasibility.

## A — prove the calculation engine and native build

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| A01 | done | — | [Reproducible desktop reference](tasks/A01-desktop-reference.md) | Clean Python 3.11 setup generates pinned game data and records meaningful raw values for one synthetic fitted ship; exact commands and data hash are reproducible. |
| A02 | ready | A01 | Expand the parity inventory | Desktop controls, context menus, settings, all stat/graph families and import/export paths map to observable behaviors, source locations and tasks; gaps stay explicit. |
| A03 | ready | A01 | Minimal headless adapter | One fitted ship calculates without wx/UI initialization; required dependencies, import order and data paths are documented; raw values match A01. |
| A04 | queued | A03 | Projected-effect reference cases | A pinned desktop source/target case records apply, range/state change and remove results; adapter agrees and restores original values on removal. |
| A05 | queued | A03 | Command-burst reference cases | A real booster/source fit and recipient produce matching results with skills/implants/state changes; disabling/removing the command source restores baseline. |
| A06 | queued | A03 | Android skeleton and native CI | Pinned toolchain builds an installable APK; an emulator test executes a real app assertion; deliberate APK delivery, concurrency, timeouts and retention are configured. No engine parity claim yet. |
| A07 | queued | A06 | Bundle data and boot EOS on Android | Fresh offline launch calculates A01 through embedded Python; x86_64 native test passes and arm64 package contains its required native dependencies/data. |
| A08 | queued | A04, A07 | Android projection parity | A04 reference cases pass through the Android bridge, including changes/removal and stale-cache checks. |
| A09 | queued | A05, A07 | Android command parity | A05 reference cases pass through the Android bridge with correct recipient updates and cleanup. |
| A10 | queued | A02, A08, A09 | Decide embedding feasibility | Record measured startup/recalculation/memory/APK size, remaining ABI/device gaps and supported dependency pins; justify continuing or propose a viable correction. |

## B — make an editable, persistent fitting workflow

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| B01 | queued | A10 | Typed bridge operations and results | One mutation/query contract carries raw units, errors and fit revisions; engine work stays off UI thread and serialized; failed edits do not leave partial state. |
| B02 | queued | B01 | Local fit persistence | Save/reopen synthetic fits and command/projection links across process restart; transactions and relationship identity preserve results. |
| B03 | queued | B02 | Fit library screen | Create, find, rename, duplicate and remove fits using test fixtures; deletion behavior preserves or explicitly resolves references. Audit desktop organization options. |
| B04 | queued | B03 | Equipment browser and fitting | Search/filter items and fit/unfit modules/rigs/charges with appropriate legality feedback and reference-matching recalculation. |
| B05 | queued | B04 | Bulk weapon/module editing | Select compatible guns, change ammo/state or fill slots in one operation; incompatible mixed selections get clear behavior; one user action updates every intended module. |
| B06 | queued | B04 | Hull-specific configuration | Supported ship/structure modes and subsystem changes update legal slots and bonuses correctly; test a mode hull and strategic cruiser. Split further if A02 identifies distinct systems. |
| B07 | queued | B04 | Cargo management | Add/remove/change stacks and move fitted equipment/ammo to/from cargo; quantities survive restart and agree with Pyfa behavior. |
| B08 | queued | B03 | Fit notes | Edit and persist per-fit notes, including multiline/non-ASCII content, without losing unsaved text on navigation. |
| B09 | queued | B05 | Undo/redo for fit edits | Single and bulk edits undo/redo as user actions; recalculated values and selection state stay consistent after reversal. Extend through later mutation tasks. |

## C — expose the full fit inputs and statistics

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| C01 | queued | B04 | Resources, capacitor and defenses | Every audited resource/capacitor/tank field has correct units/rounding and matches raw reference results under relevant assumptions. |
| C02 | queued | B04 | Firepower, bombs and mining stats | Audited outgoing fields match representative turret, missile, bomb and mining cases; unsupported/absent values remain distinguishable from zero. |
| C03 | queued | B04 | Targeting/navigation and attribute inspector | Drone control range and all audited miscellaneous/ship/item attributes are reachable and correct; search/detail behavior works on a phone. |
| C04 | queued | B04 | Drone editing | Add/split/merge stacks, activate/select counts and respect bandwidth/limits; damage and drone control range react correctly. |
| C05 | queued | B04 | Fighter editing | Squadron quantities and ability states update statistics; save/reopen retains abilities and selected states. |
| C06 | queued | B01, B03 | Offline character profiles | All-V/custom skills can be selected, edited and saved; requirements and affectors are inspectable and bonuses match references. |
| C07 | queued | C06 | Implants and implant sets | Slot handling and applying/saving sets match Pyfa; profile changes update dependent fits. |
| C08 | queued | C06 | Boosters and side effects | Add/toggle boosters and individual supported side effects; raw results and persistence match references. |
| C09 | queued | B05 | Heat, reload and spool options | Audited state/reload/spool and adaptive-module options affect the correct stats; transitions and undo have reference tests. |
| C10 | queued | C04, B04 | Mutated items | Enter/edit rolled module and drone attributes; exact values survive saves and affect calculations without reverting to base stats. |

## D — expose interacting fits and scenarios

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| D01 | queued | B02, B04, C04, C05 | Projection editor | Add fits/modules/drones/fighters as supported, adjust range/count/state, and remove them; edited source values update every recipient correctly. |
| D02 | queued | D01 | Projection interaction coverage | Multiple sources, stacking, remote reps/capacitor and supported reciprocal links match desktop; no arbitrary cycle suppression or stale effects. Split by interaction family as needed. |
| D03 | queued | B02, C06, C07 | Command-fit editor | Select/configure command sources, their enabled states and applicable strengths; recipient results persist and match A05/A09 plus audited options. |
| D04 | queued | B04 | Environments and security modifiers | Supported wormhole/weather/site/security scenarios can be applied/removed; stacking and restored baselines match reference cases. |
| D05 | queued | C01, C02 | Damage patterns and target profiles | Create/select/edit audited profile inputs and persist them; affected tank/application values recalculate with matching assumptions. |

## G — port one graph family at a time

Each graph task includes reference-matched sample values, applicable desktop input
controls, multiple-fit comparisons, readable axes/units and a focused interaction
test. Reuse shared plotting UI after G01; do not add a new plotting framework for
each graph. Keep heavy sample calculation off the UI thread.

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| G01 | queued | D02, D05, C09 | Damage graph and reusable plot surface | Port `fitDamageStats` with audited modes and projection/target assumptions; numeric samples and touch controls pass. |
| G02 | queued | G01 | Application profile graph | Port `fitApplicationProfile`, including applicable ammo optimization and projected effects; samples match and repeated edits do not accumulate stale results. |
| G03 | queued | G01, C01 | Capacitor graph | Port `fitCapacitor`; selected time/fit inputs and sampled capacitor behavior match. |
| G04 | queued | G01, C01 | Shield regeneration graph | Port `fitShieldRegen`; sample rates and axes match. |
| G05 | queued | G01, D02 | Remote repair graph | Port `fitRemoteReps`; range/effect assumptions and sampled results match. |
| G06 | queued | G01, C03 | Lock-time graph | Port `fitLockTime`; target/fit changes and sampled times match. |
| G07 | queued | G01, C03 | Mobility graph | Port `fitMobility`; applicable input modes and sampled values match. |
| G08 | queued | G01, C03 | Warp-time graph | Port `fitWarpTime`; distances/fit assumptions and sampled times match. |
| G09 | queued | G01, D02 | Electronic-warfare graph | Port `fitEwarStats`; range and effect assumptions match. |
| G10 | queued | G01, D02 | ECM/burst/scan-resolution-damp graph | Port `fitEcmBurstScanresDamps`; audited inputs and samples match. |
| G11 | queued | G02, G03, G04, G05, G06, G07, G08, G09, G10 | Remaining shared graph actions | Verify audited overlays (including drone control/lock ranges), selections, exports and comparisons across families; split any remaining substantive feature into its own task. |

## I — interchange, optional refresh and updates

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| I01 | queued | B04 | EFT import/export and phone sharing | Paste/import/export a fit; valid states/charges round-trip as supported, and malformed input does not partially overwrite saved work. |
| I02 | queued | I01, C10, D03 | Remaining Pyfa interchange formats | Port each audited format (DNA/XML/EFS/mutation/multibuy/stats) in a child task; record unavoidable format loss rather than silently discarding attributes. |
| I03 | queued | C06, I01 | Optional character/fitting synchronization | Split login, skill refresh and fitting sync into child tasks; refresh succeeds online, cancellation/expiry is handled, and saved skills/fits remain usable offline. |
| I04 | queued | B04 | Prices and price preferences | Refresh supported sources online, retain timestamped cached values offline and preserve manual pricing options; unavailable values are not zero. |
| I05 | queued | B02 | Data refresh and user backups | Separate child tasks for dataset update and fit backup/restore; validate data before activation, retain recoverable user state and reject incompatible/corrupt imports. |
| I06 | queued | A02, C03, D05 | Remaining preferences and localization | Split the audited calculation/display/language options into small tasks; preserve semantics, units and text legibility for supported locales. |

## R — close actual gaps and deliver

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| R01 | queued | B06, B07, B08, B09, C08, D04, G11, I02, I03, I04, I05, I06 | Full parity and offline audit | Every A02 behavior maps to passing evidence; fresh offline install, restart, backup and interacting-fit scenarios pass. File each uncovered behavior as a bounded fix, not a waived check. |
| R02 | queued | A07, B02 | Stable install/update packaging | Stable signing/versioning, required notices and exact source identification are established; an install-over-previous-build test preserves fits. Complete before distributing successive persistent-use APKs. |
| R03 | queued | R01, R02 | Real-device usability review | Verify the supported phone/ABI, record measured responsiveness and user feedback on bulk edits, statistics and linked fits; turn each issue into a small fix. |
| R04 | queued | R03 | Final acceptance build | All parity, offline, update and agreed usability issues are verified closed; provide installable APK, matching source and concise release/install notes. |

R01 also requires every A–I task and its discovered child tasks to be complete
even if not transitively listed in its dependency cell. R02 can run
early once its dependencies pass; it is not deferred until the final feature audit.
