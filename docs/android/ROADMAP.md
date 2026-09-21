# Android task queue

This file owns task status. Start with the first ready task whose dependencies are
done. Only one task is active by default. States: `ready`, `queued`, `active`,
`blocked`, `done`. A queued task becomes ready when its listed dependencies are
verified. Completed setup documentation is not an implementation milestone.

The 2026-09-21 local Windows setup and workflow maintenance is tracked in
[STATUS](STATUS.md) and [Windows setup](WINDOWS.md). It does not advance B03.2,
change the feature-task counts or reduce any host/native acceptance check.

Each row is a bounded outcome with a minimum acceptance check, not a license to
omit related Pyfa behavior. Before implementing a row, expand it with the
[task template](../../.github/ISSUE_TEMPLATE/android-task.md) in the PR, issue or a
task brief. If it cannot fit one focused review, split it into child tasks first.
[The A02 checklist](PARITY.md) maps observable behaviors to delivery owners.
Read the owner's rows before expanding a task. Coverage cannot be reduced to make
a task appear finished.
Early dependency requirements are ordering constraints, not claims of feasibility.

## A — prove the calculation engine and native build

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| A01 | done | — | [Reproducible desktop reference](tasks/A01-desktop-reference.md) | Clean Python 3.11 setup generates pinned game data and records meaningful raw values for one synthetic fitted ship; exact commands and data hash are reproducible. |
| A02 | done | A01 | [Expand the parity inventory](tasks/A02-parity-inventory.md) | Desktop controls, context menus, settings, all stat/graph families and import/export paths map to observable behaviors, source locations and tasks; gaps stay explicit. |
| A03 | done | A01 | [Minimal headless adapter](tasks/A03-headless-adapter.md) | One fitted ship calculates without wx/UI initialization; required dependencies, import order and data paths are documented; raw values match A01. |
| A04 | done | A03 | [Projected-effect reference cases](tasks/A04-projection-reference.md) | A pinned desktop source/target case records apply, range/state change and remove results; adapter agrees and restores original values on removal. |
| A05 | done | A03 | [Command-burst reference cases](tasks/A05-command-reference.md) | A real booster/source fit and recipient produce matching results with skills/implants/state changes; disabling/removing the command source restores baseline. |
| A06 | done | A03 | Android skeleton and native CI | Pinned toolchain builds an installable APK; an emulator test executes a real app assertion; deliberate APK delivery, concurrency, timeouts and retention are configured. No engine parity claim yet. |
| A07 | done | A06 | Bundle data and boot EOS on Android | Fresh offline launch calculates A01 through embedded Python; x86_64 native test passes and arm64 package contains its required native dependencies/data. |
| A08 | done | A04, A07 | Android projection parity | A04 reference cases pass through the Android bridge, including changes/removal and stale-cache checks. |
| A09 | done | A05, A07 | Android command parity | A05 reference cases pass through the Android bridge with correct recipient updates and cleanup. |
| A10 | done | A02, A08, A09 | Decide embedding feasibility | Record measured startup/recalculation/memory/APK size, remaining ABI/device gaps and supported dependency pins; justify continuing or propose a viable correction. |

## B — make an editable, persistent fitting workflow

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| B01 | done | A10 | [Typed bridge operations and results](tasks/B01-typed-bridge.md) | One mutation/query contract carries raw units, errors and fit revisions; engine work stays off UI thread and serialized; failed edits do not leave partial state. |
| B02 | done | B01 | [Local fit persistence](tasks/B02-local-persistence.md) | Save/reopen synthetic fits and command/projection links across process restart; transactions and relationship identity preserve results. |
| B03 | active | B02 | Fit library screen (parent) | B03.1 and B03.2 complete; all original lifecycle and organization requirements retained. |
| B03.1 | done | B02 | [Fit lifecycle and search](tasks/B03-fit-library.md) | Create from fixtures, find, open, rename, duplicate and delete; resolve links atomically, retain independent inputs and reopen an empty library. Host and native workflow checks pass. |
| B03.2 | ready | B03.1 | Library organization and open-fit navigation | Hull group/race browsing, hide/show empty groups, back-to-hull navigation, recently modified fits and multiple open fits with close one/all and optional restart restoration; preserve F01.03–F01.05 and audit desktop preferences. |
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
| I02 | queued | I02.01, I02.02, I02.03, I02.04, I02.05, I02.06, I02.07, I02.08 | Remaining Pyfa interchange formats — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |
| I03 | queued | I03.01, I03.02, I03.03, I03.04 | Optional character/fitting synchronization — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |
| I04 | queued | B04 | Prices and price preferences | Refresh supported sources online, retain timestamped cached values offline and preserve supported pricing options; resolve the manual-price question in PARITY_AUDIT Q02. Unavailable values are not zero. |
| I05 | queued | I05.01, I05.02 | Data refresh and user backups — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |
| I06 | queued | I06.01, I06.02, I06.03, I06.04, I06.05, I06.06, I06.07 | Remaining preferences and localization — rollup | Every listed child is verified, including its assigned PARITY rows and unresolved audit dispositions. This parent is not an additional implementation task. |

## I child tasks — bounded delivery units

A02 split four broad I rows before implementation. Parent IDs remain as rollups
so existing dependencies retain their meaning; children never depend on their
own parent. A parent becomes done only when every child is done. These 21 child
rows increase the queue from 55 to 76 tracked rows: 72 work items and four rollups.
Task counts measure bookkeeping, not equal effort or a percentage of app parity.
The first ready task in the A–R order remains the default next task.

| ID | State | Depends on | One outcome | Done when |
| --- | --- | --- | --- | --- |
| I02.01 | queued | I01 | DNA interchange | Plain, chat-tagged and alternate DNA fixtures pass; supported formatting and losses are documented. |
| I02.02 | queued | I01, C10, D03 | XML interchange | Single/multi-fit XML and Pyfa extensions match supported fields; notes truncation and absent relationship/state fields are explicit. |
| I02.03 | queued | C05, D02 | EFS export | Fit/type exports match the implemented EFS schema, including weapon/fighter/projection data and unsupported-effect reporting. |
| I02.04 | queued | I01, I04 | Multibuy export | Quantities and inclusion/cheaper-equivalent options match reference exports without mutating the saved fit. |
| I02.05 | queued | C01, C02, C03 | Fit stats and item CSV export | Formatted fit reports and current/base attribute CSV retain units, assumptions and Unicode. |
| I02.06 | queued | I01, C10, C05, C07, C08, B07 | Mutation and additions clipboard interchange | Mutation text and all/selected additions round-trip their supported fields; malformed pastes preserve saved work. |
| I02.07 | queued | C06, D05 | Skills and profile interchange | Character XML, skill text/training exports and damage/target-profile clipboard formats preserve supported values and validate errors. |
| I02.08 | queued | I01, B02 | HTML fit collection export | Styled/minimal collection exports contain correct fitting links/data and work through Android file sharing. |
| I03.01 | queued | C06 | Android ESI sign-in and identity management | Supported authentication return path, character selection/removal, cancellation/expiry and offline startup are verified; desktop server/token preferences have an explicit disposition. |
| I03.02 | queued | I03.01, C06 | Character skill refresh | Linked-character refresh updates skills/security; failures retain cached values and do not silently discard pending edits. |
| I03.03 | queued | I03.01, I01 | ESI fittings and JSON interchange | Browse/import/upload and explicitly confirmed remote deletions work; JSON losses and inclusion options are documented; local fits remain usable offline. |
| I03.04 | queued | C10 | Dynamic mutated-item link resolution | Supported online item links resolve exact rolls that persist offline; malformed/unavailable links preserve the current fit. |
| I05.01 | queued | A10, B02 | Dataset refresh and recovery | Validate a pinned update before activation; interrupted/corrupt/incompatible data leaves user state recoverable and calculation offline. |
| I05.02 | queued | B02, C06, C07, D05, I02.02 | User backup, restore and database maintenance | Complete Android backup scope is explicit and tested beyond lossy XML fit export; corrupt restore and clearing referenced profiles are handled safely. |
| I06.01 | queued | C06, C07, C09, D05 | Calculation/default preferences | Reload/spool, strict skill prerequisites, global character/pattern and default implant settings persist and update all affected fits. |
| I06.02 | queued | B05, B08, C03, C10 | Display and interaction preferences | Audited statistics, rack/details, context actions and market/meta controls have persistent touch equivalents and remain discoverable. |
| I06.03 | queued | A07, C03 | UI and game-data localization | Enumerate/pin available locales; bundled UI/data languages, fallback, formatting and Unicode work offline. |
| I06.04 | queued | B01, C03 | Attribute overrides | Edit/toggle/remove/import/export global overrides with exact recalculation/restoration and safe invalid CSV handling. |
| I06.05 | queued | I03.01, I04 | Network and proxy controls | Master/per-service controls and supported proxy behavior work on Android; local calculations never depend on refresh. |
| I06.06 | queued | A06, C03 | Diagnostics, notices and help | Source/version/notices/help and privacy-preserving diagnostic export are reachable; desktop-only tools have documented equivalents or a recorded product decision. |
| I06.07 | queued | R02 | Optional app update notifications | Personal-build delivery equivalent supports prerelease/suppression/download choices or records an explicit product decision; no store/backend requirement is introduced. |

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
