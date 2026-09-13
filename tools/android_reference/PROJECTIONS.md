# A04 projection reference

This is host evidence for a small linked-fit case, not completed Android projection
parity. The oracle uses unmodified EOS at
`8b04f3b271e614b3e103853b44a7851a63d79d0e`, real desktop config/wx, the A01 pinned
dependencies and the same verified game database. The adapter is never imported
by the oracle. The oracle checks the origin of all loaded EOS/utils/config files.

## Synthetic case and expected behavior

[Inputs](projection.json) define an all-V Celestis with a Remote Sensor Dampener II
and a fitted Vexor recipient. Both use uniform damage, no reload factoring, high
security and no implants, boosters, commands or environments. A railgun on the
source also makes a mixed gun/dampener charge selection a useful rejection test.

[Expected results](fixtures/projection.json) record 39 raw statistics with units
on **both fits**, for each of 11 stages. The 38 A01 fields are retained; scan
resolution in mm is added to observe the script change. Every stage matches the
entire structure, with the unchanged relative `1e-10` / absolute `1e-9` float
tolerances; integers, booleans and units match exactly. Selected target results:

| Stage | Projection distance | Target range (m, rounded here only) | Scan resolution (mm) |
| --- | --- | ---: | ---: |
| Initial | No link | 65,625 | 350 |
| Applied | 0 m | 31,110.351563 | 350 |
| Falloff | 100,000 m | 33,307.961324 | 350 |
| Distant | 300,000 m | 62,974.199720 | 350 |
| Disabled | 0 m, inactive | 65,625 | 350 |
| Reactivated | 0 m | 31,110.351563 | 350 |
| Scan-resolution script | 0 m | 65,625 | 165.921875 |
| Range script restored | 0 m | 31,110.351563 | 350 |
| Removed | No link | 65,625 | 350 |
| Reapplied | Unspecified (`None`) | 31,110.351563 | 350 |
| Removed again | No link | 65,625 | 350 |

This is Pyfa's range-weighted result: beyond optimal does not imply an immediate
hard cutoff. The reference checks that the distance stages differ and that all
values restore on disable/removal. Unspecified and zero range match in this case.

## Reproduce

First follow [A01](README.md) to obtain its clean pinned checkout, desktop venv and
verified database. Outputs below must be new directories outside both checkouts.
Use the desktop Python for the oracle:

```sh
../pyfa-reference-venv/bin/python -I tools/android_reference/projection.py --source ../pyfa-reference --database /tmp/pyfa-desktop-reference/eve.db --output /tmp/pyfa-projection-reference --check tools/android_reference/fixtures/projection.json
```

On the Linux sandbox, prefix this desktop command with A01's `LD_LIBRARY_PATH`
if needed for its recorded wx host libraries. On Windows use the venv's
`Scripts/python.exe` and an appropriate temporary output path. The same CLI is
used on both platforms. This reuses the A01 database, verifies its logical hash,
runs two independent `-I` workers and proves database bytes remain unchanged.
`fixture.json`, `repeat.json`, worker logs and `evidence.json` are written locally.
Expected values must never be regenerated from the headless implementation.

Then use the separate [three-dependency headless environment](../android_headless/README.md):

```sh
../pyfa-headless-venv/bin/python -I tools/android_headless/check.py --scenario projection --database /tmp/pyfa-desktop-reference/eve.db --output /tmp/pyfa-projection-check
```

That checks the committed input, item IDs, settings, dataset and every expected
value, then runs eight behavioral tests. It repeats the scenario in another fresh
process and rejects desktop imports or socket operations, even swallowed attempts.
Multiple-recipient tests use identical recipients so the same independent oracle
applies; they also test reverse read order and editing/removing just one link.

## Evidence and boundaries

[Retained Linux evidence](evidence/projection-linux.json) records the oracle,
headless projection and existing ammunition runs plus desktop migration and eight
reference utility checks. Windows CI is pending on the implementation PR.
The [existing Windows workflow](../../.github/workflows/desktop-reference.yml)
performs the same checks with one shared A01 database rebuild, no extra jobs or
uploads. Reference imports, fixture/data hashes, runtime versions and normalized
headless source/input hashes identify what was tested.

The adapter uses the same mapped association and flush/refresh pattern as
`gui/fitCommands/calc/projectedFit/add.py`, plus EOS's own dependent-fit
invalidation. Removal clears both directions. `snapshot` refreshes invalidated
fits before reading. No formula or upstream projection implementation was changed.

This covers one linked dampener source at count one. All projection families,
counts/stacking, cycles, remote repair/capacitor interactions, skills/implants,
source deletion, command interactions, persistence and UI actions still need their
D01/D02 cases. Q07 remains open for those interactions. A08 must run this fixture
through an actual Android runtime. Next host task: A05 command bursts.
