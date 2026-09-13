# Headless adapter verification

This verifies [the A03/A04 Python adapter](../../android_bridge/README.md). It is a
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
removal. Both scenarios record normalized code, input and fixture hashes.
Command sources, full projection coverage, persistent saves, the complete
statistics interface and Android packaging/ABIs remain unverified.

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
