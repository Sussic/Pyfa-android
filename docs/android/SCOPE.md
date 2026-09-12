# Product scope and parity inventory

## Agreed outcome

A personal offline Android Pyfa with the fitting capabilities of the pinned desktop
source. The user explicitly needs projections, command bursts, complete useful
statistics (including drone control range), and efficient group operations such
as changing all guns or their ammunition together. Usability is confirmed by the
user after technical verification; it is not a substitute for correctness tests.

The desktop feature set is the acceptance reference, not its window layout.
Capabilities hidden in menus, settings and item details count as features too.

## Coverage seed — all Android behavior is currently unimplemented

This is a source-informed inventory of families, not a completed exhaustive audit.
A02 must expand it into individual observable behaviors with source references,
task ownership and evidence slots, especially less common ship/module mechanics.
No family can be declared complete merely because a corresponding screen exists.

| ID | Capability family and examples | Upstream starting point | Tasks |
| --- | --- | --- | --- |
| F01 | Fit library, search, naming, duplication, folders/tags where supported, notes | `gui/shipBrowser.py`, `service/fit.py` | B02, B03, B08 |
| F02 | Ship/structure selection, modules, rigs, charges, slot legality, modes/subsystems | `eos/saveddata/`, `gui/fitCommands/` | B04, B06 |
| F03 | Multi-select, fill slots, bulk module/ammo/state changes and undo/redo | `gui/fitCommands/`, `gui/builtinContextMenus/moduleFill.py` | B05, B09 |
| F04 | Cargo, quantities and module/ammo transfers | `gui/builtinAdditionPanes/cargoView.py` | B07 |
| F05 | CPU/PG, capacitor, recharge, resists, EHP and tank with selected assumptions | `gui/builtinStatsViews/` | C01 |
| F06 | Damage/application inputs, firepower, bombs, mining and outgoing stats | `gui/builtinStatsViews/`, `eos/utils/` | C02 |
| F07 | Targeting, navigation and full ship/item attributes including drone control range | `gui/builtinStatsViews/targetingMiscViewMinimal.py`, `gui/itemStats.py` | C03 |
| F08 | Drones, stacks, bandwidth, activation and modified attributes | `eos/saveddata/drone.py`, `gui/builtinAdditionPanes/droneView.py` | C04 |
| F09 | Fighters, squadrons and ability states | `eos/saveddata/fighter.py`, `eos/saveddata/fighterAbility.py` | C05 |
| F10 | Character skills, all-V/custom profiles, requirements and affectors | `service/character.py`, `gui/characterEditor.py` | C06, I03 |
| F11 | Implants, implant sets and slots | `service/implantSet.py`, `gui/builtinAdditionPanes/implantView.py` | C07 |
| F12 | Boosters and selectable side effects | `eos/saveddata/booster.py`, `gui/builtinContextMenus/boosterSideEffects.py` | C08 |
| F13 | Module states/heat, reload, spool-up and supported calculation options | `eos/saveddata/module.py`, `gui/builtinContextMenus/` | C09 |
| F14 | Mutated/abyssal modules and drones; exact rolled attributes | `eos/saveddata/mutatedMixin.py`, `service/port/muta.py` | C10, I02 |
| F15 | Projected modules/fits/drones/fighters, ranges, quantities, linked recalculation | `gui/builtinAdditionPanes/projectedView.py`, `eos/saveddata/fit.py` | A04, A08, D01, D02 |
| F16 | Command fits/bursts, source skills/implants and enabled states | `gui/builtinAdditionPanes/commandView.py`, `gui/fitCommands/calc/commandFit/` | A05, A09, D03 |
| F17 | Environments, wormhole/weather effects, system/pilot security where supported | `gui/builtinContextMenus/envEffectAdd.py`, `gui/fitCommands/calc/` | D04 |
| F18 | Damage patterns, target profiles and comparison assumptions | `service/damagePattern.py`, `service/targetProfile.py` | D05 |
| F19 | Every graph family, interactive inputs, fit comparisons and export where supported | `graphs/data/`, `graphs/gui/` | G01, G02, G03, G04, G05, G06, G07, G08, G09, G10, G11 |
| F20 | EFT/DNA/XML/EFS and other existing import/export formats, sharing and multibuy | `service/port/` | I01, I02 |
| F21 | Character/fitting sync and market prices, with cached offline use | `service/esi.py`, `service/price.py`, `service/marketSources/` | I03, I04 |
| F22 | Calculation preferences, display options and supported languages | `gui/builtinPreferenceViews/`, `locale/` | I06 |
| F23 | Bundled game data, updates, fit backup/restore and upgrades preserving user data | `db_update.py`, `eos/db/`, `staticdata/` | A07, I05, R01, R02 |

## Offline means

After installing the APK, first launch and all fitting work must succeed without
network access: browse the bundled items, create/edit fits, apply linked effects,
view statistics/graphs and save/reopen work. No remote desktop, always-on home PC
or calculation server is part of the product.

Live ESI character/fitting synchronization, fresh prices and game-data downloads
naturally require a connection. They are optional refresh operations, not omitted
capabilities or prerequisites for calculation. Retain last-known values, display
their age, and support offline character profiles. Never show an unavailable price
as zero. An updated dataset must not silently corrupt existing fits.

## Complete means

- Every behavior identified by A02 has implementation and explicit verification
  evidence, including uncommon supported mechanics and interactions.
- Matched inputs produce desktop-equivalent raw results within documented numeric
  tolerances; displayed units/rounding and graph samples are also checked.
- Offline first launch, persistence, backup/restore and APK upgrades pass.
- No unexplained disabled/skipped parity tests or silently missing statistics.
- Real-device operation is verified and the user accepts the touch workflow,
  especially bulk editing and navigating projected/command fits.

Any intentional capability omission needs an explicit product decision; it cannot
be hidden as "later" while declaring the project finished. Intermediate APKs may
have incomplete features if clearly labeled as development milestones.

## Outside the current project

An iOS port, web/server fitting service, market trading automation, multiplayer
accounts system, paid features, analytics and store publication. These do not
follow from the user's request for a personal offline Android app.
