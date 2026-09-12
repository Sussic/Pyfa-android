# Pinned desktop reference (A01)

This command generates game data and runs **unmodified desktop Pyfa EOS** from
commit `8b04f3b271e614b3e103853b44a7851a63d79d0e` in a separate checkout.
It is a synthetic numerical reference, not an Android adapter or a desktop UI test.
The Vexor fixture captures 38 statistics in three states: Antimatter ammunition,
Iron ammunition on both guns, and restored Antimatter. Both exports run in fresh
isolated Python processes; restoration and unchanged drone/resource stats are
checked. The fixture is deliberately small and does not establish full parity.

## Prepare a reference checkout

Run from the development repository. Keep the reference unmodified; the exporter
rejects a different HEAD, tracked changes and untracked files. Sparse checkout
avoids fetching artwork and unrelated desktop UI files.

```sh
git clone --filter=blob:none --depth=1 --no-checkout https://github.com/Sussic/Pyfa-android.git ../pyfa-reference
git -C ../pyfa-reference fetch --depth=1 origin 8b04f3b271e614b3e103853b44a7851a63d79d0e
git -C ../pyfa-reference sparse-checkout set eos utils staticdata
git -C ../pyfa-reference checkout --detach 8b04f3b271e614b3e103853b44a7851a63d79d0e
```

Use Python 3.11 in a separate virtual environment. Install the pinned requirements
with binary wheels so a missing wx wheel fails clearly instead of starting a long
source build. Windows wheels are available from PyPI. Linux wheels use the
[official wxPython extras distribution](https://wxpython.org/pages/downloads/index.html).

Windows PowerShell:

```powershell
py -3.11 -m venv ../pyfa-reference-venv
& ../pyfa-reference-venv/Scripts/python.exe -m pip install --only-binary=:all: -r tools/android_reference/requirements.txt
$referenceRun = Join-Path $env:TEMP ('pyfa-reference-' + [guid]::NewGuid().ToString('N'))
& ../pyfa-reference-venv/Scripts/python.exe -I tools/android_reference/reference.py --source ../pyfa-reference --output $referenceRun --check tools/android_reference/fixtures/vexor.json
```

Ubuntu 22.04 with Python 3.11:

```sh
sudo apt-get update
sudo apt-get install -y libgtk-3-0 libnotify4 libxtst6 libtiff5 libgl1 libsm6 libxxf86vm1 libsdl2-2.0-0
python3.11 -m venv ../pyfa-reference-venv
../pyfa-reference-venv/bin/python -m pip install --only-binary=:all: --find-links https://extras.wxpython.org/wxPython4/extras/linux/gtk3/ubuntu-22.04/ -r tools/android_reference/requirements.txt
../pyfa-reference-venv/bin/python -I tools/android_reference/reference.py --source ../pyfa-reference --output /tmp/pyfa-reference-a01 --check tools/android_reference/fixtures/vexor.json
```

The output directory must not exist and must be outside both checkouts. Choose a
new name for each deliberate run. This prevents silently reusing a stale database
or overwriting earlier evidence. Workers have a ten-minute timeout each.

## What the command verifies and writes

- Builds `eve.db` from the pinned `staticdata/` using the original `db_update.py`.
  Only the database location is configured; source files and formulas are unchanged.
- Uses an in-memory saved-fit database. No personal character, token or saved fit
  is needed or read. English EOS calculation needs no compiled translations,
  GUI launch or X display; the real wx library is nevertheless required by imports.
- Runs SQLite integrity checking before calculating, then exports the same case
  twice in fresh Python processes and compares all fields.
- Checks both gun DPS and optimal-range changes, restoration of every captured
  stat, and unchanged drone DPS, control range, CPU and powergrid after ammo edits.
- Writes `fixture.json`, `repeat.json`, `evidence.json`, the generated database and
  short worker logs. On failure, inspect the corresponding `*.log`; a missing
  PASS/evidence result is not a successful run.
- With `--check`, compares against the committed fixture without updating it.
  To intentionally regenerate, omit `--check`, then review the output before copying
  it into `fixtures/`. Never regenerate expected values from the mobile adapter.

The source-data digest is SHA-256 of a canonical JSON mapping from each tracked
static-data path to its SHA-256, normalizing CRLF to LF. Database provenance records
both the physical SQLite file digest and a logical digest over table schema,
columns and sorted rows. Only the logical digest is compared across rebuilds;
SQLite physical layout can change without any change in game data.

All float results use raw engine values, with explicit units, relative tolerance
`1e-10` and absolute tolerance `1e-9`. These allow platform floating-point noise,
not UI rounding. IDs, counts, booleans, units, metadata, input definitions and
structure compare exactly. Future fields with different numerical behavior must
justify their tolerances rather than globally loosen this comparison.

## Validation and CI

```sh
python -m unittest discover -s tools/android_reference/tests -v
```

Eight focused tests guard against false comparison passes and check logical
database provenance. The `Desktop reference` workflow runs these plus the actual
database rebuild and fixture comparison on Windows for relevant PRs. It uses no
artifact uploads, caches, schedules, credentials or Android emulator. This is the
desktop reference gate; Android build/test setup remains A06.

## Recorded Linux execution

See [the evidence record](evidence/linux.json) for the Python/SQLite/dependency
versions, data hashes, script hash and matched fixture hash from the successful
run. [Native dependency provenance](evidence/linux-native-libraries.json) records
three official Ubuntu packages extracted locally for this sandbox's missing
wx shared libraries. They are host dependencies, not proposed Android libraries.

The tested host was Ubuntu 24.04 using Python 3.11.16 and the official Ubuntu 22.04
wxPython 4.2.1 wheel. System package installation was unavailable, so libnotify4,
libxtst6 and libtiff5 were extracted with `dpkg-deb -x` into a disposable directory.
`LD_LIBRARY_PATH` pointed to that directory's `usr/lib/x86_64-linux-gnu` when
launching Python. The package URLs and SHA-256 hashes are in the provenance record;
none of the binaries are committed. Standard Ubuntu 22.04 or the Windows workflow
avoids this sandbox-specific dependency setup.

One initial database build in the workspace failed at VACUUM with a malformed
SQLite image. The same source/runtime built successfully under `/tmp`; the exact
cause of the initial failure is not established. Reproduction commands therefore
use temporary storage and retain the integrity check. Do not reuse the failed file
or describe this as a fixed upstream Pyfa bug.
