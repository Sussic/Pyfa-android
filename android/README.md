# Offline Android engine development (A07)

Native Kotlin/Compose application in `app/`. A07 embeds the existing Python EOS,
bundles the complete pinned game database and calculates the synthetic A01 Vexor
without network access. Both guns can change ammunition together; the sample
shows drone control range and all 38 sampled attributes. Creating/saving user
fits, projection/command Android checks and the complete fitting UI are later tasks.
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
CI installs the exact Temurin archive with SHA-256
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
data read-only and keeps sample fits in memory. Startup/call failures are visible;
no substitute result is displayed. This is a provisional bridge, not B01's final
API or R02's persistent-data update system.

Start a fresh API 36 x86_64 emulator with KVM and no previous installation of this
app. On Linux/macOS with GNU `timeout`, Python 3 and adb available:

```sh
bash ci/native-test.sh
```

This disables emulator Wi-Fi/mobile data and enables airplane mode **before the
app is installed**. Do not run the script on a personal phone. It executes three
instrumented tests: offline sample/bulk-ammunition/About navigation, recreation
and landscape Back behavior, and independent A01 raw-value parity. The latter
compares all three states, 38 values and units per state, inputs, settings, item
IDs, dataset identity and the untouched golden fixture hash. It verifies the
native Greenlet module is loaded and EOS rejects database writes. The existing
reference tolerance is retained: absolute 1e-9 / relative 1e-10; boolean/string
values and object keys are exact.

`ci/verify-apk.py` inspects actual APK and nested Chaquopy archive bytes. It verifies
the complete database, source manifest, source freshness, notices and ARM64/x86_64
ELF architecture, Python/SQLite/Greenlet presence and native dependency closure.
Building and inspecting ARM64 libraries does not establish ARM64 runtime support.

The summary rejects absent, skipped, failed or empty native results and requires
all named assertions plus actual native values and four real PNG screenshots.
The evidence writer uses the API 31+ UI automation stdin pipe on the API 36 test
device, avoiding shell quoting and app storage permissions. This test transport
does not raise the application's minimum API; API 24 execution remains unverified.
Shell-owned evidence survives AGP's app uninstall. Failures retain a screenshot
and short logcat excerpt. `build/evidence/native-summary.json` identifies the
actual checkout, APK, device and measured initialization/edit timings. A08/A09
own projection/command Android parity; A10 owns fuller performance measurements.

## CI and deliberate APK delivery

[Android native](../.github/workflows/android.yml) runs for relevant PR code changes
and manual dispatches, with one Ubuntu job, read-only contents permission, pinned
actions, KVM verification, a 25-minute timeout and cancellation of superseded runs.
There are no push duplicates, schedules or persistent caches. The separate host
reference workflow remains unchanged and runs for its existing engine paths.

To obtain an APK after this workflow is merged: open GitHub **Actions → Android
native → Run workflow**, choose the intended branch and enable **Deliver the
tested development APK**. The workflow builds, checks lint/signing, installs and
tests it before upload. Download `pyfa-android-dev-<commit>` from that run's
Artifacts section and unzip it. APK and concise native evidence expire after one
day. Routine PR runs retain evidence only, never APKs. No release is published.

This is an early development APK without fit storage. Stable signing, versioned
upgrades and preserving personal fits belong to R02; do not use ephemeral debug
signing for successive persistent-use releases.

## Evidence

A06's shell checks passed in [PR #6](https://github.com/Sussic/Pyfa-android/pull/6);
its historical [receipt](../docs/android/evidence/a06-native.json) remains unchanged.
A07 native evidence is pending on the task branch; [STATUS](../docs/android/STATUS.md)
records delivery state. Host checks alone do not establish Android support.
ARM64 execution, physical phone behavior, API 24 execution, persistent fit storage
and APK upgrades remain unverified. The existing lint data-extraction-rules warning
belongs to storage/upgrade work. Manual APK upload remains opt-in.
