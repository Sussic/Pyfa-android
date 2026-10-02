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

C01.1 is active; C01.2 and C01.3 follow sequentially. These children retain the
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
all prior gates. Tests and evidence are pending, not passing claims.

Known game-data attribute defaults are genuine EOS values, including zero bays
on hulls without that capacity. Do not fabricate missing-capacity fixture inputs.
True null values remain explicit unavailable scalars; focused protocol checks
verify their representation. Fourteen independent cases include a real overload
for every resource pair. Ten accepted saved-fit cases require native restart;
four provisional fighter/over-hardpoint cases use an isolated diagnostic engine
without expanding the durable input contract or claiming C05 editor support.

Progress: two fresh original-desktop exports agree. Seven focused host tests pass
all fourteen cases and ten saved fits reopened in a fresh process, with no desktop
imports/network access or game-database writes. Eight focused raw-validator tests
pass LF/CRLF equivalence and reject incorrect hashes, missing fixtures, changed
content even with updated hashes, other whitespace, wrong scalar kinds/values,
units, overload and labels. APK/native-test compilation and lint pass at their
recorded development revisions. Earlier host/compile failures remain retained.
Final candidate e0e01d9b passed 90/93 local gates, including every inherited native
check and the fourteen-case resource probe. Saved-resource preparation exposed a
test-only copy-selection error: DuplicateFit returns the whole library, so the
test selected an older fit. The equality assertion remains; select the sole new
ID and verify its name. Preserve the original failed attempt, APK and partial
store. Eight focused repair regressions pass. Recovery independently verifies
all 147 original inputs/statistics and removes only the two exact failed test
fits. Rebuild the test APK, require unchanged application/fixture bytes and exact
source equivalence outside this correction, then reuse the 90 valid results and
retry only prepare/restored/summary. Final screenshot review/delivery are pending.

C01.1 bounded retry update: copy-ID correction passed, then preparation rejected
an empty module slot because the fixture loop ordinal was used as a physical EOS
index. Select the newly occupied index and preserve every resource/state/charge
assertion. Both failures, APKs and partial stores are archived separately. Twelve
focused source/recovery tests pass. The second recovery verifies all 147 original
inputs, revisions, metadata and EOS statistics, checks the exact three synthetic
partial records and sole railgun recent-use promotion, then restores the original
baseline in a separate copy. Production code, fixtures, tolerances, timeouts and
performance requirements remain unchanged. Only corrected test build/package,
prepare, restored and summary remain; keep the 90 valid earlier gates.
