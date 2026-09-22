# Observable parity checklist

Audited 2026-09-12 against desktop source `8b04f3b271e614b3e103853b44a7851a63d79d0e`.
This is a static source audit, not an observed desktop UI session or proof of an
Android implementation. [SCOPE.md](SCOPE.md) owns the product boundary;
[ROADMAP.md](ROADMAP.md) owns task state. A01 proves only its recorded host fixture.

Each row has a stable ID, one delivery owner, a behavior/acceptance target, pinned
source links, required check types and an evidence slot. A07 now supplies limited
Android baseline evidence to the rows below; **no full feature family is complete**. `D: —; A: —` means desktop reference evidence and
Android evidence have not yet been attached to that row. Do not fill these slots
with a planned test, source reading, an inherited placeholder, or a screen image
that does not establish the behavior. A01/A07 links cover only the fixed Vexor inputs and states actually checked.
A07 does not establish broad editing, displayed precision, persistence or the
other members of a row's required matrix. Full completion still needs each row.

Checks: **N** matched numerical/reference states and units; **U** native touch
interaction/display assertion; **P** persistence/process restart; **G** numerical
graph samples and control changes; **X** interchange fixtures, malformed input and
declared format loss; **O** network-unavailable/cancel/failure and cached behavior.
Every calculation/display row also requires offline operation in R01. Mutable
rows include reversal/removal and invalid-input checks. Save reference inputs,
source/data hashes, units, tolerances, tested commit and test/run links in a
focused evidence file, then link it from the relevant row's D/A slot.

Rows listing a finite family (four damage types, six wormhole types, an attribute
dictionary, etc.) require **every member**, not one example. An implementation
task must expand its matrix into named fixture assertions before closing it.
For dataset-driven attributes/effects, capture the complete enumerated ID set at
the pinned dataset and compare it to Android; this document intentionally does
not freeze thousands of item types as guessed constants. Preserve new discoveries
as additional IDs or child IDs, never delete an unimplemented requirement.

Sources identify the actual controls and calculation routes, not a claim that
every inherited behavior is bug-free. Suspected quirks, missing behavior and
platform substitutions are tracked in [the audit notes](PARITY_AUDIT.md).

A10 [retains the embedding design](tasks/A10-embedding-feasibility.md) after bounded
native performance measurements and a source-refresh correction. [Its receipt](evidence/a10-native.json)
adds rerun evidence for the same cases; it does not complete any broader parity
row or remove UI, persistence or matrix requirements. All 239 rows are preserved.

## F01 — Fit library and notes

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F01.01 | Create a named fit for a ship or structure; duplicate without aliasing editable contents. | B03 | [s233][s233], [s129][s129] | NUP | D: —; A: — |
| F01.02 | Rename and delete a fit; resolve projection/command references and open views consistently. | B03 | [s233][s233], [s129][s129] | NUP | D: —; A: — |
| F01.03 | Browse by hull group and race, hide/show empty groups, and navigate back to a hull from its fit. | B03 | [s225][s225], [s130][s130], [s131][s131] | UP | D: [complete Market catalogue export](evidence/b03-2-native.json); A: [offline groups/races/back workflow](evidence/b03-2-native.json) |
| F01.04 | Search saved fit names and access recent fits; opening a result selects the intended fit. | B03 | [s233][s233], [s130][s130] | UP | D: —; A: [offline search identity and modification-order workflow](evidence/b03-2-native.json) |
| F01.05 | Keep multiple fits open, switch between them, close one/all and optionally reopen the previous set after restart. | B03 | [s220][s220], [s221][s221] | UP | D: —; A: [four-process open/close/restore workflow](evidence/b03-2-native.json) |
| F01.06 | Edit multiline Unicode notes, preserve text on navigation and save/reopen the correct fit's notes. | B08 | [s056][s056], [s233][s233] | UP | D: —; A: — |
| F01.07 | Persist the entire fit and linked-fit identity across process death; edits to one copy do not mutate an independent duplicate. | B02 | [s017][s017], [s233][s233] | NUP | D: —; A: — |

## F02 — Hull and fitted equipment

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F02.01 | Browse bundled market groups, search items and recent items, filter meta variants, and jump to an item's market group. | B04 | [s222][s222], [s116][s116], [s117][s117], [s089][s089] | UP | D: —; A: — |
| F02.02 | Add, replace and remove modules, rigs and service modules; preserve positions and show slot/resource/skill legality. | B04 | [s198][s198], [s207][s207], [s206][s206], [s019][s019] | NUP | D: —; A: — |
| F02.03 | Load, replace and unload compatible charges/scripts/crystals; reject incompatible charges without partial edits. | B04 | [s093][s093], [s175][s175] | NUP | D: —; A: — |
| F02.04 | Swap/reorder fitted modules, retaining states/charges and changing rack-dependent heat behavior correctly. | B04 | [s208][s208], [s179][s179] | NUP | D: —; A: — |
| F02.05 | Switch an item to a supported variation in fitted and addition panes; retain or reconcile states and charges. | B04 | [s092][s092], [s174][s174] | NUP | D: —; A: — |
| F02.06 | Change tactical modes and supported primary/secondary/tertiary modes; recalculate bonuses and restore the prior mode. | B06 | [s100][s100], [s183][s183], [s018][s018] | NUP | D: —; A: — |
| F02.07 | Replace strategic-cruiser subsystems and reconcile altered slots, fitting legality and hull bonuses. | B06 | [s019][s019], [s178][s178], [s017][s017] | NUP | D: —; A: — |
| F02.08 | Fit structures with service slots and structure-specific restrictions/bonuses; compare a structure fixture independently of ship fixtures. | B06 | [s013][s013], [s017][s017] | NUP | D: —; A: — |
| F02.09 | Explicitly disable fitting restrictions for experimentation; re-enabling handles illegal items visibly and matches desktop removals. | B04 | [s220][s220], [s186][s186] | NUP | D: —; A: — |

## F03 — Bulk edits and undo

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F03.01 | Select multiple compatible weapons and change all selected ammunition in one action; mixed selections do not silently edit unintended modules. | B05 | [s199][s199], [s093][s093] | NU | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): fixed two-gun change/restoration and touch button; selection/mixed UI pending |
| F03.02 | Choose same-type-all versus selection-only ammo changes; expose the desktop modifier-key alternative as a touch-accessible choice. | B05 | [s122][s122], [s199][s199] | NUP | D: —; A: — |
| F03.03 | Change selected module states together, including offline, online, active and overheated where supported. | B05 | [s201][s201], [s177][s177] | NU | D: —; A: — |
| F03.04 | Fill free slots with an item or clones of a fitted module; verify charges, states and stopping limits. | B05 | [s088][s088], [s094][s094], [s204][s204], [s203][s203] | NU | D: —; A: — |
| F03.05 | Clone selected modules and apply compatible variation/removal operations to the complete selection. | B05 | [s202][s202], [s200][s200], [s206][s206] | NU | D: —; A: — |
| F03.06 | Undo/redo single and bulk edits as user actions with restored values; keep command history associated with its fit and invalidate redo after a new edit. | B09 | [s161][s161], [s220][s220] | NU | D: —; A: — |
| F03.07 | Extend undo/redo to every later supported mutation, including linked effects, quantities, mutations and cargo transfers; enumerate any desktop gaps before claiming parity. | B09 | [s184][s184], [s162][s162] | NU | D: —; A: — |

## F04 — Cargo

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F04.01 | Add/remove cargo stacks and change selected quantities; calculate used volume including container behavior. | B07 | [s051][s051], [s087][s087], [s146][s146] | NUP | D: —; A: — |
| F04.02 | Add an item's ammunition to cargo with desktop quantity presets, including the crystal exception. | B07 | [s064][s064], [s063][s063] | NUP | D: —; A: — |
| F04.03 | Fill remaining cargo capacity with a chosen item; handle insufficient capacity and partial stack boundaries. | B07 | [s065][s065] | NUP | D: —; A: — |
| F04.04 | Move fitted modules to cargo and fit modules from cargo, preserving supported charge/state semantics and undo. | B07 | [s210][s210], [s209][s209] | NUP | D: —; A: — |
| F04.05 | Replace cargo item variations and merge quantities consistently; save/reopen retains item identity and count. | B07 | [s185][s185], [s164][s164] | NUP | D: —; A: — |

## F05 — Resources, capacitor and defenses

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F05.01 | Show used and available turret hardpoints (count); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.02 | Show used and available launcher hardpoints (count); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.03 | Show used and available active drones (count); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.04 | Show used and available fighter tubes (count); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.05 | Show used and available calibration (points); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.06 | Show used and available CPU (tf); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): CPU used/output only |
| F05.07 | Show used and available powergrid (MW); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): powergrid used/output only |
| F05.08 | Show used and available drone bay (m³); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.09 | Show used and available fighter bay (m³); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.10 | Show used and available drone bandwidth (Mbit/s); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): used bandwidth only |
| F05.11 | Show used and available cargo bay (m³); limits, over-capacity and detail precision agree with the reference. | C01 | [s142][s142] | NUP | D: —; A: — |
| F05.12 | Show capacitor capacity (GJ) and neutralizer-resistance-adjusted effective capacity in accessible details. | C01 | [s133][s133], [s017][s017] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): raw capacity only |
| F05.13 | Distinguish stable capacitor percentage/range from depletion time (s); do not confuse capState units. | C01 | [s133][s133], [s017][s017] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): baseline cap stability/state only |
| F05.14 | Show recharge, use and signed delta (GJ/s), including effective excess gain in details. | C01 | [s133][s133], [s017][s017] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): use/recharge only |
| F05.15 | Show neutralizer resistance (%) and update capacity/delta details after battery or projected-neut changes. | C01 | [s133][s133], [s017][s017] | NUP | D: —; A: — |
| F05.16 | Show all four shield damage resistances (EM, thermal, kinetic, explosive) and resistance multiplier; modify each damage-type input independently. | C01 | [s141][s141] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): four raw shield resonances only |
| F05.17 | Show shield raw HP and damage-pattern-dependent EHP; toggling HP/EHP retains values and units. | C01 | [s141][s141] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): shield HP/uniform EHP only |
| F05.18 | Show all four armor damage resistances (EM, thermal, kinetic, explosive) and resistance multiplier; modify each damage-type input independently. | C01 | [s141][s141] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): four raw armor resonances only |
| F05.19 | Show armor raw HP and damage-pattern-dependent EHP; toggling HP/EHP retains values and units. | C01 | [s141][s141] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): armor HP/uniform EHP only |
| F05.20 | Show all four hull damage resistances (EM, thermal, kinetic, explosive) and resistance multiplier; modify each damage-type input independently. | C01 | [s141][s141] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): four raw hull resonances only |
| F05.21 | Show hull raw HP and damage-pattern-dependent EHP; toggling HP/EHP retains values and units. | C01 | [s141][s141] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): hull HP/uniform EHP only |
| F05.22 | Show total raw HP/EHP and the selected incoming damage pattern with all four contributions. | C01 | [s141][s141] | NUP | D: —; A: — |
| F05.23 | Show passive shield recharge in HP/s or EHP/s with applicable reinforced/sustained variants; capacitor limits and projected repairs match desktop. | C01 | [s140][s140], [s017][s017] | NUP | D: —; A: — |
| F05.24 | Show active shield boost in HP/s or EHP/s with applicable reinforced/sustained variants; capacitor limits and projected repairs match desktop. | C01 | [s140][s140], [s017][s017] | NUP | D: —; A: — |
| F05.25 | Show active armor repair in HP/s or EHP/s with applicable reinforced/sustained variants; capacitor limits and projected repairs match desktop. | C01 | [s140][s140], [s017][s017] | NUP | D: —; A: — |
| F05.26 | Show active hull repair in HP/s or EHP/s with applicable reinforced/sustained variants; capacitor limits and projected repairs match desktop. | C01 | [s140][s140], [s017][s017] | NUP | D: —; A: — |
| F05.27 | Expose pre/full spool tank values and current spool indication in repair details; disabling/removing repair restores baseline. | C01 | [s140][s140] | NUP | D: —; A: — |

## F06 — Firepower, mining and outgoing effects

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F06.01 | Show weapon DPS and four damage-type shares; target-profile effective mode and no-profile raw mode match desktop. | C02 | [s134][s134], [s017][s017] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): total weapon DPS only |
| F06.02 | Show drone/fighter DPS contribution and four damage-type shares; target-profile effective mode and no-profile raw mode match desktop. | C02 | [s134][s134], [s017][s017] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): total drone DPS only |
| F06.03 | Show total DPS and four damage-type shares; target-profile effective mode and no-profile raw mode match desktop. | C02 | [s134][s134], [s017][s017] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): combined DPS only |
| F06.04 | Show total volley and four damage-type shares; target-profile effective mode and no-profile raw mode match desktop. | C02 | [s134][s134], [s017][s017] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): total volley only |
| F06.05 | Show current, initial and full-spool damage details and the default spool percentage used. | C02 | [s134][s134] | NUP | D: —; A: — |
| F06.06 | Show mining modules yield, drain and efficiency; m³/s and detail m³/hour agree for crystals and non-crystal cases. | C02 | [s135][s135] | NUP | D: —; A: — |
| F06.07 | Show mining drones yield, drain and efficiency; m³/s and detail m³/hour agree for crystals and non-crystal cases. | C02 | [s135][s135] | NUP | D: —; A: — |
| F06.08 | Show combined mining yield, drain and efficiency; m³/s and detail m³/hour agree for crystals and non-crystal cases. | C02 | [s135][s135] | NUP | D: —; A: — |
| F06.09 | Switch firepower/mining views without losing either capability or changing the fit. | C02 | [s134][s134], [s135][s135] | U | D: —; A: — |
| F06.10 | Show bombs needed to destroy the fitted target for four bomb damage types at Covert Ops levels 0–5, including Red Giant effects and rounding. | C02 | [s132][s132] | NUP | D: —; A: — |
| F06.11 | Show outgoing capacitor transfer (GJ/s), including applicable initial/full spool details in both compact and full views. | C02 | [s136][s136], [s137][s137] | NUP | D: —; A: — |
| F06.12 | Show outgoing shield repair (HP/s), including applicable initial/full spool details in both compact and full views. | C02 | [s136][s136], [s137][s137] | NUP | D: —; A: — |
| F06.13 | Show outgoing armor repair (HP/s), including applicable initial/full spool details in both compact and full views. | C02 | [s136][s136], [s137][s137] | NUP | D: —; A: — |
| F06.14 | Show outgoing hull repair (HP/s), including applicable initial/full spool details in both compact and full views. | C02 | [s136][s136], [s137][s137] | NUP | D: —; A: — |

## F07 — Navigation, targeting and detailed attributes

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F07.01 | Show Maximum locked targets (count). | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.02 | Show Maximum targeting range (m raw, km display). | C03 | [s143][s143] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): raw target range only |
| F07.03 | Show Scan resolution (mm) and lock times for each reference target size. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.04 | Show Sensor strength, sensor type and chance to be jammed (%). | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.05 | Show Drone control range (m raw, km display); skills, modules and modifiers update the value. | C03 | [s143][s143] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): fixed all-V/augmentor case, raw metres displayed; modifier edits/km display pending |
| F07.06 | Show Maximum speed (m/s). | C03 | [s143][s143] | NUP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): fixed-fit speed only |
| F07.07 | Show Align time (s) with precise mass (kg) and agility details. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.08 | Show Signature radius (m) and probe-size detail. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.09 | Show Warp speed (AU/s), maximum warp distance (AU), and warp-core strength detail. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.10 | Show fleet hangar capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.11 | Show maintenance bay capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.12 | Show infrastructure hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.13 | Show ammo hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.14 | Show fuel bay capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.15 | Show ship hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.16 | Show small ship hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.17 | Show medium ship hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.18 | Show large ship hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.19 | Show industrial ship hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.20 | Show mining hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.21 | Show ice hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.22 | Show gas hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.23 | Show mineral hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.24 | Show material bay capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.25 | Show salvage hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.26 | Show command center hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.27 | Show planetary goods hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.28 | Show Quafe hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.29 | Show mobile depot hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.30 | Show expedition hold capacity (m³) in cargo details when present; preserve the desktop aggregate and distinguish absence from an unimplemented field. | C03 | [s143][s143] | NUP | D: —; A: — |
| F07.31 | Inspect a ship, fitted/base item and loaded charge: grouped current/base attributes, raw view, precise values and refresh after edits. | C03 | [s219][s219], [s107][s107], [s104][s104] | NU | D: —; A: — |
| F07.32 | Show item description and traits with copyable text. | C03 | [s110][s110], [s115][s115] | U | D: —; A: — |
| F07.33 | Show recursive skill requirements, dependent skills and affectors; navigate to the relevant skill and change its level. | C06 | [s114][s114], [s109][s109], [s101][s101] | NU | D: —; A: — |
| F07.34 | Inspect attribute affectors with expanded detail, name/view modes and refresh; stacking and unused modifiers remain explainable. | C03 | [s106][s106] | NU | D: —; A: — |
| F07.35 | Compare item variations with current/base view modes and prices; refresh comparisons after fit changes. | C03 | [s108][s108] | NU | D: —; A: — |
| F07.36 | Inspect effect name, active flag, type, runtime and ID, plus supported object properties. | C03 | [s111][s111], [s113][s113] | NU | D: —; A: — |
| F07.37 | Show equipment optimal/falloff or missile flight-range probabilities, capacitor use/peak recharge effect, CPU/PG and volume including stacks. | C03 | [s151][s151], [s147][s147], [s145][s145], [s154][s154] | NU | D: —; A: — |
| F07.38 | Expose item-row details: Turret/drone tracking and signature-resolution details; missile/Vorton explosion radius and velocity. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.39 | Expose item-row details: Neutralizer/nosferatu rates and web/grappler, target-painter and warp disruption/stabilization strengths. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.40 | Expose item-row details: ECM/ECCM racial strengths, sensor boost/damp effects, turret disruption and missile guidance disruption bonuses. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.41 | Expose item-row details: Damage-upgrade and drone-damage bonuses; distinguish weapon families and affected attributes. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.42 | Expose item-row details: Remote/local/ancillary repair and cap-booster amounts, cycles, charge/reload totals and effective/raw modes. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.43 | Expose item-row details: Command-burst buff IDs, strength and affected attributes for every supported burst charge. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.44 | Expose item-row details: Mining yield/drain/efficiency, crystal critical/waste chances, and scanner-probe strength at scan range. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.45 | Expose item-row details: Salvage retrieval chance, hacking virus strength/coherence, cloak recalibration and cargo/ship scan duration. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.46 | Expose item-row details: Fuel consumption type/quantity and duration for jump, siege and cyno modules; assault damage-control duration. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.47 | Expose item-row details: Subsystem slot modifiers, reactive-hardener damage-type distribution and superweapon damage/duration. | C03 | [s152][s152] | NU | D: —; A: — |
| F07.48 | Expose item-row details: SCARAB breacher pod maximum damage per tick, HP percentage cap and duration; target total HP affects damage. | C03 | [s152][s152] | NU | D: —; A: — |

## F08 — Drones

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F08.01 | Add/remove drone stacks, change stored/active quantities, and enforce drone count, storage and bandwidth rules. | C04 | [s053][s053], [s014][s014] | NUP | D: —; A: — |
| F08.02 | Activate/deactivate selected stacks and fill the bay with supported add-stack choices; calculate only the intended active count. | C04 | [s068][s068], [s195][s195] | NUP | D: —; A: — |
| F08.03 | Split, merge and clone stacks without losing active counts, item identity or mutation differences. | C04 | [s193][s193], [s194][s194], [s191][s191] | NUP | D: —; A: — |
| F08.04 | Change drone variations; show damage, range, tracking, velocity, volume and resource changes. | C04 | [s190][s190], [s053][s053] | NUP | D: —; A: — |
| F08.05 | Show per-drone HP/EHP and shield regeneration under the chosen damage pattern; support combat, mining, salvage, logistics and EWAR drone behavior. | C04 | [s148][s148], [s149][s149], [s014][s014] | NU | D: —; A: — |

## F09 — Fighters

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F09.01 | Add/remove light, heavy and support fighter squadrons; show squadron size, stored/active counts and tube/category limits. | C05 | [s054][s054], [s015][s015] | NUP | D: —; A: — |
| F09.02 | Edit squadron quantity, activate/deactivate and replace variants; invalid merges/counts preserve valid state. | C05 | [s196][s196], [s197][s197], [s054][s054] | NUP | D: —; A: — |
| F09.03 | Toggle each supported fighter ability independently; damage, propulsion and EWAR effects follow ability state and survive restart. | C05 | [s071][s071], [s016][s016], [s144][s144] | NUP | D: —; A: — |

## F10 — Characters and skills

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F10.01 | Choose All 0, All 5 or an offline custom character; distinguish per-fit from global character selection. | C06 | [s230][s230], [s157][s157], [s233][s233] | NUP | D: —; A: — |
| F10.02 | Create, name, duplicate and delete custom profiles with duplicate-name and protected built-in handling. | C06 | [s157][s157], [s230][s230] | UP | D: —; A: — |
| F10.03 | Search/browse skill groups and change selected levels 0–5; dependent bonuses recalculate. | C06 | [s157][s157] | NUP | D: —; A: — |
| F10.04 | Save, save-as and revert pending skill edits; switching profiles does not silently lose changes. | C06 | [s157][s157], [s220][s220] | NUP | D: —; A: — |
| F10.05 | Apply/remove Alpha clone caps without replacing underlying learned skills. | C06 | [s157][s157], [s230][s230] | NUP | D: —; A: — |
| F10.06 | Set character security status and propagate it to fits using the character default. | C06 | [s157][s157], [s230][s230] | NUP | D: —; A: — |
| F10.07 | Import supported character XML and clipboard skill text; export skill text and fit-required skills to text/EVEMon formats. | I02.07 | [s230][s230], [s157][s157], [s220][s220] | XUP | D: —; A: — |

## F11 — Implants

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F11.01 | Add/remove/toggle implants and replace variations with correct slot conflicts and bonuses. | C07 | [s055][s055], [s187][s187] | NUP | D: —; A: — |
| F11.02 | Choose character versus fit-specific implants and move implants between supported locations; preserve each collection. | C07 | [s055][s055], [s173][s173] | NUP | D: —; A: — |
| F11.03 | Create/rename/duplicate/delete implant sets, edit their contents and apply a set to a fit/character as supported. | C07 | [s156][s156], [s234][s234], [s085][s085] | NUP | D: —; A: — |
| F11.04 | Save current implants as a named set; applying or editing sets updates dependent fits without aliasing an unintended collection. | C07 | [s086][s086], [s188][s188] | NUP | D: —; A: — |

## F12 — Boosters

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F12.01 | Add/remove/toggle boosters and replace variations, respecting applicable slots and showing duration. | C08 | [s050][s050], [s012][s012], [s152][s152] | NUP | D: —; A: — |
| F12.02 | Enable/disable each available booster side effect independently; expose active side effects and preserve them across reopen. | C08 | [s062][s062], [s163][s163], [s155][s155] | NUP | D: —; A: — |

## F13 — Heat, reload and adaptive mechanics

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F13.01 | Calculate valid offline/online/active/overheated transitions for local and projected modules; returning to the prior state restores values. | C09 | [s019][s019], [s177][s177], [s180][s180] | NU | D: —; A: — |
| F13.02 | Show estimated time to heat burnout per module with rack position/empty-slot effects and full detail precision. | C09 | [s150][s150] | NU | D: —; A: — |
| F13.03 | Toggle factoring reload into damage, capacitor and tank; loaded/empty ancillary and cap-booster behavior matches desktop. | C09 | [s070][s070], [s120][s120], [s019][s019] | NUP | D: —; A: — |
| F13.04 | Set per-module spool cycles and reset to global default; distinguish default from explicit zero and update linked damage/repair stats. | C09 | [s097][s097], [s176][s176] | NUP | D: —; A: — |
| F13.05 | Assign a reactive armor hardener damage pattern, including fit-pattern/default behavior; remove/change it and restore resists. | C09 | [s096][s096], [s233][s233] | NUP | D: —; A: — |

## F14 — Mutations

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F14.01 | Convert eligible modules and drones with a selected mutaplasmid; preserve base identity and exact rolled attributes. | C10 | [s090][s090], [s020][s020] | NUP | D: —; A: — |
| F14.02 | Edit each rolled attribute numerically/by slider with converted units, ranges and high-is-good direction including negative-base attributes. | C10 | [s112][s112], [s105][s105], [s021][s021] | NUP | D: —; A: — |
| F14.03 | Reset defaults, randomize within supported limits, revert unsaved mutations and revert the item to its base type; undo restores exact values. | C10 | [s112][s112], [s205][s205], [s192][s192] | NUP | D: —; A: — |
| F14.04 | Copy/import module and drone mutation text without lossy rounding; handle malformed or mismatched attributes without corrupting a fit. | I02.06 | [s240][s240], [s095][s095] | XUP | D: —; A: — |
| F14.05 | Optionally resolve supported dynamic-item links online; save resolved rolls for subsequent offline use and allow manual entry without network. | I03.04 | [s241][s241] | XOP | D: —; A: — |

## F15 — Projections

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F15.01 | Add individual projected modules, load charges/change variants and expose their state/range; removal restores recipient baseline. | D01 | [s057][s057], [s216][s216], [s217][s217] | NUP | D: —; A: — |
| F15.02 | Add projected drone stacks and change quantity/state/variant/range; only the intended active effects apply. | D01 | [s213][s213], [s168][s168], [s169][s169] | NUP | D: —; A: — |
| F15.03 | Add projected fighters, change quantity/state/range and individual ability states, then remove them cleanly. | D01 | [s215][s215], [s214][s214], [s170][s170] | NUP | D: —; A: — |
| F15.04 | Link a saved or currently open source fit; edit projected source count, active state and range, and navigate back to edit the source. | D01 | [s072][s072], [s073][s073], [s074][s074], [s182][s182] | NUP | D: [partial A04 host case](../../tools/android_reference/PROJECTIONS.md); A: [partial A08 native case](evidence/a08-native.json) |
| F15.05 | Project a selected item or library fit onto the active fit; prevent unsupported duplicates/self-links according to the desktop's actual rules. | D01 | [s091][s091], [s129][s129], [s181][s181] | NUP | D: —; A: — |
| F15.06 | Bulk change projection state/range and remove selected projectors; quantities and m/km conversions match reference. | D01 | [s212][s212], [s211][s211], [s218][s218] | NUP | D: —; A: — |
| F15.07 | Recalculate all recipients after source modules, skills, implants, charges or state change; avoid stale effects after repeated apply/remove and source deletion. | D02 | [s017][s017], [s233][s233] | NUP | D: [partial A04 host case](../../tools/android_reference/PROJECTIONS.md); A: [partial A08 native case](evidence/a08-native.json) |
| F15.08 | Match multiple-source stacking for EWAR, remote support, falloff/range and effect resistance; test inactive, zero-range and beyond-range cases. | D02 | [s017][s017], [s006][s006] | NU | D: [partial A04 host case](../../tools/android_reference/PROJECTIONS.md); A: [partial A08 native case](evidence/a08-native.json) |
| F15.09 | Match remote shield/armor/hull repairs and capacitor transfers/drains including reciprocal links; discover cycle behavior in the reference before choosing any guard. | D02 | [s017][s017], [s007][s007] | NUP | D: —; A: — |
| F15.10 | Combine projected effects, commands and environments; compare order changes, shared recipients and complete removal against the pinned reference. | D02 | [s017][s017] | NUP | D: —; A: — |

## F16 — Command fits and bursts

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F16.01 | Add command-source fits from the browser/open fits, enable/disable/remove them and navigate to the source fit. | D03 | [s052][s052], [s066][s066], [s165][s165] | NUP | D: [partial A05 host case](../../tools/android_reference/COMMANDS.md); A: [partial A09 native case](evidence/a09-native.json) |
| F16.02 | Calculate every supported command burst charge using actual source hull, modules, skills, implants and states; editing the source updates recipients. | D03 | [s017][s017], [s152][s152] | NUP | D: [partial A05 host case](../../tools/android_reference/COMMANDS.md); A: [partial A09 native case](evidence/a09-native.json) |
| F16.03 | Combine multiple command sources with correct per-bonus selection/stacking; test source/recipient overlap and commands plus projections. | D03 | [s017][s017], [s167][s167] | NUP | D: —; A: — |
| F16.04 | Persist command links and enabled states, then toggle/remove/re-add sources without duplicate or stale bonuses. | D03 | [s166][s166], [s017][s017] | NUP | D: [partial A05 host case](../../tools/android_reference/COMMANDS.md); A: [partial A09 native case](evidence/a09-native.json) |

## F17 — Environments and security

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F17.01 | Enumerate pinned-data wormhole effects (all six types and available classes); add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.02 | Enumerate pinned-data Abyssal weather (all five weather families and available strengths); add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.03 | Enumerate pinned-data metaliminal storms; add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.04 | Enumerate pinned-data Sansha incursions; add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.05 | Enumerate pinned-data Drifter incursions; add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.06 | Enumerate pinned-data Triglavian invasions; add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.07 | Enumerate pinned-data FW/insurgency effects; add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.08 | Enumerate pinned-data IHub upgrades; add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.09 | Enumerate pinned-data localized effects exposed under the environment groups; add/toggle/remove each offered effect and compare applicable attributes and restoration. | D04 | [s069][s069] | NUP | D: —; A: — |
| F17.10 | Choose structure system security: high, low, null and W-space; recalculate security-dependent effects. | D04 | [s076][s076], [s172][s172] | NUP | D: —; A: — |
| F17.11 | Choose character-derived or custom pilot security (-10 to 5); supported CONCORD hull bonuses follow the selected source. | D04 | [s075][s075], [s171][s171] | NUP | D: —; A: — |

## F18 — Damage patterns and target profiles

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F18.01 | Create/rename/duplicate/delete damage patterns and edit EM/thermal/kinetic/explosive components with desktop validation/normalization. | D05 | [s223][s223], [s231][s231] | NUP | D: —; A: — |
| F18.02 | Choose global/per-fit damage patterns and derive a pattern from ammunition; tank and drone defenses update without changing outgoing ammo. | D05 | [s067][s067], [s061][s061], [s233][s233] | NUP | D: —; A: — |
| F18.03 | Create/rename/duplicate/delete target profiles and edit four resists, maximum speed, signature radius, physical radius and total HP. | D05 | [s228][s228], [s246][s246] | NUP | D: —; A: — |
| F18.04 | Select/clear target profiles for fits/graphs; blank infinite-size/HP semantics and physical versus signature radius remain distinct. | D05 | [s228][s228], [s103][s103], [s102][s102] | NUP | D: —; A: — |
| F18.05 | Import/export damage patterns and target profiles via clipboard with validation and stable names/values. | I02.07 | [s223][s223], [s228][s228] | XUP | D: —; A: — |

## F19 — Graphs

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F19.01 | Plot reference-matched samples with all offered axis combinations and inputs: Distance, time, target speed or signature radius on X; raw/effective DPS, volley or accumulated damage on Y; attacker/target speed and angle, distance and target signature inputs. | G01 | [s029][s029], [s028][s028] | NGU | D: —; A: — |
| F19.02 | Plot reference-matched samples with all offered axis combinations and inputs: Application by range with DPS/volley, attacker/target velocity vectors and target signature; optimized compatible ammo including charge segmentation and T1/Navy/All tiers. | G02 | [s025][s025], [s024][s024] | NGU | D: —; A: — |
| F19.03 | Plot reference-matched samples with all offered axis combinations and inputs: Time/cap amount inputs; capacitor amount or regeneration outputs, initial capacitor percentage and capacitor simulator toggle. | G03 | [s027][s027], [s026][s026] | NGU | D: —; A: — |
| F19.04 | Plot reference-matched samples with all offered axis combinations and inputs: Time/shield amount inputs, regeneration and shield values, starting shield percentage, raw/effective HP modes tied to the damage pattern. | G04 | [s041][s041], [s040][s040] | NGU | D: —; A: — |
| F19.05 | Plot reference-matched samples with all offered axis combinations and inputs: Range/time inputs, repair rate or accumulated repairs, per-layer repair contributions and ancillary reload option. | G05 | [s039][s039], [s038][s038] | NGU | D: —; A: — |
| F19.06 | Plot reference-matched samples with all offered axis combinations and inputs: Target signature radius input and lock time output with each selected fit scan resolution. | G06 | [s035][s035], [s034][s034] | NGU | D: —; A: — |
| F19.07 | Plot reference-matched samples with all offered axis combinations and inputs: Time/distance inputs and speed, distance, momentum, bump speed/distance outputs with target mass and inertia inputs. | G07 | [s037][s037], [s036][s036] | NGU | D: —; A: — |
| F19.08 | Plot reference-matched samples with all offered axis combinations and inputs: Warp distance in AU/km versus warp time; fit maximum warp distance and warp-speed assumptions. | G08 | [s043][s043], [s042][s042] | NGU | D: —; A: — |
| F19.09 | Plot reference-matched samples with all offered axis combinations and inputs: Range against neut rate, web speed reduction, combined ECM strength, damp lock-range reduction, turret optimal reduction, missile range reduction and target-paint strength; target resistance input. | G09 | [s033][s033], [s032][s032] | NGU | D: —; A: — |
| F19.10 | Plot reference-matched samples with all offered axis combinations and inputs: Enemy scan resolution/DPS, lock time/uptime, inflicted damage, uptime adjustment/limit, apply-damps and use-drones controls. | G10 | [s031][s031], [s030][s030] | NGU | D: —; A: — |
| F19.11 | Compare multiple attacker fits against multiple fits/target profiles; add/remove/select entries and refresh after fit edits without mutating saved fits. | G11 | [s046][s046], [s049][s049] | NGU | D: —; A: — |
| F19.12 | Edit axis ranges, speed/angle vectors, show legend, force Y=0 and adjust curve color/lightness/line style. | G11 | [s045][s045], [s048][s048], [s047][s047] | GU | D: —; A: — |
| F19.13 | Inspect cursor/sample annotations and pointer navigation; retain precise values through touch controls. Export availability remains an explicit audit question. | G11 | [s044][s044] | GU | D: —; A: — |
| F19.14 | Toggle projected items and target resists, plus Auto/Stick to Target/Stick to Attacker drone modes in damage graphs. | G01 | [s079][s079], [s081][s081], [s080][s080] | NGU | D: —; A: — |
| F19.15 | Toggle projected effects/target resists during ammo optimization; change ammo color/pattern/no-style and tier filters without stale caches. | G02 | [s077][s077], [s078][s078], [s045][s045], [s023][s023] | NGU | D: —; A: — |
| F19.16 | Plot a fit using alternative compatible ammo without editing its saved loadout. | G11 | [s083][s083] | NGU | D: —; A: — |
| F19.17 | Enable/ignore drone control range and lock range restrictions; verify resulting curve cutoffs and markers where the selected graph supports them. | G11 | [s082][s082], [s084][s084] | NGU | D: —; A: — |
| F19.18 | Choose target resistance mode: Auto, shield, armor, hull or weighted average, and profile/no-profile selection. | G11 | [s099][s099], [s103][s103] | NGU | D: —; A: — |

## F20 — Interchange and sharing

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F20.01 | Import/export EFT text and named ship .cfg files; preserve supported empty slots/states/charges and report malformed or unknown items. | I01 | [s237][s237], [s241][s241] | XUP | D: —; A: — |
| F20.02 | Choose EFT inclusion of loaded charges, mutated attributes, implants, boosters and cargo; retain choices and share via phone clipboard/files. | I01 | [s158][s158], [s237][s237] | XUP | D: —; A: — |
| F20.03 | Import/export DNA and supported chat/alternate DNA syntax, including formatting tags; document format limitations rather than invent round-trip fidelity. | I02.01 | [s235][s235], [s241][s241], [s158][s158] | XUP | D: —; A: — |
| F20.04 | Import/export XML files including Pyfa extensions, fit collections and supported relationships/mutations; explicitly enumerate fields that XML cannot preserve. | I02.02 | [s244][s244], [s241][s241] | XUP | D: —; A: — |
| F20.05 | Export EFS fit/type data with implemented weapon/fighter/projection fields and errors for unsupported effects; EFS import is not an exposed desktop path. | I02.03 | [s236][s236], [s158][s158] | XU | D: —; A: — |
| F20.06 | Export multibuy text with loaded-charge, cargo, implant and booster options and optional cheaper-equivalent selection; show quantity/format loss clearly. | I02.04 | [s239][s239], [s158][s158] | XU | D: —; A: — |
| F20.07 | Export formatted fit statistics with damage, defenses, tank and miscellaneous fields using the current assumptions. | I02.05 | [s243][s243], [s158][s158] | XU | D: —; A: — |
| F20.08 | Export current/base item attributes to CSV with correct units and Unicode names. | I02.05 | [s107][s107] | XU | D: —; A: — |
| F20.09 | Copy all/selected and paste drone, fighter, cargo, implant and booster additions with supported quantities and mutation fields. | I02.06 | [s058][s058], [s059][s059], [s060][s060], [s242][s242], [s237][s237] | XUP | D: —; A: — |
| F20.10 | Export all fittings to styled or minimal HTML with fitting links and selected destination; validate Unicode and embedded fitting data. | I02.08 | [s229][s229], [s123][s123] | XU | D: —; A: — |
| F20.11 | Import/export ESI JSON fitting data independently of live login; declare unsupported state/relationship loss and loaded-charge/implant/booster options. | I03.03 | [s238][s238], [s241][s241], [s160][s160] | XUP | D: —; A: — |
| F20.12 | Route clipboard/file imports to the detected fit or addition format; empty/invalid input and multi-file failures leave saved work recoverable. | I01 | [s241][s241], [s220][s220] | XUP | D: —; A: — |

## F21 — Optional online refresh and prices

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F21.01 | Add/remove ESI identities, select the supported server and authenticate via an Android return path; cancellation, expiry and offline startup leave local fits usable. | I03.01 | [s226][s226], [s160][s160], [s232][s232], [s121][s121] | OUP | D: —; A: — |
| F21.02 | Link a local character and refresh skills/security online; retain cached values and age offline without overwriting pending edits silently. | I03.02 | [s157][s157], [s230][s230] | NOUP | D: —; A: — |
| F21.03 | Browse/download ESI fits and upload a selected fit with supported inclusion options; preserve useful failure messages and local copies. | I03.03 | [s160][s160], [s232][s232] | XOUP | D: —; A: — |
| F21.04 | Explicitly delete selected/all remote fittings only on the user's action with clear confirmation; cancel/failure does not delete local fits. | I03.03 | [s160][s160] | XOU | D: —; A: — |
| F21.05 | Choose preferred price source/system and use fallback behavior; timeout/missing values stay distinguishable from zero and cached prices carry age. | I04 | [s245][s245], [s125][s125] | OUP | D: —; A: — |
| F21.06 | Show item price and ship/modules/drones+fighters/cargo/implants+boosters/total ISK breakdown with detail precision. | I04 | [s153][s153], [s138][s138], [s139][s139] | NUP | D: —; A: — |
| F21.07 | Toggle drones, cargo and character additions in price totals; compact/full views use the same inclusion rules. | I04 | [s098][s098], [s125][s125] | NUP | D: —; A: — |
| F21.08 | Optimize fit price using supported equivalent replacements; review resulting substitutions and preserve calculations/undo where the desktop does. | I04 | [s245][s245], [s220][s220], [s189][s189] | NOU | D: —; A: — |
| F21.09 | Clear cached prices explicitly; offline missing-price state and later refresh recover correctly. | I04 | [s119][s119], [s245][s245] | OUP | D: —; A: — |

## F22 — Preferences, overrides and app equivalents

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F22.01 | Persist global reload and default spool-percentage settings and recalculate affected open/linked fits; per-module overrides retain precedence. | I06.01 | [s120][s120], [s233][s233] | NUP | D: —; A: — |
| F22.02 | Toggle strict skill dependencies; reducing a prerequisite resets dependent skills exactly as desktop, with visible changes. | I06.01 | [s120][s120], [s230][s230] | NUP | D: —; A: — |
| F22.03 | Persist global/per-fit character and damage-pattern choices plus default use of character implants for new fits. | I06.01 | [s122][s122], [s233][s233] | NUP | D: —; A: — |
| F22.04 | Select available compact/full/hidden statistics panels while keeping hidden values reachable; firepower/mining toggling still works. | I06.02 | [s127][s127], [s227][s227] | UP | D: —; A: — |
| F22.05 | Preserve fitting rack separation/labels, slot coloring, tab/browser/skills details, gauge animation and new-page/reopen choices through appropriate phone controls. | I06.02 | [s122][s122] | UP | D: —; A: — |
| F22.06 | Choose expanded mutation names and additions-tab active/all/none quantity summaries. | I06.02 | [s122][s122], [s146][s146] | UP | D: —; A: — |
| F22.07 | Enable/disable optional context actions while keeping a touch equivalent of show-all: pattern, skills, variants, project, fill module/cargo, spool, additions copy/paste. | I06.02 | [s118][s118] | UP | D: —; A: — |
| F22.08 | Configure market search delay, shortcuts and meta-filter behavior on search/recents, group selection, empty view and item jumps. | I06.02 | [s125][s125] | UP | D: —; A: — |
| F22.09 | Choose UI and EVE-data language including auto/fallback; bundle required translations/data, format Unicode/numbers/units and retain the choice offline. | I06.03 | [s122][s122], [s002][s002] | UP | D: —; A: — |
| F22.10 | Search item attributes and create/edit/remove global attribute overrides; enable/disable all overrides and restore exact baseline values. | I06.04 | [s224][s224], [s022][s022], [s220][s220] | NUP | D: —; A: — |
| F22.11 | Import/export overrides CSV and clear all with explicit confirmation; reject malformed values without partially corrupting existing overrides. | I06.04 | [s224][s224] | XUP | D: —; A: — |
| F22.12 | Provide network master/per-service switches for ESI, prices and update checks; disabled refresh never gates local calculations. | I06.05 | [s126][s126] | OUP | D: —; A: — |
| F22.13 | Preserve the capability of no/automatic/manual proxy settings through a supported Android equivalent; credentials remain private. Resolve platform behavior in the task. | I06.05 | [s126][s126] | OU | D: —; A: — |
| F22.14 | Expose app/source/data versions, notices and help links plus accessible diagnostics/export without private tokens or fits in public logs. | I06.06 | [s221][s221], [s124][s124], [s159][s159] | UP | D: —; A: — |
| F22.15 | Account for desktop widget inspection, log dump and developer fit-test controls with an explicit Android disposition; no silent omission or runtime parity claim. | I06.06 | [s220][s220], [s159][s159], [s124][s124] | U | D: —; A: — |
| F22.16 | Preserve optional update checks, prerelease choice, suppressed-notification reset and download action; agree the personal-APK delivery equivalent before claiming this row verified. | I06.07 | [s128][s128] | OUP | D: —; A: — |
| F22.17 | Explicitly clear damage patterns/target profiles with confirmation and safe handling of fits that reference them. | I05.02 | [s119][s119] | NUP | D: —; A: — |

## F23 — Offline data, backups and upgrades

| ID | Observable behavior / acceptance target | Owner | Sources | Checks | Evidence |
| --- | --- | --- | --- | --- | --- |
| F23.01 | Install bundled pinned game data and calculate on a fresh launch without network/account/PC or initial download. | A07 | [s003][s003], [s008][s008], [s009][s009] | NOP | D: [A01 sample](../../tools/android_reference/README.md); A: [A07 partial](evidence/a07-native.json): fresh offline install and baseline calculation; process restart remains R01 verification |
| F23.02 | Validate a new dataset/source version before activation, reconcile changed/removed types and preserve recoverable user state on interrupted or failed updates. | I05.01 | [s003][s003], [s010][s010] | NOP | D: —; A: — |
| F23.03 | Back up and restore fits plus linked state, characters, settings and profiles; document differences between desktop XML fit backup and a complete Android user backup. | I05.02 | [s241][s241], [s011][s011] | XNUP | D: —; A: — |
| F23.04 | Install over a previous APK with stable signing/versioning, required notices and source/data identification while preserving user fits and linked effects. | R02 | [s010][s010], [s001][s001] | UP | D: —; A: — |
| F23.05 | Verify all inventory rows offline where applicable, including first launch, process restart and interacting-fit edits; any missing row blocks full parity. | R01 | [s005][s005], [s004][s004] | NOP | D: —; A: — |

## Source references

All upstream links are pinned; Android requirement links are local.

[s001]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/LICENSE "LICENSE"
[s002]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/config.py "config.py"
[s003]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/db_update.py "db_update.py"
[s004]: DEVELOPMENT.md "docs/android/DEVELOPMENT.md"
[s005]: SCOPE.md "docs/android/SCOPE.md"
[s006]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/calc.py "eos/calc.py"
[s007]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/capSim.py "eos/capSim.py"
[s008]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/config.py "eos/config.py"
[s009]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/db/gamedata/__init__.py "eos/db/gamedata/__init__.py"
[s010]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/db/migration.py "eos/db/migration.py"
[s011]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/db/saveddata/__init__.py "eos/db/saveddata/__init__.py"
[s012]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/booster.py "eos/saveddata/booster.py"
[s013]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/citadel.py "eos/saveddata/citadel.py"
[s014]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/drone.py "eos/saveddata/drone.py"
[s015]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/fighter.py "eos/saveddata/fighter.py"
[s016]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/fighterAbility.py "eos/saveddata/fighterAbility.py"
[s017]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/fit.py "eos/saveddata/fit.py"
[s018]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/mode.py "eos/saveddata/mode.py"
[s019]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/module.py "eos/saveddata/module.py"
[s020]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/mutatedMixin.py "eos/saveddata/mutatedMixin.py"
[s021]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/mutator.py "eos/saveddata/mutator.py"
[s022]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/eos/saveddata/override.py "eos/saveddata/override.py"
[s023]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitApplicationProfile/calc/optimize_ammo.py "graphs/data/fitApplicationProfile/calc/optimize_ammo.py"
[s024]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitApplicationProfile/getter.py "graphs/data/fitApplicationProfile/getter.py"
[s025]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitApplicationProfile/graph.py "graphs/data/fitApplicationProfile/graph.py"
[s026]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitCapacitor/getter.py "graphs/data/fitCapacitor/getter.py"
[s027]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitCapacitor/graph.py "graphs/data/fitCapacitor/graph.py"
[s028]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitDamageStats/getter.py "graphs/data/fitDamageStats/getter.py"
[s029]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitDamageStats/graph.py "graphs/data/fitDamageStats/graph.py"
[s030]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEcmBurstScanresDamps/getter.py "graphs/data/fitEcmBurstScanresDamps/getter.py"
[s031]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEcmBurstScanresDamps/graph.py "graphs/data/fitEcmBurstScanresDamps/graph.py"
[s032]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEwarStats/getter.py "graphs/data/fitEwarStats/getter.py"
[s033]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitEwarStats/graph.py "graphs/data/fitEwarStats/graph.py"
[s034]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitLockTime/getter.py "graphs/data/fitLockTime/getter.py"
[s035]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitLockTime/graph.py "graphs/data/fitLockTime/graph.py"
[s036]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitMobility/getter.py "graphs/data/fitMobility/getter.py"
[s037]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitMobility/graph.py "graphs/data/fitMobility/graph.py"
[s038]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitRemoteReps/getter.py "graphs/data/fitRemoteReps/getter.py"
[s039]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitRemoteReps/graph.py "graphs/data/fitRemoteReps/graph.py"
[s040]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitShieldRegen/getter.py "graphs/data/fitShieldRegen/getter.py"
[s041]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitShieldRegen/graph.py "graphs/data/fitShieldRegen/graph.py"
[s042]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitWarpTime/getter.py "graphs/data/fitWarpTime/getter.py"
[s043]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/data/fitWarpTime/graph.py "graphs/data/fitWarpTime/graph.py"
[s044]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/gui/canvasPanel.py "graphs/gui/canvasPanel.py"
[s045]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/gui/ctrlPanel.py "graphs/gui/ctrlPanel.py"
[s046]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/gui/lists.py "graphs/gui/lists.py"
[s047]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/gui/stylePickers.py "graphs/gui/stylePickers.py"
[s048]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/gui/vector.py "graphs/gui/vector.py"
[s049]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/graphs/wrapper.py "graphs/wrapper.py"
[s050]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/boosterView.py "gui/builtinAdditionPanes/boosterView.py"
[s051]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/cargoView.py "gui/builtinAdditionPanes/cargoView.py"
[s052]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/commandView.py "gui/builtinAdditionPanes/commandView.py"
[s053]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/droneView.py "gui/builtinAdditionPanes/droneView.py"
[s054]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/fighterView.py "gui/builtinAdditionPanes/fighterView.py"
[s055]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/implantView.py "gui/builtinAdditionPanes/implantView.py"
[s056]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/notesView.py "gui/builtinAdditionPanes/notesView.py"
[s057]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinAdditionPanes/projectedView.py "gui/builtinAdditionPanes/projectedView.py"
[s058]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/additionsExportAll.py "gui/builtinContextMenus/additionsExportAll.py"
[s059]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/additionsExportSelection.py "gui/builtinContextMenus/additionsExportSelection.py"
[s060]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/additionsImport.py "gui/builtinContextMenus/additionsImport.py"
[s061]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/ammoToDmgPattern.py "gui/builtinContextMenus/ammoToDmgPattern.py"
[s062]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/boosterSideEffects.py "gui/builtinContextMenus/boosterSideEffects.py"
[s063]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/cargoAdd.py "gui/builtinContextMenus/cargoAdd.py"
[s064]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/cargoAddAmmo.py "gui/builtinContextMenus/cargoAddAmmo.py"
[s065]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/cargoFill.py "gui/builtinContextMenus/cargoFill.py"
[s066]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/commandFitAdd.py "gui/builtinContextMenus/commandFitAdd.py"
[s067]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/damagePatternChange.py "gui/builtinContextMenus/damagePatternChange.py"
[s068]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/droneAddStack.py "gui/builtinContextMenus/droneAddStack.py"
[s069]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/envEffectAdd.py "gui/builtinContextMenus/envEffectAdd.py"
[s070]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/factorReload.py "gui/builtinContextMenus/factorReload.py"
[s071]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fighterAbilities.py "gui/builtinContextMenus/fighterAbilities.py"
[s072]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitAddBrowse.py "gui/builtinContextMenus/fitAddBrowse.py"
[s073]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitAddCurrentlyOpen.py "gui/builtinContextMenus/fitAddCurrentlyOpen.py"
[s074]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitOpenNewTab.py "gui/builtinContextMenus/fitOpenNewTab.py"
[s075]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitPilotSecurity.py "gui/builtinContextMenus/fitPilotSecurity.py"
[s076]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/fitSystemSecurity.py "gui/builtinContextMenus/fitSystemSecurity.py"
[s077]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphAmmoOptimalApplyProjected.py "gui/builtinContextMenus/graphAmmoOptimalApplyProjected.py"
[s078]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphAmmoOptimalIgnoreResists.py "gui/builtinContextMenus/graphAmmoOptimalIgnoreResists.py"
[s079]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDmgApplyProjected.py "gui/builtinContextMenus/graphDmgApplyProjected.py"
[s080]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDmgDroneMode.py "gui/builtinContextMenus/graphDmgDroneMode.py"
[s081]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDmgIgnoreResists.py "gui/builtinContextMenus/graphDmgIgnoreResists.py"
[s082]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphDroneControlRange.py "gui/builtinContextMenus/graphDroneControlRange.py"
[s083]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphFitAmmoPicker.py "gui/builtinContextMenus/graphFitAmmoPicker.py"
[s084]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/graphLockRange.py "gui/builtinContextMenus/graphLockRange.py"
[s085]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/implantSetApply.py "gui/builtinContextMenus/implantSetApply.py"
[s086]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/implantSetSave.py "gui/builtinContextMenus/implantSetSave.py"
[s087]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemAmountChange.py "gui/builtinContextMenus/itemAmountChange.py"
[s088]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemFill.py "gui/builtinContextMenus/itemFill.py"
[s089]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemMarketJump.py "gui/builtinContextMenus/itemMarketJump.py"
[s090]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemMutations.py "gui/builtinContextMenus/itemMutations.py"
[s091]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemProject.py "gui/builtinContextMenus/itemProject.py"
[s092]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/itemVariationChange.py "gui/builtinContextMenus/itemVariationChange.py"
[s093]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleAmmoChange.py "gui/builtinContextMenus/moduleAmmoChange.py"
[s094]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleFill.py "gui/builtinContextMenus/moduleFill.py"
[s095]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleMutatedExport.py "gui/builtinContextMenus/moduleMutatedExport.py"
[s096]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleRahPattern.py "gui/builtinContextMenus/moduleRahPattern.py"
[s097]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/moduleSpool.py "gui/builtinContextMenus/moduleSpool.py"
[s098]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/priceOptions.py "gui/builtinContextMenus/priceOptions.py"
[s099]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/resistMode.py "gui/builtinContextMenus/resistMode.py"
[s100]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/shipModeChange.py "gui/builtinContextMenus/shipModeChange.py"
[s101]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/skillAffectors.py "gui/builtinContextMenus/skillAffectors.py"
[s102]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/targetProfile/adder.py "gui/builtinContextMenus/targetProfile/adder.py"
[s103]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinContextMenus/targetProfile/switcher.py "gui/builtinContextMenus/targetProfile/switcher.py"
[s104]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/attributeGrouping.py "gui/builtinItemStatsViews/attributeGrouping.py"
[s105]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/attributeSlider.py "gui/builtinItemStatsViews/attributeSlider.py"
[s106]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemAffectedBy.py "gui/builtinItemStatsViews/itemAffectedBy.py"
[s107]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemAttributes.py "gui/builtinItemStatsViews/itemAttributes.py"
[s108]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemCompare.py "gui/builtinItemStatsViews/itemCompare.py"
[s109]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemDependants.py "gui/builtinItemStatsViews/itemDependants.py"
[s110]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemDescription.py "gui/builtinItemStatsViews/itemDescription.py"
[s111]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemEffects.py "gui/builtinItemStatsViews/itemEffects.py"
[s112]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemMutator.py "gui/builtinItemStatsViews/itemMutator.py"
[s113]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemProperties.py "gui/builtinItemStatsViews/itemProperties.py"
[s114]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemRequirements.py "gui/builtinItemStatsViews/itemRequirements.py"
[s115]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinItemStatsViews/itemTraits.py "gui/builtinItemStatsViews/itemTraits.py"
[s116]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinMarketBrowser/itemView.py "gui/builtinMarketBrowser/itemView.py"
[s117]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinMarketBrowser/marketTree.py "gui/builtinMarketBrowser/marketTree.py"
[s118]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaContextMenuPreferences.py "gui/builtinPreferenceViews/pyfaContextMenuPreferences.py"
[s119]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaDatabasePreferences.py "gui/builtinPreferenceViews/pyfaDatabasePreferences.py"
[s120]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaEnginePreferences.py "gui/builtinPreferenceViews/pyfaEnginePreferences.py"
[s121]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaEsiPreferences.py "gui/builtinPreferenceViews/pyfaEsiPreferences.py"
[s122]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaGeneralPreferences.py "gui/builtinPreferenceViews/pyfaGeneralPreferences.py"
[s123]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaHTMLExportPreferences.py "gui/builtinPreferenceViews/pyfaHTMLExportPreferences.py"
[s124]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaLoggingPreferences.py "gui/builtinPreferenceViews/pyfaLoggingPreferences.py"
[s125]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaMarketPreferences.py "gui/builtinPreferenceViews/pyfaMarketPreferences.py"
[s126]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaNetworkPreferences.py "gui/builtinPreferenceViews/pyfaNetworkPreferences.py"
[s127]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaStatViewPreferences.py "gui/builtinPreferenceViews/pyfaStatViewPreferences.py"
[s128]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinPreferenceViews/pyfaUpdatePreferences.py "gui/builtinPreferenceViews/pyfaUpdatePreferences.py"
[s129]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinShipBrowser/fitItem.py "gui/builtinShipBrowser/fitItem.py"
[s130]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinShipBrowser/navigationPanel.py "gui/builtinShipBrowser/navigationPanel.py"
[s131]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinShipBrowser/raceSelector.py "gui/builtinShipBrowser/raceSelector.py"
[s132]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/bombingViewFull.py "gui/builtinStatsViews/bombingViewFull.py"
[s133]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/capacitorViewFull.py "gui/builtinStatsViews/capacitorViewFull.py"
[s134]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/firepowerViewFull.py "gui/builtinStatsViews/firepowerViewFull.py"
[s135]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/miningyieldViewFull.py "gui/builtinStatsViews/miningyieldViewFull.py"
[s136]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/outgoingViewFull.py "gui/builtinStatsViews/outgoingViewFull.py"
[s137]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/outgoingViewMinimal.py "gui/builtinStatsViews/outgoingViewMinimal.py"
[s138]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/priceViewFull.py "gui/builtinStatsViews/priceViewFull.py"
[s139]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/priceViewMinimal.py "gui/builtinStatsViews/priceViewMinimal.py"
[s140]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/rechargeViewFull.py "gui/builtinStatsViews/rechargeViewFull.py"
[s141]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/resistancesViewFull.py "gui/builtinStatsViews/resistancesViewFull.py"
[s142]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/resourcesViewFull.py "gui/builtinStatsViews/resourcesViewFull.py"
[s143]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinStatsViews/targetingMiscViewMinimal.py "gui/builtinStatsViews/targetingMiscViewMinimal.py"
[s144]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/abilities.py "gui/builtinViewColumns/abilities.py"
[s145]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/attributeDisplay.py "gui/builtinViewColumns/attributeDisplay.py"
[s146]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/baseName.py "gui/builtinViewColumns/baseName.py"
[s147]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/capacitorUse.py "gui/builtinViewColumns/capacitorUse.py"
[s148]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/droneEhp.py "gui/builtinViewColumns/droneEhp.py"
[s149]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/droneRegen.py "gui/builtinViewColumns/droneRegen.py"
[s150]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/heat.py "gui/builtinViewColumns/heat.py"
[s151]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/maxRange.py "gui/builtinViewColumns/maxRange.py"
[s152]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/misc.py "gui/builtinViewColumns/misc.py"
[s153]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/price.py "gui/builtinViewColumns/price.py"
[s154]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/propertyDisplay.py "gui/builtinViewColumns/propertyDisplay.py"
[s155]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViewColumns/sideEffects.py "gui/builtinViewColumns/sideEffects.py"
[s156]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/builtinViews/implantEditor.py "gui/builtinViews/implantEditor.py"
[s157]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/characterEditor.py "gui/characterEditor.py"
[s158]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/copySelectDialog.py "gui/copySelectDialog.py"
[s159]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/devTools.py "gui/devTools.py"
[s160]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/esiFittings.py "gui/esiFittings.py"
[s161]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/__init__.py "gui/fitCommands/__init__.py"
[s162]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/__init__.py "gui/fitCommands/calc/__init__.py"
[s163]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/booster/sideEffectToggleState.py "gui/fitCommands/calc/booster/sideEffectToggleState.py"
[s164]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/cargo/changeAmount.py "gui/fitCommands/calc/cargo/changeAmount.py"
[s165]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/commandFit/add.py "gui/fitCommands/calc/commandFit/add.py"
[s166]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/commandFit/remove.py "gui/fitCommands/calc/commandFit/remove.py"
[s167]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/commandFit/toggleStates.py "gui/fitCommands/calc/commandFit/toggleStates.py"
[s168]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/drone/projectedChangeAmount.py "gui/fitCommands/calc/drone/projectedChangeAmount.py"
[s169]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/drone/projectedChangeProjectionRange.py "gui/fitCommands/calc/drone/projectedChangeProjectionRange.py"
[s170]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/fighter/projectedChangeProjectionRange.py "gui/fitCommands/calc/fighter/projectedChangeProjectionRange.py"
[s171]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/fitPilotSecurity.py "gui/fitCommands/calc/fitPilotSecurity.py"
[s172]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/fitSystemSecurity.py "gui/fitCommands/calc/fitSystemSecurity.py"
[s173]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/implant/changeLocation.py "gui/fitCommands/calc/implant/changeLocation.py"
[s174]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/itemRebase.py "gui/fitCommands/calc/itemRebase.py"
[s175]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/module/changeCharges.py "gui/fitCommands/calc/module/changeCharges.py"
[s176]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/module/changeSpool.py "gui/fitCommands/calc/module/changeSpool.py"
[s177]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/module/localChangeStates.py "gui/fitCommands/calc/module/localChangeStates.py"
[s178]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/module/localReplace.py "gui/fitCommands/calc/module/localReplace.py"
[s179]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/module/localSwap.py "gui/fitCommands/calc/module/localSwap.py"
[s180]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/module/projectedChangeStates.py "gui/fitCommands/calc/module/projectedChangeStates.py"
[s181]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/projectedFit/add.py "gui/fitCommands/calc/projectedFit/add.py"
[s182]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/projectedFit/changeAmount.py "gui/fitCommands/calc/projectedFit/changeAmount.py"
[s183]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/calc/shipModeChange.py "gui/fitCommands/calc/shipModeChange.py"
[s184]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/__init__.py "gui/fitCommands/gui/__init__.py"
[s185]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/cargo/changeMetas.py "gui/fitCommands/gui/cargo/changeMetas.py"
[s186]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/fitRestrictionToggle.py "gui/fitCommands/gui/fitRestrictionToggle.py"
[s187]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/implant/changeMeta.py "gui/fitCommands/gui/implant/changeMeta.py"
[s188]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/implant/setAdd.py "gui/fitCommands/gui/implant/setAdd.py"
[s189]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/itemsRebase.py "gui/fitCommands/gui/itemsRebase.py"
[s190]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localDrone/changeMetas.py "gui/fitCommands/gui/localDrone/changeMetas.py"
[s191]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localDrone/clone.py "gui/fitCommands/gui/localDrone/clone.py"
[s192]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localDrone/mutatedRevert.py "gui/fitCommands/gui/localDrone/mutatedRevert.py"
[s193]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localDrone/stackSplit.py "gui/fitCommands/gui/localDrone/stackSplit.py"
[s194]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localDrone/stacksMerge.py "gui/fitCommands/gui/localDrone/stacksMerge.py"
[s195]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localDrone/toggleStates.py "gui/fitCommands/gui/localDrone/toggleStates.py"
[s196]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localFighter/changeAmount.py "gui/fitCommands/gui/localFighter/changeAmount.py"
[s197]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localFighter/changeMetas.py "gui/fitCommands/gui/localFighter/changeMetas.py"
[s198]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/add.py "gui/fitCommands/gui/localModule/add.py"
[s199]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/changeCharges.py "gui/fitCommands/gui/localModule/changeCharges.py"
[s200]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/changeMetas.py "gui/fitCommands/gui/localModule/changeMetas.py"
[s201]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/changeStates.py "gui/fitCommands/gui/localModule/changeStates.py"
[s202]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/clone.py "gui/fitCommands/gui/localModule/clone.py"
[s203]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/fillAdd.py "gui/fitCommands/gui/localModule/fillAdd.py"
[s204]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/fillClone.py "gui/fitCommands/gui/localModule/fillClone.py"
[s205]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/mutatedRevert.py "gui/fitCommands/gui/localModule/mutatedRevert.py"
[s206]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/remove.py "gui/fitCommands/gui/localModule/remove.py"
[s207]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/replace.py "gui/fitCommands/gui/localModule/replace.py"
[s208]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModule/swap.py "gui/fitCommands/gui/localModule/swap.py"
[s209]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModuleCargo/cargoToLocalModule.py "gui/fitCommands/gui/localModuleCargo/cargoToLocalModule.py"
[s210]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/localModuleCargo/localModuleToCargo.py "gui/fitCommands/gui/localModuleCargo/localModuleToCargo.py"
[s211]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedChangeProjectionRange.py "gui/fitCommands/gui/projectedChangeProjectionRange.py"
[s212]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedChangeStates.py "gui/fitCommands/gui/projectedChangeStates.py"
[s213]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedDrone/add.py "gui/fitCommands/gui/projectedDrone/add.py"
[s214]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedFighter/abilityToggleState.py "gui/fitCommands/gui/projectedFighter/abilityToggleState.py"
[s215]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedFighter/add.py "gui/fitCommands/gui/projectedFighter/add.py"
[s216]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedModule/add.py "gui/fitCommands/gui/projectedModule/add.py"
[s217]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedModule/changeCharges.py "gui/fitCommands/gui/projectedModule/changeCharges.py"
[s218]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/fitCommands/gui/projectedRemove.py "gui/fitCommands/gui/projectedRemove.py"
[s219]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/itemStats.py "gui/itemStats.py"
[s220]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/mainFrame.py "gui/mainFrame.py"
[s221]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/mainMenuBar.py "gui/mainMenuBar.py"
[s222]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/marketBrowser.py "gui/marketBrowser.py"
[s223]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/patternEditor.py "gui/patternEditor.py"
[s224]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/propertyEditor.py "gui/propertyEditor.py"
[s225]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/shipBrowser.py "gui/shipBrowser.py"
[s226]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/ssoLogin.py "gui/ssoLogin.py"
[s227]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/statsPane.py "gui/statsPane.py"
[s228]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/targetProfileEditor.py "gui/targetProfileEditor.py"
[s229]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/gui/utils/exportHtml.py "gui/utils/exportHtml.py"
[s230]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/character.py "service/character.py"
[s231]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/damagePattern.py "service/damagePattern.py"
[s232]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/esi.py "service/esi.py"
[s233]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/fit.py "service/fit.py"
[s234]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/implantSet.py "service/implantSet.py"
[s235]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/dna.py "service/port/dna.py"
[s236]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/efs.py "service/port/efs.py"
[s237]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/eft.py "service/port/eft.py"
[s238]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/esi.py "service/port/esi.py"
[s239]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/multibuy.py "service/port/multibuy.py"
[s240]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/muta.py "service/port/muta.py"
[s241]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/port.py "service/port/port.py"
[s242]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/shared.py "service/port/shared.py"
[s243]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/shipstats.py "service/port/shipstats.py"
[s244]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/port/xml.py "service/port/xml.py"
[s245]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/price.py "service/price.py"
[s246]: https://github.com/Sussic/Pyfa-android/blob/8b04f3b271e614b3e103853b44a7851a63d79d0e/service/targetProfile.py "service/targetProfile.py"
