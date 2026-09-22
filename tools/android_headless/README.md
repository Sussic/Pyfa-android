# Headless adapter verification

This verifies [the A03–A05 Python adapter](../../android_bridge/README.md). It is a
host check, not native Android evidence. The A01 fixture, input file, exporter
and numeric tolerances remain unchanged.

## Reproduce locally

Use the A01 [reference instructions](../android_reference/README.md) to build the
game database from the separate clean checkout pinned at
`8b04f3b271e614b3e103853b44a7851a63d79d0e`. Reuse a verified A01 database if it
already exists: the headless verifier checks its integrity/logical content hash
and proves its file bytes do not change. Never substitute a personal user DB.

Create a separate Python 3.11 environment **without** system-site packages:

```sh
python3.11 -m venv ../pyfa-headless-venv
../pyfa-headless-venv/bin/python -m pip install --only-binary=:all: -r tools/android_headless/requirements.txt
../pyfa-headless-venv/bin/python -I tools/android_headless/check.py --database /tmp/pyfa-a01-run-5/eve.db --output /tmp/pyfa-a03-check-1
```

Replace the database path with your A01 output. Output must be a new disposable
directory outside the development checkout and cannot contain the input DB.
On Windows PowerShell the same steps are:

```powershell
py -3.11 -m venv ../pyfa-headless-venv
../pyfa-headless-venv/Scripts/python.exe -m pip install --only-binary=:all: -r tools/android_headless/requirements.txt
../pyfa-headless-venv/Scripts/python.exe -I tools/android_headless/check.py --database "$env:TEMP/pyfa-desktop-reference/eve.db" --output "$env:TEMP/pyfa-headless-check"
```

To verify the preserved desktop migration behavior, use the **A01 desktop
environment**, which has real wx installed:

```sh
../pyfa-reference-venv/bin/python -I tools/android_headless/check_desktop_migration.py --database /tmp/pyfa-a01-run-5/eve.db
```

The local Linux sandbox also needed A01's recorded `LD_LIBRARY_PATH` containing
its three extracted host libraries for this desktop regression. The headless
environment needs none of those libraries. Windows CI uses native desktop wheels.

## What is asserted

- Match all 38 raw values/units in all three A01 states, resolved item IDs,
  dataset metadata and EOS settings. Expected values come only from the pinned
  desktop fixture. Only the unchanged comparator/digest utilities are shared;
  the adapter does not call the reference's bootstrap, fit builder or snapshot.
- Ten real EOS tests cover numerical parity, whole-selection charge changes,
  rejection without partial mutation, unsupported input fields, independent
  fits, read-only game data, process/thread ownership and current-schema checks.
- Repeat the fit/edit/restoration scenario in a second fresh `-I` process to
  catch initialization/cache leaks. Only the first process runs the full test set.
- Refuse environments containing desktop packages. A fail-closed import finder
  records/rejects `wx`, `gui`, `service` and root `config`; a Python audit hook
  records/rejects socket connection, resolution and binding attempts. Even an
  attempted operation swallowed by library code causes the final check to fail.
  This establishes the tested host path; it is not an Android offline test or
  a general operating-system network sandbox.
- Confirm all loaded engine/adapter modules come from the development checkout,
  and that the database's physical bytes are unchanged after both processes.

Outputs are `tests.json`, `repeat.json`, bounded-process logs, a normalized source
manifest and `evidence.json`. Evidence records dependency/runtime versions, source
and fixture hashes, current commit/dirty state, checks, and explicitly false
Android-test status. Worker logs remain local/temporary; concise evidence is
retained in this directory's `evidence` folder and CI logs.

## CI

The existing [desktop-reference workflow](../../.github/workflows/desktop-reference.yml)
now watches the adapter, EOS, shared utilities and headless checks. One Windows
job rebuilds the independent reference once, tests the real desktop migration,
then creates a separate three-package venv for the headless comparison. It keeps
the existing eight oracle comparator/digest tests. There are no additional
uploads, caches, scheduled runs, spending changes or emulator runs.

The [A04 projection commands and evidence](../android_reference/PROJECTIONS.md)
extend that same job with an independent desktop projection export and
`check.py --scenario projection` in the headless environment. Eight additional
real EOS tests cover the 11 reference states, two recipients, independent link
edits, invalid inputs, mixed source-charge rejection, ownership and repeated
removal.

The [A05 command reference](../android_reference/COMMANDS.md) adds
`check.py --scenario command`. Nine additional tests cover 19 reference stages,
two recipients, skill/implant/charge/module edits, independent command toggles,
invalid input rejection and repeated removal. All three scenarios record
normalized code, input and fixture hashes and use the same import/network guards.
Full command/projection coverage, persistent saves, the complete statistics
interface and Android packaging/ABIs remain unverified.

## Retained A03 evidence

[Linux](evidence/linux.json) and [Windows](evidence/windows.json) both passed ten
behavioral tests and the fresh-process scenario. The Windows run also passed the
unchanged eight A01 comparator/digest checks, full independent reference rebuild
and real desktop migration regression. [Passing CI run](https://github.com/Sussic/Pyfa-android/actions/runs/34695947959).

The normalized code manifest is
`7efc65d10c3d3d9a778db48f1e76020b2ca3678d22efde3fba002377a4339d33`
on both platforms; logical game-data hash is
`5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607`.
Linux was measured before commit (tracked changes recorded); Windows used GitHub's
PR merge checkout, with the actual PR head and delivered merge recorded separately.
Only evidence/documentation changed after that passing run.

A10 adds one forced-GC source-refresh regression to each projection and command
suite, bringing the total to **29 behavioral tests** (10 ammunition, nine projection,
ten command). Both regressions fail before the adapter correction and pass after:
add/remove two recipients while a refreshed source module is actually collected,
then compare all source/recipient/control statistics and relationship directions.
[The native/Windows receipt](../../docs/android/evidence/a10-native.json) records
these checks and the unchanged independent fixtures. EOS formulas are unchanged.

## B01 typed contract and failure recovery

The application-facing contract is defined in
[`android_bridge/contract.py`](../../android_bridge/contract.py) and
[the B01 task](../../docs/android/tasks/B01-typed-bridge.md). Run its focused host
suite in a separate process using the same pinned Python 3.11 environment:

```sh
python -I tools/android_headless/check_bridge.py \
  --database /path/to/reference/eve.db \
  --output /path/outside/checkout/new-bridge-check
```

The suite sends JSON requests to real EOS, compares all A01/A04/A05 stages with
the independent fixtures, checks transitive/inactive-link revisions, and injects
failures after real creation, link, skill, implant, serialization and SQL commit
work. Recovery must preserve actual dependent skill nulls, logical IDs, revisions,
session identity and saved-data cache identity; failed recovery is terminal.
Desktop imports and network operations are blocked, and the database identity is
checked before/after execution. Host evidence does not establish Android behavior;
`BridgeContractTest` provides the separate native contract gate.

## B02 durable graphs and process recovery

Run the persistence gate against the same pinned game database:

```sh
python -I tools/android_headless/check_persistence.py \
  --database /path/to/reference/eve.db \
  --output /path/outside/checkout/new-persistence-check
```

Fourteen focused tests use separate operating-system processes, real EOS and a
temporary SQLite store. They check nine-fit restoration, exact relationship and
revision identity, dependent skill nulls, interrupted initial installation,
process death before/after commit, errors after confirmed saves, stale writers,
and preservation of invalid or incompatible files. The game database remains
read-only; desktop imports and network operations stay blocked. Existing B01 and
29 headless tests remain required. Native restart evidence comes from three
separate `PersistenceTest` invocations with app data preserved between them.
See [B02's storage contract and limits](../../docs/android/tasks/B02-local-persistence.md).

## B03.1 fit lifecycle regressions

Run `python -I tools/android_headless/check_library.py --database /absolute/eve.db --output /outside/checkout/library-check` with the pinned Python 3.11 environment. Eight tests cover Unicode/stale requests, copy input/relationship independence, source/recipient deletion, true subprocess reopen including an empty store, rollback of each lifecycle operation and confirmation after a lost commit acknowledgement. Uses the existing independent fixtures and the B02 guarded reopen worker. Native UI/restart evidence is a separate required gate.

B03.2 extends this same gate to 13 tests. Five additional cases compare all hull
metadata with the pinned desktop catalogue, preserve modification order through
reads/failures/restart, distinguish recipient recalculation from changed inputs,
open legacy saves without inventing historical order and reject malformed metadata.
The full host total is now 78. Reproduce the independent catalogue with the
reference environment: `python -I tools/android_reference/catalog.py --source
/clean/pinned/checkout --database /absolute/eve.db --output /new/external/catalog
--check tools/android_reference/fixtures/catalog.json`. Its checkout also needs
`service/`; no mobile adapter is imported by that exporter.

## B04.1 equipment discovery

Run `python -I tools/android_headless/check_market.py --database /absolute/eve.db
--output /new/external/equipment-check` with the installed headless environment.
Six additional guarded tests compare all 718 groups, 6,822 items, memberships,
metadata and 22 searches to the independent desktop exporter. Cache isolation,
repeat searches, invalid input, unchanged fitting data and worker ownership are
checked without desktop imports or network access. The current required host
total is 84; the separate native equipment workflow raises native executions to
18. Earlier counts above are historical.
