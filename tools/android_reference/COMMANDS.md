# A05 command-burst reference

This establishes a host command-burst case against unmodified desktop EOS at
`8b04f3b271e614b3e103853b44a7851a63d79d0e`. It does not establish Android support or
full command-feature parity. The oracle uses the A01 dependencies, real config/wx
and the same verified game data. It rejects adapter imports and checks that every
loaded EOS/utils/config file originates in the clean pinned reference checkout.

## Synthetic case

[Inputs](command.json) specify an all-V Vulture with a Shield Command Burst II and
a fitted Vexor recipient. The source also carries a railgun to exercise rejection
of a mixed gun/burst charge or state selection. Both fits use uniform damage,
reload factoring off, high security and no projections, environments or boosters.
Implants begin empty; the case adds and removes a Shield Command Mindlink.

[Expected results](fixtures/command.json) record **39 raw statistics on both fits
in 19 stages** (1,482 values with units). This reuses A04's sample vocabulary.
The comparator checks the complete structure with the unchanged relative `1e-10`
and absolute `1e-9` float tolerances, exact units, integer counts and booleans.
Selected target results, rounded only in this table:

| Stage | Shield HP | EM shield resonance (fraction) |
| --- | ---: | ---: |
| Initial | 2,750 | 0.875 |
| Shield Extension applied | 3,224.375 | 0.875 |
| Shield Command Specialist IV | 3,192.750 | 0.875 |
| Specialist restored to V | 3,224.375 | 0.875 |
| Command Ships IV | 3,212 | 0.875 |
| Command Ships restored to V | 3,224.375 | 0.875 |
| Mindlink added | 3,342.968750 | 0.875 |
| Mindlink inactive | 3,224.375 | 0.875 |
| Mindlink active | 3,342.968750 | 0.875 |
| Burst module online (not active) | 2,750 | 0.875 |
| Burst module active | 3,342.968750 | 0.875 |
| Command link inactive | 2,750 | 0.875 |
| Command link active | 3,342.968750 | 0.875 |
| Shield Harmonizing charge | 2,750 | 0.686328125 |
| Shield Extension restored | 3,342.968750 | 0.875 |
| Mindlink removed | 3,224.375 | 0.875 |
| Command removed | 2,750 | 0.875 |
| Command reapplied | 3,224.375 | 0.875 |
| Command removed again | 2,750 | 0.875 |

The charge change must replace the HP bonus with resistance bonuses, not leave
both effects behind. Lowering either skill must reduce received strength; adding
the mindlink must increase it. Disabling the module or link restores every target
statistic. Final removal restores both fits' original statistics. Each completed
sample also checks that EOS has consumed its pending command-bonus dictionary.

## Reproduce

Follow [A01](README.md) for the clean reference checkout, desktop Python 3.11
environment and verified database. Reuse that database; the verifier checks its
logical hash and integrity and confirms its file bytes do not change. Output
directories must be new and outside both checkouts and the input database.

With the desktop environment:

```sh
../pyfa-reference-venv/bin/python -I tools/android_reference/command.py --source ../pyfa-reference --database /tmp/pyfa-desktop-reference/eve.db --output /tmp/pyfa-command-reference --check tools/android_reference/fixtures/command.json
```

The Linux sandbox needs A01's recorded `LD_LIBRARY_PATH` for the genuine wx host
libraries. On Windows use the venv's `Scripts/python.exe` and Windows temporary
paths; the CLI is otherwise the same. Two isolated `-I` workers must produce the
same fixture. Outputs include `fixture.json`, `repeat.json`, logs and evidence.
Never generate expected numbers through `android_bridge`.

With the separate [headless environment](../android_headless/README.md):

```sh
../pyfa-headless-venv/bin/python -I tools/android_headless/check.py --scenario command --database /tmp/pyfa-desktop-reference/eve.db --output /tmp/pyfa-command-check
```

This checks item IDs, input definitions, settings, data identity and every expected
value, runs nine real EOS behavioral tests and repeats in a fresh process. The
headless environment contains only Logbook, SQLAlchemy and Greenlet; its verifier
rejects desktop imports and socket operations, including swallowed attempts.

Two-recipient tests use identical target specifications so the independent oracle
applies to each. They exercise reversed read order, skills, implants, charge and
module changes, independent link states and removal of just one recipient. Other
tests cover duplicate/missing links, wrong-thread/foreign handles, occupied implant
slots, invalid skills and mixed charge/state rejection without partial edits.

## Evidence and remaining scope

[Retained Linux evidence](evidence/command-linux.json) includes the command oracle
and all three headless scenarios. Windows CI is pending on the implementation PR.
The [existing Windows workflow](../../.github/workflows/desktop-reference.yml)
rebuilds A01 data once, runs all independent references and migration regression,
then runs all three headless scenarios. It adds no jobs, uploads or caches.

No upstream code patch or equation change is needed. Command links follow the
desktop association/flush/refresh pattern; EOS recalculation invalidates boosted
recipients. The adapter refreshes invalidated fits before reading. Adding an
implant checks its slot first, so this case never enters the GUI-coupled
`makeRoom` replacement helper. Full replacement remains C07.

Coverage is one source hull, one burst module, two shield charges, two skills and
one mindlink. Every other burst, range/duration display, shared character/implant
profiles, multiple-source overlap/selection, self/reciprocal command graphs,
commands combined with projections, persistence and UI actions still need their
D03/C06/C07/C09 cases. Q07 remains open for those interactions. A09 must execute
the reference through Android. Next task: A06 Android skeleton and native CI.
