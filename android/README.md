# Android development shell (A06)

Native Kotlin/Compose application in `app/`. It displays an honest development
status, build version and offline About screen. There is no fitting engine,
database, saved-fit storage or fabricated fitting result in this milestone.
The APK has no Internet permission. The root GPLv3 license is bundled as an asset;
upstream source and notices remain in the repository.

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
| CI host / emulator | ubuntu-24.04 / emulator 37.1.11, build 15917651 |
| Native test device | API 36, google_apis, x86_64, Pixel 2 profile, KVM |

Selected from the documented compatibility intersection, checked 2026-09-13:
[AGP 8.11](https://developer.android.com/build/releases/agp-8-11-0-release-notes),
[Kotlin's Gradle/AGP ranges](https://kotlinlang.org/docs/gradle-configure-project.html),
[Compose BOM mapping](https://developer.android.com/develop/ui/compose/bom/bom-mapping)
and [Chaquopy compatibility](https://chaquo.com/chaquopy/doc/current/versions.html).
Chaquopy 17.0.0 with Python 3.11 is the provisional A07 choice, **not yet a
dependency or proven Android EOS runtime**. Its Android wheels remain to be tested.

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

The hosted runner image, SDK command-line/platform tools and system-image patch
revision can change independently of API 36. CI retains installed package versions,
emulator version and the device fingerprint. This is a pinned application toolchain,
not a claim that the entire hosted environment is byte-for-byte reproducible.
Debug signing certificates also vary across fresh runners; APK hashes identify
individual builds, not deterministic release binaries.

## Build and native checks

Install the pinned JDK, Android SDK platform 36 and build-tools 35.0.0. Set
`JAVA_HOME` and `ANDROID_HOME` to those installations (or use an ignored
`local.properties` for `sdk.dir`). Open this `android/` directory in Android Studio,
or, from this directory:

```sh
./gradlew --no-daemon --console=plain :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
```

On Windows use `gradlew.bat`. Output is
`app/build/outputs/apk/debug/app-debug.apk`, package `io.github.sussic.pyfa.dev`.
No secrets, server or EVE login are needed. Build dependencies need a connection
on a fresh build machine; the installed shell does not.

Start a fresh API 36 x86_64 emulator with KVM and no previous installation of this
app. On Linux/macOS with GNU `timeout`, Python 3 and adb available:

```sh
bash ci/native-test.sh
```

This disables emulator Wi-Fi/mobile data and enables airplane mode **before the
app is installed**. Do not run the script on a personal phone. It executes two
real Compose instrumented tests:

- Fresh offline launch shows the unavailable fitting status, has no Internet
  permission, opens the versioned About screen and returns with its Back button.
- About survives activity recreation and landscape rotation; its lower content
  is reachable by scrolling, and Android's Back dispatcher returns home.

The summary rejects absent, skipped, failed or empty native results and requires
both named assertions. Screenshots come from Android's UI automation, including a
landscape scroll; failures retain a current screenshot and a short logcat excerpt.
`build/evidence/native-summary.json` records the actual checkout, APK and device.
These tests prove only the shell behavior. A07–A09 own the EOS runtime/parity tests;
ARM64 runtime, physical phone behavior and full offline fitting remain unverified.

## CI and deliberate APK delivery

[Android native](../.github/workflows/android.yml) runs for relevant PR code changes
and manual dispatches, with one Ubuntu job, read-only contents permission, pinned
actions, KVM verification, a 25-minute timeout and cancellation of superseded runs.
There are no push duplicates, schedules or persistent caches. The separate host
reference workflow remains unchanged and runs for its existing engine paths.

To obtain an APK after this workflow is merged: open GitHub **Actions → Android
native → Run workflow**, choose the intended branch/commit and enable **Deliver the
tested development APK**. The workflow builds, checks lint/signing, installs and
tests it before upload. Download `pyfa-android-dev-<commit>` from that run's
Artifacts section and unzip it. APK and concise native evidence expire after one
day. Routine PR runs retain evidence only, never APKs. No release is published.

This is an early development APK without fit storage. Stable signing, versioned
upgrades and preserving personal fits belong to R02; do not use ephemeral debug
signing for successive persistent-use releases.

## Evidence

A06 native validation is pending. See [STATUS](../docs/android/STATUS.md) for the
active PR/check and the exact next task. No passing build or emulator result is
claimed until its actual run is recorded.
