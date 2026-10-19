# C03.2 inspector acceptance matrix

Selected on `codex/c03-item-inspector`, from delivered C03.1 merge745fc1e2.
This matrix expands the existing C03.2 outcome; it does not close any parity row.
All F07.31–32 and F07.34–48 remain required together. C06 owns recursive skill
editing/navigation; I02.05 owns CSV and I04 owns optional network price refresh.

## Independent inventory

Run the [inventory exporter](../../../tools/android_reference/inspector_inventory.py)
with the installed reference interpreter, unchanged pinned checkout and bundled
database. It validates source8b04f3b271e614b3e103853b44a7851a63d79d0e, reads SQLite
with `mode=ro`, verifies integrity and records the complete logical digest. The
[inventory](../../../tools/android_reference/fixtures/inspector-inventory.json)
contains all2860 attribute IDs (1775 assigned),3419 effect IDs (3016 assigned),
60 units and1590 groups, including unpublished members. Its114 terminal return
paths cover every original misc/range/capacitor/attribute/property detail path;
all nested conditions include every command-burst ID and availability branch.
This is an enumeration, not calculated expected values or Android validation.

Source inspection confirms the inspector and equipment columns are unchanged
from the pinned reference. Every raw modified attribute must be included even
when metadata is missing; missing metadata must be explicit, never guessed.
Declaration lists are aids to property coverage: runtime enumeration must also
cover inherited and instance fields, rather than restricting to declarations.

## Field and behavior contracts

| Family | Original source and required values | Reference acceptance | Native acceptance |
| --- | --- | --- | --- |
| Targets and refresh | `gui/itemStats.py`; base market item, fitted ship/module/addition and loaded charge; fit ID/revision plus stable target identity | Ship, module, cargo/base item, drone/fighter/implant/booster/mode and loaded charges; rejection of removed/replaced/stale targets | Open from hull/equipment/fitted item/charge; refresh after edit/undo/redo; discard obsolete responses; recreation and fresh-process restart |
| Attributes | `itemAttributes.py`, `attributeGrouping.py`; internal name/metadata ID/display label/group, raw current/base, unit ID/name/display, published flag, precise and normal formatted values | Full current/base/raw member sets and ordered groups; effective base getters retain mutations/overrides; normal suppression of non-grouped zero, unpublished/missing metadata and required-skill fields; raw retains them | Mode toggles, case-insensitive search by name/ID, group expansion, exact values and copy; zero distinct from absent; all members reachable |
| Units | `eos/gamedata.py:Unit.PreformatValue`, original `ItemParams.FormatValue` | All60 unit definitions; percentages/milliseconds/boolean/type/group/attribute references and size class; format and precise raw values independently compared | Raw units stay distinct from transformed display units; finite numeric validation and typed reference values; no Kotlin fitting formulas |
| Description and traits | `itemDescription.py`, `itemTraits.py`; original rich text and readable plain copy text | Absent/present, multiline/non-ASCII, links/font markup; compare original HTML window plain text | Readable offline text, selection and copy-all, no loss of paragraphs or Unicode |
| Affectors | `itemAffectedBy.py`, EOS modified-attribute `iterAfflictions/getAfflictions/getOriginal`; source identity/type/fit, attribute, operator, stacking group, pre/post resistance amount, used/projected state | Local/linked projection/command/skill/item/charge afflictors; identical-item counts and changed-value filtering; source and attribute order; stacking/resistance and unused witness | Source/attribute and friendly/internal-name views, expand-all, source inspection, refresh; explicit unused detail without claiming it changes results |
| Variation comparison | `itemCompare.py`, existing market variation policy; union of named differing base attributes, absent cells, meta/name order, independent compare formatting, prices | Complete variation family and differing-column set; ascending/descending name/attribute/price order; raw/normal values; loaded charge/base item cases | Sort, highlight, navigate to variation, refresh, compare current/base context; cached price or explicit unavailable with age when known; no network requirement |
| Effects | `itemEffects.py`; full item effect names/IDs, implemented state, default activity, effect types and runtime | Compare every assigned effect and handler/Dummy distinctions; implemented false is not inactive false; absent runtime explicit | Full effect list/search/detail; metadata retained, no global debug effect mutation |
| Properties | `itemProperties.py`; enumerate `dir` excluding dunder, original getter exceptions skipped | Enumerate every supported public value including inherited/instance fields; primitive/structured values stable and precise; unsupported/private/callable members explicitly identified rather than fabricated values or process-address text | Search/detail/copy; unavailable getter or unsupported diagnostic member visibly distinguished; no mutation or desktop dependency |
| Equipment attributes/properties | `attributeDisplay.py`, `propertyDisplay.py` | CPU/power and arbitrary configured attribute/property, unit volume and stack volume; absence/zero behavior and precise underlying values | Full inspector provides underlying values even where compact desktop column is blank |
| Range and capacitor | `maxRange.py`, `capacitorUse.py` | Optimal/falloff>=5m; missile lower/upper range and chance; cap use and all9 regeneration groups via EOS `getCapRegenGainFromMod`; absent/non-applicable modes | Both compact/detail plus precise underlying values; unavailable distinct from true zero |

## Complete equipment dispatch

`misc.py:Miscellanea.__getData` owns the original presentation rules. Preserve
every enumerated branch and condition, including branches currently absent from
the dataset. Synthetic probes exercise absent-data branches without adding fake
game types to the production catalogue. Expectations must execute the unchanged
pinned methods; copied Android presentation cannot generate its own expectations.

| Families | Required underlying EOS fields and detail modes |
| --- | --- |
| Booster, doomsday, turret/combat drone, precursor, Vorton, fighter bomber | Booster duration; volley/duration and doomsday cycles; tracking/signature normalization; combat-drone special effects; default/pre/full spool damage/time; explosion radius/velocity; optimal signature |
| Subsystems, neut/nos, salvage/hacking, assault damage control, tackle | All slot modifiers; neut/transfer and average-cycle rate; access chance; virus strength/coherence; ability duration; signed warp strength |
| Web/paint/damp/disruption and structure/burst equivalents | Every effect-gated variant and modifier; maximum-magnitude display versus complete contributing values; tracking and missile disruption families |
| Weapon/drone upgrades, ECM, sensor/ECCM, cloak | Each weapon upgrade's original damage/rate attributes, drone bonus, all4 ECM/sensor strengths, range/resolution/sensor bonuses, recalibration time |
| Remote repair/capacitor and mutadaptive repair | Shield/armor/hull/cap transfer; default/pre/full spool and interval; availability and ignore-state semantics |
| Gang coordinator, all electronic/logistics/neut drone branches | Command visible/hidden bonus; paint/damp/disruption/ECM precedence; repair family and per-drone amounts; neut duration/rate |
| All mining/gas branches | Yield/drain per-second and per-hour, efficiency and zero-drain behavior; original EOS APIs |
| Jump drive/field/capital mobility, siege/cyno, scanners | Spool duration; fuel type and quantity; scan duration |
| All5 ancillary/cap booster groups | Shots/cycle/hp-before-reload; charge cap/armor/shield amounts; charged multiplier, damage-profile EHP switch for local repairs; duration/reload and5/10/25 charge batches; uncharged remote fallback |
| Reactive armor hardener | All4 shifted resistances and selected damage profile |
| Command bursts | All4 buff positions and every original ID10–26/60/2464/2465/2466/2468/2481/2516/2517, including repeated buffs, duration and radius; underlying values retained |
| Loaded missile/Vorton/bomb/probe/breacher charges | Every original missile group; explosion radius/velocity; bomb radius; probe strength/range; breacher duration, absolute/relative tick amounts, total and full-DPS HP threshold |

## Verification requirements

Reference generation uses the independent pinned wx/EOS interpreter with exact
dataset, skills/settings/fit state. Numeric comparisons retain REL1e-10/ABS1e-9,
units and original formatting. Coverage validation requires exact catalogue IDs,
original path/condition coverage and all selected model/property variants. Every
changed value must have an edit and reversal witness; preserve saved graph inputs.

Host regression checks reject missing/extra/duplicate/reordered members, wrong
units/types/IDs, non-finite values, inconsistent availability, wrong identity,
stale revision, altered affectors/variation/effects and falsified coverage. Native
checks exercise actual controls and immutable decoding, offline operation,
recreation and fresh-process restart. Full final verification retains all existing
desktop/build/native gates, A10 performance bounds and screenshot review. A host
inventory or prototype launch cannot establish inspector completion.
