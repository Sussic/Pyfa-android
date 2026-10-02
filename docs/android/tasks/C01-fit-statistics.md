# C01 resources, capacitor and defenses

Selected 2026-10-02 after B09.2 PR #35, from delivered master b48f40d7.
Parent remains active until all F05.01–F05.27 acceptance rows are verified.
Retain Kotlin/Compose, Chaquopy, serialized EOS, offline persistence and all prior
acceptance gates. Calculation formulas remain in EOS; pinned desktop views define
units, formatting, detail precision and the meaning of available capacity.

## Bounded children

| Child | Scope | Acceptance |
| --- | --- | --- |
| C01.1 | F05.01–F05.11: fitting resources | Eleven used/capacity pairs, overload state and accessible precision for hardpoints, active drones, fighter tubes, calibration, CPU, powergrid, drone/fighter/cargo bays and bandwidth; pinned desktop raw and display comparisons, host rejection/read-only checks, native controls/recreation/restart and screenshot review. |
| C01.2 | F05.12–F05.15: capacitor | Capacity/effective capacity, correctly distinguished stable percentage/range versus depletion seconds, recharge/use/signed delta/effective excess gain and neutralizer resistance; independent battery/projected-neut and stable/unstable cases, native details and restart. |
| C01.3 | F05.16–F05.27: defenses and tank | Every damage resistance and multiplier, raw/effective HP and selected pattern contributions, raw/effective reinforced/sustained passive and active tank, applicable projected repair and spool details; independent assumption changes, typed persistence/history extension where needed, native controls/restart and screenshots. |

C01.1 is delivered in PR #36; C01.2 is delivered in PR #37, then C01.3 follows. These children retain the
parent's full acceptance rather than dropping fields. C01.3 may be subdivided
before implementation if the native outcome needs another bounded review.
Named damage-pattern management remains D05; audited C01 assumption inputs must
still be usable and verified. Drone/fighter editors remain C04/C05; populated
resource calculations must nevertheless have real EOS/native coverage now.

## C01.1 selected outcome

Expose a dedicated Resources screen for the current fit, with all eleven pairs
visible without changing addition tabs. Show used and capacity with desktop
compact formatting and units; expose desktop detail precision and raw values.
Over-capacity must be visible without relying only on color. Preserve explicit
unavailable capacities instead of adopting the desktop UI's zero fallback.
Changing equipment, cargo, fit selection or Undo/Redo must refresh the correct
fit/revision. Read-only details must not change saved inputs, history or recent use.

Reuse the existing serialized query pattern. Keep the earlier 39 calculation
fields and all independent fixtures valid; do not replace their assertions with
new resource expectations. Reuse the pinned presentation-only number formatter
in an isolated adapter if needed, with exact source equivalence checks, rather
than calculating fitting formulas in Kotlin.

Required verification: independent unmodified desktop raw/compact/detail values
across empty/fitted/over-capacity/drone/cargo/fighter cases; exact
counts/types/units and justified existing numeric tolerances; meaningful host
read-only, mutation/reversal and restart checks; APK/lint/package inspection;
real offline native UI/engine cases and screenshot review; full local plan with
all prior gates. Required verification is completed in the linked receipt below.

Known game-data attribute defaults are genuine EOS values, including zero bays
on hulls without that capacity. Do not fabricate missing-capacity fixture inputs.
True null values remain explicit unavailable scalars; focused protocol checks
verify their representation. Fourteen independent cases include a real overload
for every resource pair. Ten accepted saved-fit cases require native restart;
four provisional fighter/over-hardpoint cases use an isolated diagnostic engine
without expanding the durable input contract or claiming C05 editor support.

C01.1 delivery evidence: [receipt](../evidence/c01-1-native.json) records reviewed
code `e310303f`, actual gate commits, retained APK hashes and three native failures
plus the missing-witness staging failure. All 93 local gates pass. All 63 required
native executions, 154 required screenshots and the optional failed-run diagnostic
are reviewed. Ten resource fits plus a copy and the 147 inherited fits persist
through restart. Four provisional fighter/over-hardpoint cases remain isolated
real-EOS diagnostics; no C05 editor is claimed.

Two fresh original wx resource-view exports cover fourteen cases and overloads for
every pair. A separate two-process original desktop editing witness preserves the
vacant slots in Offline guns, including their zero scalar kinds. Seven original
host tests, eleven fixture/type validator tests, eighteen exact source/asset/recovery
tests and the actual-report corruption checks pass. Original resource fixture bytes
remain unchanged; reported hashes match verified retained APK bytes, and references
match after CRLF-to-LF normalization only. Every functional, type, tolerance,
restart, performance and overload assertion remains intact.

Three bounded recoveries independently verified all original 147 fit inputs,
revisions, metadata and EOS statistics before removing only known partial synthetic
test records. Full original failure logs/stores/APKs remain retained. The first
optional shared failure PNG/logcat were overwritten by the second failure and are
explicitly recorded as unavailable, never passing evidence. Later diagnostics are
archived by hash; required passing screenshots are intact. PR #36 merged as `7e457c97` from reviewed head `c5b187c0` with matching trees and
its successful exact-head `local/full-verification`. C01.2 is the next outcome.

## C01.2 selected outcome

Selected 2026-10-02 from delivered master `2cb602f3` on
`codex/c01-2-capacitor-details`. Expose read-only capacitor details for the current
fit/revision: capacity and applicable effective capacity in GJ, recharge/use and
signed delta in GJ/s, applicable effective excess gain, neutralizer resistance
in percent, and a typed stable percentage versus depletion time in seconds.
Preserve original desktop compact/detail presentation and raw precision. EOS at
the pinned revision returns a scalar stable state (the mean of simulation bounds);
verify this source contract rather than claiming an unproduced range as tested.
Any range representation must retain percent units and both bounds.

Acceptance: independent original wx/EOS empty, active/online/offline, battery and
projected-neutralizer cases; read-only, refresh, Undo/Redo, recreation and process
restart; strict protocol and incorrect-report rejection; APK/lint/package checks,
all inherited local gates and screenshots. No additional mutation, fitting formula
in Kotlin, reload setting, character-profile editor or projection editor is added.

C01.2 verification: [receipt](../evidence/c01-2-native.json) records all 97 required
local gates, 65 required native executions, 174 restored fits, 159 required
screenshots plus one reviewed failure diagnostic, twelve independent original
wx/EOS cases, ten raw fixture tests and 22 rejected actual-report corruptions.
Product code `855c87c3` is unchanged by exact test-runner repair `7775b40a`.
Ten source/package guards prove the sole missing persistent phase flag; all158
prior fits and the app APK remain unchanged. Only affected test build/package,
capacitor prepare/restored and summary reran, retaining94 valid earlier gates.
The scalar EOS stability contract and typed range protocol remain distinguished.
Failures remain recorded; the optional B05.4 shared failure logcat overwritten by
capacitor diagnostics is explicitly unavailable. Required passing evidence remains
intact. No assertion, tolerance, timeout or A10 requirement was weakened.

PR #37 merged as 1c3beef9 from ca052755; merge/head trees match and its
exact-head local/full-verification passed. C01.2 is closed; C01.3 is next.

## C01.3 bounded outcomes

C01.3.1 selected2026-10-02 from `adafcadc`, branch
codex/c01-3-1-defense-details: F05.16–F05.22 defenses/HP and usable incoming
damage contributions. Display all twelve resistances and three multipliers;
raw/effective HP per layer and total, toggle with retained units/precision;
edit each EM/thermal/kinetic/explosive contribution independently, reject invalid
or all-zero patterns, persist accepted values and include their history disposition.
Use actual EOS and unmodified original resistance refresh/pattern command evidence.
Verify single/mixed patterns, active/offline resistance and HP modules, read-only
queries, rejection/no-op, Undo/Redo, copy, recreation and separate-process restart.
Final delivery requires APK/lint/package, every inherited gate, native screen/raw
assertions, screenshot review and report-corruption checks. Named pattern libraries
remain D05. C01.3.2 follows delivery and retains F05.23–F05.27 tank/spool acceptance.
The parent remains active until both children are verified and delivered.
