# Original-source map and qualified finite result

All original methods below are read from the retained reconstructed-source tree.
The exporter records whole-file SHA-256 values and executes extracted AST bodies
or imports EOS directly from that tree. No candidate calculations supply expected
values. Existing supplemental game data remains explicitly unqualified as a new
clean pin; this result is host/reference evidence, not Android proof.

## Exact call path

- `graphs/data/fitRemoteReps/graph.py::FitRemoteRepsGraph` supplies the actual
  distance-km normalizer (`*1000`) and denormalizer (`/1000`) expressions.
- `graphs/data/base/getter.py::{PointGetter,SmoothPointGetter}` supplies original
  construction, linear iteration, adaptive recursion, range and point getters.
  `graphs/data/fitRemoteReps/getter.py::XDistanceMixin` selects 50 base intervals
  and depth 2. Original output/evaluation orders, duplicates and rounding survive.
- `Distance2RpsGetter` composes `XDistanceMixin` and `YRpsMixin`. Original
  `_getCommonData` calls original `TimeCache.prepareRpsData`; `maxTime=None`
  returns before generation. Original `_getRepsPerKey` iterates active modules
  then drones and applies graph ancillary reload only to the two ancillary effects.
- `graphs/data/fitRemoteReps/calc.py::getApplicationPerKey` invokes original
  `graphs/calc.py::{checkLockRange,checkDroneControlRange}` with explicit request
  options; its EOS range factor and float rounding run unchanged.
- Original `applyReps` sums shield, armor and hull, excluding capacitor transfers.
  Per-key repair dictionaries retain the nonzero capacitor witness separately.
- Original `gui/builtinViewColumns/attributeDisplayGraph.py::{ShieldRRColumn,
  ArmorRRColumn,HullRRColumn}._getValue` calls original `Fit.getRemoteReps` with
  default spool options and no graph ancillary override. No GUI formatting is
  claimed. The returned HP/s values and units are exported separately.
- Original `Module.getCycleParameters/getRemoteReps`, `Drone.getRemoteReps`,
  `CycleInfo/CycleSequence.averageTime` and spool resolution supply all arithmetic.
  Both `iterCycles` methods, TimeCache generation/data paths and all capacitor/
  tank/simulation entries are fail-fast forbidden before fixture construction.
- Original `service.fit.Fit.recalc` supplies LOCAL preparation. Its global reload
  option explicitly sets the effective fit flag; the harness selects the declared
  fixture flag first and asserts the effective flag before every graph observation.
  This is isolated reference configuration, not a product setting change.

## Proven legal source inputs

All-V Vexor is type 626; all-V Rodiva is 49712. Original legality checks cover
module restrictions, loaded charge validity/publication, CPU/PG/slots/hardpoints,
drone bay/bandwidth/active count and nonnegative counts. Restriction overrides are
false. The base Vexor fitting container has 16 rows including empty slots.

- Inherited mixed outgoing modules, in source order: Medium Remote Capacitor
  Transmitter II (12221), Shield Booster II (3598), Armor Repairer II (26913), Hull
  Repairer II (4296). Empty and capacitor-only cases are distinct zero witnesses.
- Maintenance drones in source order: Light Shield Maintenance Bot I (23719),
  Light Armor Maintenance Bot I (23711), Light Hull Maintenance Bot I (33706).
  Each starts at total 2 / active 1. Initial source rates are 3, 3 and 1.5 HP/s.
  Original shield quantity 2→3 raises active count 1→2, with exact undo/redo.
- Small Ancillary Remote Armor Repairer (41476) with Nanite Repair Paste (28668),
  and Small Ancillary Remote Shield Booster (41480) with Cap Booster 25 (263).
  Both loaded charges pass original `isValidCharge`. One of each respects their
  distinct maxGroupFitted constraints. Loaded/no-reload source rates are armor
  37 and shield 31.25 HP/s; reload-factored rates are armor 10.571428571428571 and
  shield 9.943181818181818 HP/s. Graph ancillary reload switches the aggregate
  independently between 68.25 and 20.51461038961039 HP/s at zero distance.
- Heavy Mutadaptive Remote Armor Repairer II (49773) on Rodiva: default/full source
  rate 346.66666666666663 HP/s; explicit zero 138.66666666666666; three cycles
  180.26666666666668. Reset returns exactly to the default. All are original getter
  outputs, not handwritten expected formulas.
- Remote Armor Repair Systems (16069) affects capacitor need only in original
  Effect1030. The linked profile edit changes its captured input while repair
  curves stay unchanged, proving that this graph does not substitute cap/tank.

## Final V2 finite result

Five original processes passed: ordinary 7 stages, drones 4, spool 6, ancillary 9,
linked 13. Total 39 stages, 87 recorded fit observations, 129 curves and 8,850
stored range points. Every observation is repeated in reverse fit-read order,
for 174 actual observations. Actual point calls including gate probes: 21,004;
application calls including per-key zero-distance witnesses: 21,262. Actual roots:
219 LOCAL and 58 PROJECTED. Highest real-curve count: 93; the separate original
adaptive ramp test reaches the 201-point source ceiling.

Measured active-iterator scans include all rows: 401,312 module-row and 6,288
drone-row visits, plus source-column cache misses scanning 2,784 module rows and
24 drone rows. Each fixture has at most 4 occupied local modules, 3 local drone
rows and 4 active remote rows. These finite measurements are not a new universal
ordinary-fit admission proof or a product restriction.

Maximum process duration was 4.861 seconds; peak RSS 186,060 KiB, under the existing
180-second/1-GiB limits. No forbidden calls or network attempts; the actual
TimeCache remained empty. Database pre/post hashes agree. Eight no-EOS tests pass
for singleton, subnormal-step underflow, duplicates, exact source evaluation order,
ceiling, original midpoint overflow and the actual null-time cache early return.

Evidence is in candidate-root `preflight-evidence/`: five `*-v2.json` receipts and
logs, `verify-v2.json`, `measurements-v2.json` and `pure-adaptive-source-v1.log`.
The complete current exporter hash is
`16d32a32802351b62241b2c8f099fcb795d7873d944ef12c6e18b3d259a50c2e`.

V1's first three suites passed; ancillary then failed a harness input-binding
assertion because inherited service settings overwrote factorReload=true with
false. No simulation/resource/source arithmetic failure occurred. Those logs and
receipts are unchanged. Exact V1/V2 exporter bytes are retained as text with
matching original hashes. V2 corrects only explicit source service settings and
records declared/effective flags. First-three V1/V2 raw inputs, curves and source
columns match exactly. This does not weaken source-column distinction witnesses.

Candidate runtime parity, stale/context/durable/publication/history checks, native
integration/compiler/device evidence and G05.2 time/total remain separate work.
