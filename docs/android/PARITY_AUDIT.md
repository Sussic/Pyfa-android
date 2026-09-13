# A02 source audit and open questions

Audited 2026-09-12 at desktop commit `8b04f3b271e614b3e103853b44a7851a63d79d0e`. The deliverable is the
[behavior checklist](PARITY.md), not a running Android app. All 239 rows remain
unimplemented on Android. Source links are fixed to this revision.

## Review method and boundary

Read the menu registrations, fit/addition commands, statistic refresh paths,
item-detail panels/columns, graph definitions/getters, preference registrations,
and interchange routing/options. Cross-check names and controls against their
service/EOS entry points. In particular, inspect the data behind tooltips and
context actions instead of inventorying only panel titles.

The control index below accounts for every non-initializer Python file in the
context-menu, preference, statistic, addition-pane, item-detail, view-column and
port directories, plus the ten graph definition/getter pairs and main entry
points. Helper files are labeled as such. Coverage means a source route maps to
requirements; it does not mean every code branch has executed or is correct.

No desktop wx session or new numerical reference cases were run for A02. A01's
reference remains unchanged. Item attributes, effect beacons, locale availability
and uncommon module mechanics are data-driven: the owning implementation task
must capture their exact IDs/options and fixture matrix from the pinned data.
R01 must compare that enumeration with Android. Static reading cannot certify
that no feature will ever be discovered later.

## Findings that change task planning

- Detailed statistics include capacitor resistance/effective-capacity tooltips,
  sensor jam probability, lock times, warp limits, 21 special holds, mining
  drain/efficiency, bomb survival estimates and item-specific mechanics such as
  breacher pods. They now have explicit rows.
- Attribute overrides, fitting-restriction toggles, fit-price optimization,
  HTML/CSV/skills/profile exports and additional environment groups need owners.
- Ten graph calculations are present. G11 covers shared interactions; it is not
  an eleventh calculation family. Each G task must enumerate valid axes/controls,
  include multiple fits/targets, and compare actual samples.
- I02, I03, I05 and I06 now have 21 numbered children. Their original IDs remain
  rollups. There are 76 tracked rows (72 work items plus four rollups); A01/A02 are
  done. A03 is the next ready work item. Further splits remain possible.

## Unresolved questions — no waivers

These are investigation/disposition requirements assigned to existing tasks,
not reasons to block A03 or permission to silently omit a capability. An owner
must attach source/runtime evidence for resolution. A deliberate capability
omission still needs the product decision required by SCOPE.

| Gap | Finding / uncertainty | Owner and closure requirement |
| --- | --- | --- |
| Q01 | The seed mentioned folders/tags. The audited browser exposes hull/race groups, recents and search; no folder/tag editor was found. XML tag replacement concerns note markup, not fit tags. | B03: verify browser/query behavior and record supported organization. Do not invent a tag UI requirement from a seed example or drop a discovered one. |
| Q02 | The roadmap mentioned manual pricing. Audited controls expose source/system selection, totals, optimization and clearing cache; a manual per-item price editor was not found. Source modules include Fuzzwork, EveTycoon, EVE Market Data and CEVEMarket, but endpoint availability was not tested. | I04: inspect registration/current service availability when implementing and record manual-price disposition. Do not equate a source file with a working provider. |
| Q03 | EFS has an export route; no EFS import route was found. XML is available through file import/export/backup, but its clipboard format choice is commented out. XML export truncates long notes and does not demonstrate full linked-state backup. | I02.02/I02.03/I05.02: record exact supported directions/field loss and provide a complete Android user backup; do not call XML lossless. |
| Q04 | No explicit graph-save toolbar/export handler was found in the audited graph canvas/frame. The seed says export where supported. Pointer/sample controls do exist. | G11: verify the live desktop graph's available actions before settling export parity; do not claim an unobserved save action works. |
| Q05 | wx widget inspection, object/GC/fit developer tools, executable/user paths, log locations, local SSO callback server, token-expiry workaround and proxy discovery are desktop-specific surfaces. | I03.01/I06.05/I06.06: document each Android equivalent or required product decision. Token expiry and credentials need a supported Android design, not blind replication of a workaround. |
| Q06 | App update notices target desktop releases, while this project is a personal APK fork. Data refresh and app updates are separate. | I05.01/I06.07/R02: establish explicit data/build identity and update-notice/delivery behavior without introducing a backend or store publication. |
| Q07 | [A04](../../tools/android_reference/PROJECTIONS.md) establishes a linked dampener case, range/script edits and repeated removal on the host. [A05](../../tools/android_reference/COMMANDS.md) establishes one command source with skill/implant/state/charge changes and removal. Full projection-cycle, command-source overlap and stacking behavior remain unverified. | A04/A05/D02/D03: record independent desktop cases, repeated edits/removals and recipient updates; do not introduce arbitrary cycle suppression or approximate burst formulas. |
| Q08 | Dynamic dictionaries determine all item attributes, available environment effects, fighter abilities, burst buffs and locales. A finite prose list cannot prove coverage of every data entry. | C03/C05/D03/D04/I06.03 and R01: save enumerated IDs/options, match Android coverage, and split uncovered mechanics into additional rows/tasks. |
| Q09 | Some displayed desktop zero/empty values blur missing data; legacy tests include placeholders. | B01/C01/C03/R01: retain absent/error/unimplemented distinctions, and generate independent reference evidence for real behaviors. Source presence is not a passing test. |

## Control coverage index

IDs refer to [PARITY.md](PARITY.md). Multiple rows can share an implementation
file. This index is a review aid, not a generated test suite. A reference to a
helper means its behavior is accounted for in the named rows, not a new screen.

| Source surface | Behavior IDs / disposition |
| --- | --- |
| [graphs/data/fitApplicationProfile/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitApplicationProfile/getter.py) | F19.02 |
| [graphs/data/fitApplicationProfile/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitApplicationProfile/graph.py) | F19.02 |
| [graphs/data/fitCapacitor/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitCapacitor/getter.py) | F19.03 |
| [graphs/data/fitCapacitor/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitCapacitor/graph.py) | F19.03 |
| [graphs/data/fitDamageStats/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitDamageStats/getter.py) | F19.01 |
| [graphs/data/fitDamageStats/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitDamageStats/graph.py) | F19.01 |
| [graphs/data/fitEcmBurstScanresDamps/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEcmBurstScanresDamps/getter.py) | F19.10 |
| [graphs/data/fitEcmBurstScanresDamps/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEcmBurstScanresDamps/graph.py) | F19.10 |
| [graphs/data/fitEwarStats/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEwarStats/getter.py) | F19.09 |
| [graphs/data/fitEwarStats/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEwarStats/graph.py) | F19.09 |
| [graphs/data/fitLockTime/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitLockTime/getter.py) | F19.06 |
| [graphs/data/fitLockTime/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitLockTime/graph.py) | F19.06 |
| [graphs/data/fitMobility/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitMobility/getter.py) | F19.07 |
| [graphs/data/fitMobility/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitMobility/graph.py) | F19.07 |
| [graphs/data/fitRemoteReps/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitRemoteReps/getter.py) | F19.05 |
| [graphs/data/fitRemoteReps/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitRemoteReps/graph.py) | F19.05 |
| [graphs/data/fitShieldRegen/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitShieldRegen/getter.py) | F19.04 |
| [graphs/data/fitShieldRegen/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitShieldRegen/graph.py) | F19.04 |
| [graphs/data/fitWarpTime/getter.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitWarpTime/getter.py) | F19.08 |
| [graphs/data/fitWarpTime/graph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitWarpTime/graph.py) | F19.08 |
| [gui/builtinAdditionPanes/boosterView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/boosterView.py) | F12.01 |
| [gui/builtinAdditionPanes/cargoView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/cargoView.py) | F04.01 |
| [gui/builtinAdditionPanes/commandView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/commandView.py) | F16.01 |
| [gui/builtinAdditionPanes/droneView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/droneView.py) | F08.01, F08.04 |
| [gui/builtinAdditionPanes/fighterView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/fighterView.py) | F09.01, F09.02 |
| [gui/builtinAdditionPanes/implantView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/implantView.py) | F11.01, F11.02 |
| [gui/builtinAdditionPanes/notesView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/notesView.py) | F01.06 |
| [gui/builtinAdditionPanes/projectedView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/projectedView.py) | F15.01 |
| [gui/builtinContextMenus/additionsExportAll.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/additionsExportAll.py) | F20.09 |
| [gui/builtinContextMenus/additionsExportSelection.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/additionsExportSelection.py) | F20.09 |
| [gui/builtinContextMenus/additionsImport.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/additionsImport.py) | F20.09 |
| [gui/builtinContextMenus/ammoToDmgPattern.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/ammoToDmgPattern.py) | F18.02 |
| [gui/builtinContextMenus/boosterSideEffects.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/boosterSideEffects.py) | F12.02 |
| [gui/builtinContextMenus/cargoAdd.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/cargoAdd.py) | F04.02 |
| [gui/builtinContextMenus/cargoAddAmmo.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/cargoAddAmmo.py) | F04.02 |
| [gui/builtinContextMenus/cargoFill.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/cargoFill.py) | F04.03 |
| [gui/builtinContextMenus/commandFitAdd.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/commandFitAdd.py) | F16.01 |
| [gui/builtinContextMenus/damagePatternChange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/damagePatternChange.py) | F18.02 |
| [gui/builtinContextMenus/droneAddStack.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/droneAddStack.py) | F08.02 |
| [gui/builtinContextMenus/droneSplitStack.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/droneSplitStack.py) | F08.03 |
| [gui/builtinContextMenus/envEffectAdd.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/envEffectAdd.py) | F17.01, F17.02, F17.03, F17.04, F17.05, F17.06, F17.07, F17.08, F17.09 |
| [gui/builtinContextMenus/factorReload.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/factorReload.py) | F13.03 |
| [gui/builtinContextMenus/fighterAbilities.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fighterAbilities.py) | F09.03 |
| [gui/builtinContextMenus/fitAddBrowse.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitAddBrowse.py) | F15.04 |
| [gui/builtinContextMenus/fitAddCurrentlyOpen.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitAddCurrentlyOpen.py) | F15.04 |
| [gui/builtinContextMenus/fitOpenNewTab.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitOpenNewTab.py) | F15.04 |
| [gui/builtinContextMenus/fitPilotSecurity.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitPilotSecurity.py) | F17.11 |
| [gui/builtinContextMenus/fitSystemSecurity.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitSystemSecurity.py) | F17.10 |
| [gui/builtinContextMenus/graphAmmoOptimalApplyProjected.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphAmmoOptimalApplyProjected.py) | F19.15 |
| [gui/builtinContextMenus/graphAmmoOptimalIgnoreResists.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphAmmoOptimalIgnoreResists.py) | F19.15 |
| [gui/builtinContextMenus/graphDmgApplyProjected.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDmgApplyProjected.py) | F19.14 |
| [gui/builtinContextMenus/graphDmgDroneMode.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDmgDroneMode.py) | F19.14 |
| [gui/builtinContextMenus/graphDmgIgnoreResists.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDmgIgnoreResists.py) | F19.14 |
| [gui/builtinContextMenus/graphDroneControlRange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDroneControlRange.py) | F19.17 |
| [gui/builtinContextMenus/graphFitAmmoPicker.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphFitAmmoPicker.py) | F19.16 |
| [gui/builtinContextMenus/graphLockRange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphLockRange.py) | F19.17 |
| [gui/builtinContextMenus/implantSetApply.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/implantSetApply.py) | F11.03 |
| [gui/builtinContextMenus/implantSetSave.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/implantSetSave.py) | F11.04 |
| [gui/builtinContextMenus/itemAmountChange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemAmountChange.py) | F04.01 |
| [gui/builtinContextMenus/itemFill.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemFill.py) | F03.04 |
| [gui/builtinContextMenus/itemMarketJump.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemMarketJump.py) | F02.01 |
| [gui/builtinContextMenus/itemMutations.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemMutations.py) | F14.01 |
| [gui/builtinContextMenus/itemProject.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemProject.py) | F15.05 |
| [gui/builtinContextMenus/itemProjectionRange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemProjectionRange.py) | F15.06 |
| [gui/builtinContextMenus/itemRemove.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemRemove.py) | F02.02, F04.01, F08.01, F09.01, F11.01, F12.01, F15.06 |
| [gui/builtinContextMenus/itemStats.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemStats.py) | F07.31 |
| [gui/builtinContextMenus/itemVariationChange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemVariationChange.py) | F02.05 |
| [gui/builtinContextMenus/moduleAmmoChange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleAmmoChange.py) | F02.03, F03.01 |
| [gui/builtinContextMenus/moduleFill.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleFill.py) | F03.04 |
| [gui/builtinContextMenus/moduleMutatedExport.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleMutatedExport.py) | F14.04 |
| [gui/builtinContextMenus/moduleRahPattern.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleRahPattern.py) | F13.05 |
| [gui/builtinContextMenus/moduleSpool.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleSpool.py) | F13.04 |
| [gui/builtinContextMenus/priceOptions.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/priceOptions.py) | F21.07 |
| [gui/builtinContextMenus/resistMode.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/resistMode.py) | F19.18 |
| [gui/builtinContextMenus/shared/patterns.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/shared/patterns.py) | F13.05, F18.02 (support helper) |
| [gui/builtinContextMenus/shipJump.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/shipJump.py) | F01.03 |
| [gui/builtinContextMenus/shipModeChange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/shipModeChange.py) | F02.06 |
| [gui/builtinContextMenus/skillAffectors.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/skillAffectors.py) | F07.33 |
| [gui/builtinContextMenus/targetProfile/adder.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/targetProfile/adder.py) | F18.04 |
| [gui/builtinContextMenus/targetProfile/editor.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/targetProfile/editor.py) | F18.03, F18.04 |
| [gui/builtinContextMenus/targetProfile/switcher.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/targetProfile/switcher.py) | F18.04, F19.18 |
| [gui/builtinItemStatsViews/attributeGrouping.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/attributeGrouping.py) | F07.31 |
| [gui/builtinItemStatsViews/attributeSlider.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/attributeSlider.py) | F14.02 |
| [gui/builtinItemStatsViews/helpers.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/helpers.py) | F07.31, F07.33 (support helper) |
| [gui/builtinItemStatsViews/itemAffectedBy.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemAffectedBy.py) | F07.34 |
| [gui/builtinItemStatsViews/itemAttributes.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemAttributes.py) | F07.31, F20.08 |
| [gui/builtinItemStatsViews/itemCompare.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemCompare.py) | F07.35 |
| [gui/builtinItemStatsViews/itemDependants.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemDependants.py) | F07.33 |
| [gui/builtinItemStatsViews/itemDescription.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemDescription.py) | F07.32 |
| [gui/builtinItemStatsViews/itemEffects.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemEffects.py) | F07.36 |
| [gui/builtinItemStatsViews/itemMutator.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemMutator.py) | F14.02, F14.03 |
| [gui/builtinItemStatsViews/itemProperties.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemProperties.py) | F07.36 |
| [gui/builtinItemStatsViews/itemRequirements.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemRequirements.py) | F07.33 |
| [gui/builtinItemStatsViews/itemTraits.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemTraits.py) | F07.32 |
| [gui/builtinPreferenceViews/dummyView.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/dummyView.py) | Example preference code; not imported by `gui/preferenceView.py`, so not an active preference surface. Retained in index, not claimed as a user feature. |
| [gui/builtinPreferenceViews/pyfaContextMenuPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaContextMenuPreferences.py) | F22.07 |
| [gui/builtinPreferenceViews/pyfaDatabasePreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaDatabasePreferences.py) | F21.09, F22.17 |
| [gui/builtinPreferenceViews/pyfaEnginePreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaEnginePreferences.py) | F13.03, F22.01, F22.02 |
| [gui/builtinPreferenceViews/pyfaEsiPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaEsiPreferences.py) | F21.01 |
| [gui/builtinPreferenceViews/pyfaGeneralPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaGeneralPreferences.py) | F03.02, F22.03, F22.05, F22.06, F22.09 |
| [gui/builtinPreferenceViews/pyfaHTMLExportPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaHTMLExportPreferences.py) | F20.10 |
| [gui/builtinPreferenceViews/pyfaLoggingPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaLoggingPreferences.py) | F22.14, F22.15 |
| [gui/builtinPreferenceViews/pyfaMarketPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaMarketPreferences.py) | F21.05, F21.07, F22.08 |
| [gui/builtinPreferenceViews/pyfaNetworkPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaNetworkPreferences.py) | F22.12, F22.13 |
| [gui/builtinPreferenceViews/pyfaStatViewPreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaStatViewPreferences.py) | F22.04 |
| [gui/builtinPreferenceViews/pyfaUpdatePreferences.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaUpdatePreferences.py) | F22.16 |
| [gui/builtinStatsViews/bombingViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/bombingViewFull.py) | F06.10 |
| [gui/builtinStatsViews/capacitorViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/capacitorViewFull.py) | F05.12, F05.13, F05.14, F05.15 |
| [gui/builtinStatsViews/firepowerViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/firepowerViewFull.py) | F06.01, F06.02, F06.03, F06.04, F06.05, F06.09 |
| [gui/builtinStatsViews/miningyieldViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/miningyieldViewFull.py) | F06.06, F06.07, F06.08, F06.09 |
| [gui/builtinStatsViews/outgoingViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/outgoingViewFull.py) | F06.11, F06.12, F06.13, F06.14 |
| [gui/builtinStatsViews/outgoingViewMinimal.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/outgoingViewMinimal.py) | F06.11, F06.12, F06.13, F06.14 |
| [gui/builtinStatsViews/priceViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/priceViewFull.py) | F21.06 |
| [gui/builtinStatsViews/priceViewMinimal.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/priceViewMinimal.py) | F21.06 |
| [gui/builtinStatsViews/rechargeViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/rechargeViewFull.py) | F05.23, F05.24, F05.25, F05.26, F05.27 |
| [gui/builtinStatsViews/resistancesViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/resistancesViewFull.py) | F05.16, F05.17, F05.18, F05.19, F05.20, F05.21, F05.22 |
| [gui/builtinStatsViews/resourcesViewFull.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/resourcesViewFull.py) | F05.01, F05.02, F05.03, F05.04, F05.05, F05.06, F05.07, F05.08, F05.09, F05.10, F05.11 |
| [gui/builtinStatsViews/targetingMiscViewMinimal.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/targetingMiscViewMinimal.py) | F07.01, F07.02, F07.03, F07.04, F07.05, F07.06, F07.07, F07.08, F07.09, F07.10, F07.11, F07.12, F07.13, F07.14, F07.15, F07.16, F07.17, F07.18, F07.19, F07.20, F07.21, F07.22, F07.23, F07.24, F07.25, F07.26, F07.27, F07.28, F07.29, F07.30 |
| [gui/builtinViewColumns/abilities.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/abilities.py) | F09.03 |
| [gui/builtinViewColumns/ammo.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/ammo.py) | F02.03, F09.03 |
| [gui/builtinViewColumns/ammoIcon.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/ammoIcon.py) | F02.03 |
| [gui/builtinViewColumns/attributeDisplay.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/attributeDisplay.py) | F07.37 |
| [gui/builtinViewColumns/attributeDisplayGraph.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/attributeDisplayGraph.py) | F19.01, F19.02, F19.03, F19.04, F19.05, F19.06, F19.07, F19.08, F19.09, F19.10 |
| [gui/builtinViewColumns/baseIcon.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/baseIcon.py) | F02.01, F02.02 |
| [gui/builtinViewColumns/baseName.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/baseName.py) | F04.01, F22.06 |
| [gui/builtinViewColumns/capacitorUse.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/capacitorUse.py) | F07.37 |
| [gui/builtinViewColumns/dampScanRes.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/dampScanRes.py) | F19.10 |
| [gui/builtinViewColumns/droneEhp.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/droneEhp.py) | F08.05 |
| [gui/builtinViewColumns/droneRegen.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/droneRegen.py) | F08.05 |
| [gui/builtinViewColumns/graphColor.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/graphColor.py) | F19.12 |
| [gui/builtinViewColumns/graphLightness.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/graphLightness.py) | F19.12 |
| [gui/builtinViewColumns/graphLineStyle.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/graphLineStyle.py) | F19.12 |
| [gui/builtinViewColumns/heat.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/heat.py) | F13.02 |
| [gui/builtinViewColumns/maxRange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/maxRange.py) | F07.37 |
| [gui/builtinViewColumns/misc.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/misc.py) | F07.38, F07.39, F07.40, F07.41, F07.42, F07.43, F07.44, F07.45, F07.46, F07.47, F07.48, F12.01, F16.02 |
| [gui/builtinViewColumns/price.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/price.py) | F21.06 |
| [gui/builtinViewColumns/projectionRange.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/projectionRange.py) | F15.06 |
| [gui/builtinViewColumns/propertyDisplay.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/propertyDisplay.py) | F07.37 |
| [gui/builtinViewColumns/sideEffects.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/sideEffects.py) | F12.02 |
| [gui/builtinViewColumns/state.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/state.py) | F03.03, F15.06, F16.01 |
| [gui/builtinViewColumns/targetResists.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/targetResists.py) | F19.18 |
| [gui/builtinViews/implantEditor.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViews/implantEditor.py) | F11.03 |
| [gui/characterEditor.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/characterEditor.py) | F10.01, F10.02, F10.03, F10.04, F10.05, F10.06, F10.07, F21.02 |
| [gui/copySelectDialog.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/copySelectDialog.py) | F20.02, F20.03, F20.05, F20.06, F20.07 |
| [gui/esiFittings.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/esiFittings.py) | F20.11, F21.01, F21.03, F21.04 |
| [gui/itemStats.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/itemStats.py) | F07.31 |
| [gui/mainFrame.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/mainFrame.py) | F01.05, F02.09, F03.06, F10.04, F10.07, F20.12, F21.08, F22.10, F22.15 |
| [gui/mainMenuBar.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/mainMenuBar.py) | F01.05, F22.14 |
| [gui/patternEditor.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/patternEditor.py) | F18.01, F18.05 |
| [gui/propertyEditor.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/propertyEditor.py) | F22.10, F22.11 |
| [gui/ssoLogin.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/ssoLogin.py) | F21.01 |
| [gui/targetProfileEditor.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/targetProfileEditor.py) | F18.03, F18.04, F18.05 |
| [service/port/dna.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/dna.py) | F20.03 |
| [service/port/efs.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/efs.py) | F20.05 |
| [service/port/eft.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/eft.py) | F20.01, F20.02, F20.09 |
| [service/port/esi.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/esi.py) | F20.11 |
| [service/port/multibuy.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/multibuy.py) | F20.06 |
| [service/port/muta.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/muta.py) | F14.04 |
| [service/port/port.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/port.py) | F14.05, F20.01, F20.03, F20.04, F20.11, F20.12, F23.03 |
| [service/port/shared.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/shared.py) | F20.09 |
| [service/port/shipstats.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/shipstats.py) | F20.07 |
| [service/port/xml.py](https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/xml.py) | F20.04 |

## A02 validation record

Documentation-only checks: unique behavior/task IDs, all 23 families, a delivery
owner and nonempty evidence slot for every row, every source path present at the
pinned commit, all control-index entries mapped or explicitly dispositioned,
all ten graph pairs covered, local Markdown link targets, acyclic task
dependencies, parent/child ownership, ready-task prerequisites, and whitespace.
The delivery PR records the checked commit. No Android/emulator, desktop fixture
regeneration, or CI run is needed for this documentation-only change.
