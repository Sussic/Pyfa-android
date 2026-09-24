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
avoids fetching artwork and unrelated desktop UI files. Explicit cone mode keeps
required root files such as `db_update.py` and `config.py` on older Git versions.

```sh
git clone --filter=blob:none --depth=1 --no-checkout https://github.com/Sussic/Pyfa-android.git ../pyfa-reference
git -C ../pyfa-reference fetch --depth=1 origin 8b04f3b271e614b3e103853b44a7851a63d79d0e
git -C ../pyfa-reference sparse-checkout set --cone eos utils staticdata
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

## Windows verification

[CI run 34691992984](https://github.com/Sussic/Pyfa-android/actions/runs/34691992984)
passed all eight tests and the complete fixture comparison on Windows, Python
3.11.9 and SQLite 3.45.1. [Windows evidence](evidence/windows.json) records the
runtime, data identity and tested commit. It matches Linux's logical data digest
and all 38 statistics in the three states.

Exporter/fixture byte hashes identify files from each run. Windows CRLF line
endings can produce different byte hashes; the verification compares parsed JSON
and normalized source data. No numeric tolerance or expected value was changed to
obtain the Windows pass. The first Windows check found open SQLite handles during
cleanup; explicit connection closing fixed the actual resource lifetime.

## B04.1 independent equipment reference

Use the reference environment and clean pinned checkout (including `service/`):
`python -I tools/android_reference/equipment.py --source /clean/pinned/checkout
--database /absolute/eve.db --output /new/external/equipment-reference
--check tools/android_reference/fixtures/equipment.json`.

The exporter reads the original Market service and executes its actual search
worker with wx event dispatch. It sets `gamedataCache=False` before EOS imports,
matching desktop `config.init`; no source or search method is patched. It keeps
settings in memory, validates source/dependencies/data, enumerates all 718 visible
market groups and 6,822 items, records group membership/meta/parent/jump mappings
and executes the 22 input queries in `equipment-queries.json`. A second process
must produce the same result; the input database must remain unchanged. The
Android adapter is never imported. The fixture is packaged only in the test APK.

## B04.2.1 independent empty hull reference

Run `python -I tools/android_reference/empty_hulls.py --source /clean/pinned/checkout
--database /absolute/eve.db --output /new/external/empty-hulls-reference
--check tools/android_reference/fixtures/empty-hulls.json` with the same installed
reference environment. Original Market hull enumeration and EOS Ship/Citadel/Fit
constructors produce all 437 empty fits under explicit all-V, uniform-damage,
high-security/no-addition inputs. No desktop method is patched and no mobile
adapter imported. All 39 raw fields/units/scalar types compare across two fresh
processes and against the fixture; absent gun ranges are JSON null. The receipt
binds the fixture digest to verified source/data identity. Existing fitted
references and tolerances remain unchanged.

## B04.2.2 independent module command reference

Run `python -I tools/android_reference/module_edits.py --source /clean/pinned/checkout
--database /absolute/eve.db --output /new/external/module-edits-reference
--check tools/android_reference/fixtures/module-edits.json` in the installed
reference environment. Include `gui` in the pinned sparse checkout. The oracle
AST-loads original, unchanged command/helper/service definitions with real
wx/Market/EOS to avoid unrelated login/window dependencies. It records original
file hashes and does not import the adapter or patch calculation methods.
GUI window dispatch is outside this oracle; restriction-toggle orchestration is
audited separately and invokes original removal commands.

Two fresh processes must match 11 cases/91 states, all 4,242 default module states
and 25 recent-use attempts under explicit inputs/settings. Cases include racks,
holes, rejection/override/re-enable, state limits, resource/skill warnings,
structure services, two projected recipients and subsystem vacancy retention.
Identifiers, units, booleans, nulls and numeric kinds remain exact; floating
values use the existing relative `1e-10` / absolute `1e-9` tolerance.

## B04.2.3.1 charge commands and discovery

`charge_edits.py` runs the unchanged pinned calculation command, original Ammo
service and original browser union method in the isolated reference checkout.
It compares two fresh processes and the unchanged logical dataset. The matrix
covers 14 cases/74 states and complete compatible sets for 4,242 supported modules:
ordinary/T2 ammunition, laser/mining crystals, scripts, cap-booster volume,
ancillary paste, structure missiles, empty/no-charge fits and linked recipients.
Recipient values are read only after EOS calculates their invalidated attributes.

Use the installed reference Python with `-I tools/android_reference/charge_edits.py`,
`--source` the clean pinned checkout, `--database` the verified reference database,
`--output` a new disposable directory outside both checkouts, and
`--check tools/android_reference/fixtures/charge-edits.json` for verification.
The expected fixture contains original source hashes, settings, full inputs,
identities, raw values and units. Integer/bool/null identities remain exact;
float comparisons retain relative 1e-10 and absolute 1e-9 tolerances. The original
desktop disables the optional global EOS gamedata cache; this exporter does too.
No Android adapter is imported and no original calculation body is replaced.

## B04.2.3.2 variation commands and menus

Run installed reference Python with `-I tools/android_reference/variation_edits.py`,
`--source` the clean pin, `--database` the verified dataset, `--output` a fresh
external directory, and `--check tools/android_reference/fixtures/variation-edits.json`.
`variation_oracle.py` executes unchanged AST definitions for original GUI/calc
commands and the variation menu, using real wx command history, Market and Fit.
Inert menu/event recipients replace only presentation, capturing the original
ordering, grouping and enablement decisions. EOS bodies are unchanged.

Two fresh processes compare 5,226 published supported families (including every
additional member returned by the original menu) and 17 cases/55 states. Cases
cover charge retention/unloading, active Breach Control falling back to online,
rig/structure edits, separate drone stack order/quantities, active/inactive FIT
implants (including families spanning multiple slots) and six projection/command recipients. Settings, source hashes, full
inputs, raw values/types/units and unchanged database digest remain recorded.
Use the existing exact identity/type and 1e-10 relative/1e-9 absolute numeric rules.

## B04.2.3.3 rack ordering and heat

Run `rack_ordering.py` with the installed reference Python, `-I`, pinned `--source`,
verified `--database`, a new external `--output`, and
`--check tools/android_reference/fixtures/rack-ordering.json`. The oracle executes
unchanged original GUI/calculation swap commands and the complete Thermodynamics
class, with real wx command history, Fit and EOS. Its nine cases/48 states cover
all five editable racks, occupied/vacant swaps, mixed states and charges, heat
distances and four recipients. Original startDrag requires an occupied source.
Fresh-process repeat, source hashes, settings and unchanged data remain required.
Burnout cycles are integers, seconds and probabilities decimals; raw units and
the existing 1e-10 relative/1e-9 absolute tolerance remain unchanged.

### B05.1 bulk ammunition reference

`bulk_charges.py` executes the pinned original context-menu selector, command
wrapper, calculation command and similar-module helper with real Market/Ammo/EOS
and wx history. Only window/mouse input plumbing is supplied. Nine synthetic cases
and 41 states cover asymmetric mixed compatibility, related variants, explicit
selected/all-similar scopes, modifier inversion, ammo/scripts/crystals, no-ops
and four linked recipients. It checks source/data identity and repeats in fresh
processes; Android code is never imported.

Run with the existing reference Python:
`python -I tools/android_reference/bulk_charges.py --source <pinned-checkout> --database <verified-eve.db> --output <new-outside-checkout-directory> --check tools/android_reference/fixtures/bulk-charges.json`.
