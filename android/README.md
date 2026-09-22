# Offline Android engine development (B04.1)

Native Kotlin/Compose application in `app/`. A07 embeds the existing Python EOS,
bundles the complete pinned game database and calculates the synthetic A01 Vexor
without network access. Both guns can change ammunition together; the sample
shows drone control range and all 39 sampled attributes. B02 persists fit graphs;
B03.1 adds creation from bundled examples, search, open, rename, copy and deletion.
B03.2 adds hull/race browsing, recently modified fits and saved open-fit navigation.
Full hull/equipment editing remains later work.
A08/A09 add native projection
and command checks against the unchanged A04/A05 references; they do not add
projection or command editors to the sample UI.
The APK has no Internet permission. Root GPLv3 and EOS LGPL notices are included.

## Toolchain

| Component | Pin |
| --- | --- |
| JDK | Eclipse Temurin 17.0.20.1+1, JDK 17 bytecode |
| Gradle | 8.13, canonical wrapper with SHA-256 distribution verification |
| Android Gradle plugin | 8.11.1 |
| Kotlin / Compose compiler plugin | 2.2.21 / 2.2.21 |
| Compose BOM | 2025.10.01 (UI 1.9.4, Material 3 1.4.0) |
| Activity Compose | 1.11.0 |
| AndroidX test runner / JUnit extension | 1.7.0 / 1.3.0 |
| Compile / target / minimum API | 36 / 36 / 24 (Android 7.0 minimum) |
| SDK build tools | 35.0.0 |
| SDK command-line tools | 19.0, archive 13114758, SHA-256 checked |
| CI host / emulator | ubuntu-24.04 / emulator 37.1.11, build 15917651 |
| Embedded runtime | Chaquopy 17.0.0 / Python 3.11 |
| Android Python packages | Logbook 1.7.0.post0, SQLAlchemy 1.4.50, Greenlet 3.0.1 build 1, chaquopy-libcxx 180000 build 0 |
| Native test device | API 36, google_apis, x86_64, Pixel 2 profile, KVM |

Selected from the documented compatibility intersection, checked 2026-09-13:
[AGP 8.11](https://developer.android.com/build/releases/agp-8-11-0-release-notes),
[Kotlin's Gradle/AGP ranges](https://kotlinlang.org/docs/gradle-configure-project.html),
[Compose BOM mapping](https://developer.android.com/develop/ui/compose/bom/bom-mapping)
and [Chaquopy compatibility](https://chaquo.com/chaquopy/doc/current/versions.html).
A07 uses [Chaquopy's Android integration](https://chaquo.com/chaquopy/doc/current/android.html)
and [Android wheel repository](https://chaquo.com/pypi-13.1/), checked 2026-09-14.
See the evidence section for the actual runtime validation state.

`prepare-dependencies.py` verifies source/archive SHA-256 values and builds the
supported pure-Python variants of Logbook and SQLAlchemy. SQLAlchemy 1.4.50's
`Distribution.has_ext_modules` always returns true: after confirming the wheel
contains no native binaries, the script corrects its wheel tags and regenerates
RECORD hashes without changing package code. Android Greenlet uses the available
3.0.1 build 1 wheels (API 24, ARM64/x86_64), with pinned native libc++ dependencies.
The independent desktop environment remains on Greenlet 3.0.3. Gradle's Python
package install uses only these six prepared wheels with `--no-index`.

One additional upstream compatibility correction is isolated to
`eos/db/migrations/__init__.py`: dynamic import now uses `fromlist=["upgrade"]`
instead of the invalid boolean accepted by desktop CPython but rejected by
Chaquopy's import hook. Migration functions and calculation formulas are unchanged.
Native tests require all 49 migration functions to be discovered; the separate
desktop workflow exercises the real 48-to-49 migration and backup.

Gradle distribution SHA-256:
`20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78`.
Wrapper JAR SHA-256:
`81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f`.
Both were checked against Gradle's published distribution/checksum endpoints.
Do not edit the wrapper JAR or change pins without reviewing compatibility.
CI installs the exact Linux Temurin archive with SHA-256
`3808d1d15e3ec6bd5b84057fb5d84c33d8a1536a258146bcea2e603fc726e08e`.
The four-part JDK version is not accepted by setup-java's version parser, so the
workflow checks and extracts the pinned vendor archive directly.

The hosted runner image, SDK platform tools and system-image patch
revision can change independently of API 36. CI retains installed package versions,
emulator version and the device fingerprint. This is a pinned application toolchain,
not a claim that the entire hosted environment is byte-for-byte reproducible.
Debug signing certificates also vary across fresh runners; APK hashes identify
individual builds, not deterministic release binaries.

## Build and native checks

For a local Windows checkout, follow [Windows setup](../docs/android/WINDOWS.md)
for separate Python environments, PowerShell commands, certificate-store setup,
host verification and the boundary between local checks and native CI.

Install the pinned JDK, Android SDK platform 36 and build-tools 35.0.0. Set
`JAVA_HOME` and `ANDROID_HOME` to those installations (or use an ignored
`local.properties` for `sdk.dir`). Open this `android/` directory in Android Studio,
or, from this directory, using a clean Python 3.11 environment:

```sh
python -m pip install --only-binary=:all: -r ../tools/android_headless/requirements.txt pip==25.1.1 setuptools==68.2.2 wheel==0.41.3
python prepare-dependencies.py
python -I prepare-engine.py
./gradlew --no-daemon --console=plain :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
python ci/verify-apk.py
```

On Windows use `gradlew.bat`. Output is
`app/build/outputs/apk/debug/app-debug.apk`, package `io.github.sussic.pyfa.dev`.
No secrets, server or EVE login are needed. Build dependencies need a connection
on a fresh build machine; the installed app does not.

Prepare after every source/data change. `prepare-engine.py` reads this checkout's
`eos`, `utils`, `android_bridge`, `db_update.py`, `staticdata` and reference tools;
include those paths in sparse checkouts. It checks the static-data digest against
the pinned desktop fixture, builds the database through the original builder,
checks SQLite integrity and logical identity, and stages normalized source files.
No generated database or wheel is committed. Data generation imports the fork's
existing A03 lazy migration import; its logical result must exactly match A01.
Golden results are copied only into the instrumentation APK, never the app.

The process-owned `pyfa-engine` executor installs a checksum-verified database
atomically into app-private files and boots EOS off the UI thread. Python source
is packaged from the existing tree, not a maintained duplicate. EOS opens game
data read-only and uses a transient calculation graph plus a separate durable fit
store in app-private, no-backup storage. Startup/call failures are visible;
no substitute result is displayed. B01 adds a strict typed mutation/query contract,
revision checks and failure recovery; see the [contract and boundaries](../docs/android/tasks/B01-typed-bridge.md).
The game-data installation is not R02's persistent-data update system.
B02 saves the complete committed graph and recalculates it on restart; see the
[storage boundary](../docs/android/tasks/B02-local-persistence.md). Invalid or
incompatible saved data is preserved and startup fails visibly.

Start a fresh API 36 x86_64 emulator with KVM and no previous installation of this
app. On Linux/macOS with GNU `timeout`, Python 3 and adb available:

```sh
bash ci/native-test.sh
```

This disables emulator Wi-Fi/mobile data and enables airplane mode **before the
app is installed**. Do not run the script on a personal phone. It executes five
instrumented tests: offline sample/bulk-ammunition/About navigation, recreation
and landscape Back behavior, and independent A01 raw-value parity. The latter
compares all three states, 38 values and units per state, inputs, settings, item
IDs, dataset identity and the untouched golden fixture hash. It verifies the
native Greenlet module is loaded and EOS rejects database writes. The existing
reference tolerance is retained: absolute 1e-9 / relative 1e-10; boolean/string
values and object keys are exact.

The fourth test checks A04's Celestis/Vexor projections: 39 raw statistics and
units on each fit in 11 states (apply, distance, disable/reactivate, source script
edit/restoration, remove/reapply/remove). Nine additional phases check two
recipients and an unlinked control, reading recipient two before one after source
edits. Five apply/remove cycles check both directions of every association and
all restored values. The entire probe repeats on the same worker; A01 ammunition
parity is checked again afterward. No manual recipient refresh or golden values
are used in production Python. `projection-expected.json` is test-APK-only.

The fifth test checks A05's Vulture/Vexor command bursts: 39 raw statistics and
units on each fit in 19 states, including both source skills, mindlink addition/
state/removal, burst module state, command-link state and both shield charges.
Eighteen additional phases exercise two recipients and an unlinked control,
reading recipient two first; link edits affect only the selected recipient.
Five apply/remove cycles verify complete restoration and both link directions.
All 112 observed pending-command-bonus counts must be zero after snapshots.
The entire command probe repeats on the same worker, followed by independent A01
and A04 comparisons. `command-expected.json` stays in the test APK; the runtime
contains only operations, actual observations and case-specific provenance.

`ci/verify-apk.py` inspects actual APK and nested Chaquopy archive bytes. It verifies
the complete database, source manifest, source freshness, notices and ARM64/x86_64
ELF architecture, Python/SQLite/Greenlet presence and native dependency closure.
Building and inspecting ARM64 libraries does not establish ARM64 runtime support.

The summary rejects absent, skipped, failed or empty native results and requires
all five named assertions plus actual native values and four real PNG screenshots.
A10 then reinstalls for five normal app launches and a separate, fresh-process
performance test. It verifies 120 edit snapshots against desktop fixtures and
retains startup phases, raw edit samples and process-memory snapshots. Read the
[A10 measurement boundaries](../docs/android/tasks/A10-embedding-feasibility.md)
before interpreting these debug/emulator numbers. The performance class must run
separately: do not invoke an unfiltered connected suite. B01 then force-stops the
app and runs `BridgeContractTest` alone via `ci/check-contract.py`. That test
exercises the typed request path, independent A01/A04/A05 values, stale revisions,
atomic rejection, request serialization and strict codec errors. Its complete
responses and provenance are retained in `contract-native.json`.
B02 follows with `ci/check-persistence.py`: prepare, reopen/edit and verify run
in three separate processes, with no uninstall or data clearing between them.
Nine fits retain identities/revisions and active/inactive projection/command links;
45 snapshots are compared with the independent fixtures. `PersistenceTest` must
also be excluded from the initial connected suite. `DiagnosticTestRunner` selects
ephemeral storage for the older direct-engine probes; only B02 instrumentation
and normal app launches use production persistence.
The evidence writer uses the API 31+ UI automation stdin pipe on the API 36 test
device, avoiding shell quoting and app storage permissions. This test transport
does not raise the application's minimum API; API 24 execution remains unverified.
Shell-owned evidence survives AGP's app uninstall. Failures retain a screenshot
and short logcat excerpt. `build/evidence/native-summary.json` identifies the
actual checkout, APK, device and measured initialization/edit timings.
`projection-native.json` and `command-native.json` retain every linked-fit
observation and its fixture/data/source provenance. A10 adds [separate startup/edit/process-memory measurements](../docs/android/tasks/A10-embedding-feasibility.md).

## CI and deliberate APK delivery

[Android native](../.github/workflows/android.yml) runs for relevant PR code changes
and manual dispatches, with one Ubuntu job, read-only contents permission, pinned
actions, KVM verification, a 25-minute timeout and cancellation of superseded runs.
There are no push duplicates, schedules or persistent caches. The separate host
reference workflow also runs B01 contract recovery and B02 subprocess persistence,
interrupted-save and invalid-store checks for
its existing engine paths.

To obtain an APK after this workflow is merged: open GitHub **Actions → Android
native → Run workflow**, choose the intended branch and enable **Deliver the
tested development APK**. The workflow builds, checks lint/signing, installs and
tests it before upload. Download `pyfa-android-dev-<commit>` from that run's
Artifacts section and unzip it. APK and concise native evidence expire after one
day. Routine PR runs retain evidence only, never APKs. No release is published.

This development APK includes persistent fit storage. Stable signing, versioned
upgrades and preserving personal fits belong to R02; do not use ephemeral debug
signing for successive persistent-use releases.

## Evidence

A06's shell checks passed in [PR #6](https://github.com/Sussic/Pyfa-android/pull/6);
its historical [receipt](../docs/android/evidence/a06-native.json) remains unchanged.
A07 is merged in [PR #7](https://github.com/Sussic/Pyfa-android/pull/7).
[Native CI](https://github.com/Sussic/Pyfa-android/actions/runs/34846081342) passed all
three tests, APK inspection, signing and lint on head
`a4182bd17462dbfe79ddf0dde8cb700429fa89cb`. The 70,361,140-byte APK contains the
99,897,344-byte database and 73 native libraries per ABI. Four screenshots were
reviewed. [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/34846081350)
passed 35 host tests, all independent references and real migration/backup checks.
[The durable receipt](../docs/android/evidence/a07-native.json) preserves raw native
values, exact hashes, selected library identities, toolchain and resolved failures.

Python boot through initial fit creation measured 5.29 s; the edit/report sequence
measured 0.67 s on this emulator. These are not full cold-start or individual-edit
benchmarks. The Python thread name `MainThread` identifies the interpreter's first
thread; Kotlin started it on `pyfa-engine` and asserts it is off the Android UI
thread. See A10 below for separately measured startup, individual edits and process memory.
At A07, ARM64 execution, physical phone behavior, API 24 execution, persistent fit
storage and APK upgrades remained unverified. B02/B03.1 subsequently verified
storage on the CI emulator; physical devices, older APIs and upgrades remain
open. The existing lint data-extraction-rules warning
belongs to storage/upgrade work. Manual APK upload remains opt-in.

A08 is merged in [PR #8](https://github.com/Sussic/Pyfa-android/pull/8).
[Native CI](https://github.com/Sussic/Pyfa-android/actions/runs/35159732933) passed all four tests on head
`7799cecf906950c24f7e23901d359df99030fedf` on the first run. The unchanged A04 fixture,
all nine recipient phases, five removal cycles and complete same-worker repeat
pass; A01 also passes after projection verification. Package checks cover both
mobile Python sources and both ABIs. [A08's durable receipt](../docs/android/evidence/a08-native.json)
retains every native observation, exact build/data hashes, JUnit and host evidence.
This adds bounded projection feasibility, not the projection editor or full
D01/D02 coverage. A09 subsequently added the command evidence below.

A09 is merged in [PR #9](https://github.com/Sussic/Pyfa-android/pull/9).
[Native CI](https://github.com/Sussic/Pyfa-android/actions/runs/35161269681) passed all five tests on head
`e5e249b9ac95b9144d16f99de4801473661ffa05` on the first run. A05's 19 states, all
18 recipient phases, five removal cycles and 112 pending-bonus checks pass,
including a complete same-worker repeat and A01/A04 after command operations.
[The A09 receipt](../docs/android/evidence/a09-native.json) retains all raw values,
source/data/build hashes, JUnit, package checks and focused host evidence.
This is bounded command feasibility; full editors and remaining burst/overlap
cases stay on the roadmap. A10 follows with the measured embedding decision below.

A10 is merged in [PR #10](https://github.com/Sussic/Pyfa-android/pull/10).
[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35288937092) passes five
functional tests plus one separate performance test. [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35288937029)
passes 37 host tests, independent references and real migration/backup. The longer
benchmark also found and fixed source modules losing calculated bonuses after ORM
relationship refresh; two forced-GC regressions guard all four add/remove paths.

The [A10 decision](../docs/android/tasks/A10-embedding-feasibility.md) retains the
embedded EOS/Chaquopy worker for B01. Normal process-to-ready-draw is 2.960 s first
install and 2.008 s subsequent median; five edit medians range 10.258–60.421 ms.
Normal ready-fit PSS is 154.1–184.8 MiB; instrumented graph snapshots are cumulative
and are not peak/leak measurements. APK size: 70,395,255 bytes. [The durable receipt](../docs/android/evidence/a10-native.json)
retains all observations and measured boundaries. These debug x86_64 results do
not establish physical ARM64, older APIs, release speed, large graphs or full parity.


B01 is merged in [PR #11](https://github.com/Sussic/Pyfa-android/pull/11).
[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35295023667) passes seven native tests and package checks;
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35295023583) passes 51 host tests, independent
references and migration/backup. The typed request path matches 63 full desktop
snapshots and preserves raw types, units and revisions. Rejected and failed edits
preserve the committed fit; malformed replies make the bridge unavailable until
restart. [Contract and scope](../docs/android/tasks/B01-typed-bridge.md),
[raw retained evidence](../docs/android/evidence/b01-native.json). The visible app
remains the sample fit. B02 adds persistent fits and links, with the fit library
screen reserved for B03. The retained A10 edit timings measure the ephemeral
calculation path; they do not include B02 durable-save latency.


## B02 delivery

[PR #12](https://github.com/Sussic/Pyfa-android/pull/12) delivers atomic local fit
storage and process-restart restoration. [Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35389186247) passes the seven
existing native tests plus three persistence phases; 45 new snapshots match the
independent desktop values. [Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35389186269) passes 65 host tests, the
independent references and migration/backup check. [Full evidence and limits](../docs/android/evidence/b02-native.json)
remain in the repository after CI artifacts expire. B03.1 subsequently added the
fit library described below. B03.2 adds the organization workflow below.

## B03.1 fit library

The development library creates bundled Vexor/Celestis/Vulture example fits, searches names/hulls, opens, renames, copies and confirms deletion. Equipment/hull selection remains later work. Copies retain incoming linked-source identities; deleting a source refreshes recipients in the same durable transaction. Empty stores reopen empty.

`ci/native-test.sh` retains every prior suite and runs `ci/check-library.py` in three additional production-storage processes after B02. It exercises native controls, dialog recreation, Unicode/search/open/cancel, independent ammunition edits, two-recipient projection/command deletion and empty-store reopen/recreation. `library_summary.py` independently checks retained raw outputs against pinned desktop fixtures. Screenshots and raw receipts share the existing one-day diagnostic artifact; no APK upload or release is added.

## B03.2 organization and open fits

Browse all 55 desktop hull groups and 437 hulls, filter races and empty groups,
return from a fit to its hull, and find the 50 most recently modified fits.
Opening or switching fits does not affect modification order. Multiple open
views can be closed individually or together without deleting saved fits.
Restart restoration is opt-in and includes the active fit. Older fit stores
remain readable; their historical edit order is explicitly unknown.

`ci/check-navigation.py` follows B03.1 with four separate offline processes,
without reinstalling or clearing app data. `navigation_summary.py` verifies
restart boundaries, desktop catalogue metadata and every retained raw statistic.
Run the full `ci/native-test.sh` on its disposable CI emulator to retain all 17
required executions. Do not run the unfiltered phase tests on a personal phone.
The same one-day evidence artifact includes four additional screenshots.

## B04.1 equipment discovery

The equipment browser reads the complete offline Market catalogue on demand on
the EOS worker, outside launch timing. It supports group navigation, name/regex/
wildcard/default-jargon search, Normal/Faction/Complex/Officer filters, paginated
results and a selected item's market-group jump. Browser state survives activity
recreation. Fitting edits and recently used items remain B04.2; parent B04 stays
open and all inventory requirements remain.

`ci/check-market.py` adds a separate production-storage native execution after
all 17 prior executions. Full typed catalogue equality covers 718 groups and
6,822 items; all 22 real desktop search results are compared. Native touches check
tree navigation, selection/jump, filters, empty results, pagination, recreation
and unchanged saved fits. Raw catalogue/search data, provenance and five screens
are retained in the existing one-day artifact. Current total: 18 native executions.

## B04.2.1 empty ships and structures

New fit opens a searchable paginated picker for every bundled hull. The hull
browser can preselect a ship or structure. Creation uses all-V skills and no
equipment/additions; saved empty fits can be named, copied and reopened. Missing
gun ranges display "Unavailable" while calculated zero damage stays numeric.
Example fits remain accessible. Equipment mutations and structure modes retain
their later B04/B06 scope.

`ci/check-empty-hulls.py` adds two production-storage processes after all 18 prior
executions. It verifies every one of the 437 hulls against the independent desktop
reference, native picker/search/page/recreation and ship/structure creation/copy,
atomic rejection and force-stop/reopen. The strict raw validator and four new
screenshots use the existing one-day artifact policy. Older builds reject these
empty-module fits without replacing the file; downgrade/upgrade safety is R02.
