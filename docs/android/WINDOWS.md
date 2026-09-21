# Windows Android development setup

Use this guide from the repository root in PowerShell. Work only in
`Sussic/Pyfa-android`. Check `git status --short --branch`, remotes and open fork
PRs before changing an existing checkout. Keep existing work. Setup does not
start B03.2 or another feature milestone.

## Toolchain and isolation

The current build files require Python 3.11, JDK 17, Android platform 36 and
Build Tools 35.0.0. Use the checked-in Gradle 8.13 wrapper. The native CI JDK pin
is Temurin 17.0.20.1+1; local setup uses its Windows x64 ZIP. Python 3.11.9 x64
matches the established Windows reference environment; native CI uses 3.11.16.
Do not use the system's default Python 3.13 or Java 21 for these commands.

Install the required SDK packages through Android Studio if absent. Inspect
`%LOCALAPPDATA%\Android\Sdk\platforms\android-36\source.properties` and
`build-tools\35.0.0\source.properties`; do not replace other installed versions.

Keep `.venv/headless` separate from `.venv/reference`, both without
`--system-site-packages`. The former builds/tests the Android engine; the latter
has real wxPython for the independent desktop oracle and migration check.
Desktop native wheels must never enter the APK. `prepare-dependencies.py`
prepares and verifies the six Android input wheels, including both native ABIs.

```powershell
py -0p
py -3.11 -c "import sys, struct; print(sys.version); assert struct.calcsize('P') == 8"
py -3.11 -m venv .venv/headless
py -3.11 -m venv .venv/reference
$headless = Join-Path $PWD '.venv/headless/Scripts/python.exe'
$reference = Join-Path $PWD '.venv/reference/Scripts/python.exe'
& $headless -m pip install --use-feature=truststore --only-binary=:all: pip==25.1.1 setuptools==68.2.2 wheel==0.41.3 -r tools/android_headless/requirements.txt
& $reference -m pip install --use-feature=truststore --only-binary=:all: -r tools/android_reference/requirements.txt
& $headless -m pip check
& $reference -m pip check
```

The truststore flag lets the initial pip 24 use trusted Windows certificates.
Do not disable TLS verification or add `--trusted-host` to work around issuer
errors. On this host, Git also needed the Windows certificate store:
`git config --local http.sslBackend schannel`. For a new clone use
`git -c http.sslBackend=schannel clone --filter=blob:none https://github.com/Sussic/Pyfa-android.git .`
only in an empty folder. Filtered history downloads older blobs on demand.

The Windows Temurin archive is
`OpenJDK17U-jdk_x64_windows_hotspot_17.0.20.1_1.zip` from the official
[Temurin release](https://github.com/adoptium/temurin17-binaries/releases/tag/jdk-17.0.20.1%2B1),
SHA-256 `e53a79c3c3d86865bd7e787903884331068e71321714ffd44f145785affc7cb0`.
Extract it into ignored `build/tools/`, then configure this PowerShell session.
The property-file commands below are for a new setup; for existing files, merge
these keys and preserve all other settings:

```powershell
$env:JAVA_HOME = Join-Path $PWD 'build/tools/jdk-17.0.20.1+1'
$env:ANDROID_HOME = Join-Path $env:LOCALAPPDATA 'Android/Sdk'
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:GRADLE_USER_HOME = Join-Path $env:LOCALAPPDATA 'PyfaAndroid/PyfaDevelopment/gradle-home'
$env:PYTHONUTF8 = '1'
$env:PATH = "$PWD/.venv/headless/Scripts;$env:JAVA_HOME/bin;$env:ANDROID_HOME/platform-tools;$env:PATH"
$env:JAVA_OPTS = '-Djavax.net.ssl.trustStoreType=Windows-ROOT -Djavax.net.ssl.trustStore=NONE -Djava.net.useSystemProxies=true'
New-Item -ItemType Directory -Force $env:GRADLE_USER_HOME | Out-Null
@"
systemProp.javax.net.ssl.trustStoreType=Windows-ROOT
systemProp.javax.net.ssl.trustStore=NONE
systemProp.java.net.useSystemProxies=true
"@ | Set-Content "$env:GRADLE_USER_HOME/gradle.properties" -Encoding ascii
"sdk.dir=$($env:ANDROID_HOME.Replace('\','/').Replace(':','\:'))" | Set-Content android/local.properties -Encoding ascii
& "$env:JAVA_HOME/bin/java.exe" -version
```

Keep Gradle's cache outside OneDrive: the first local instrumentation build
failed renaming an immutable transform workspace in the synced folder. This
per-project AppData cache, ignored files and session variables leave system
Python, Java, PATH and other projects unchanged. Choose this JDK as Android
Studio's Gradle JDK when opening `android/`. In the prepared local workspace, `. ./build/windows-env.ps1` restores
these settings and sets `$pyfaHeadless` and `$pyfaReference`; the helper contains
machine-specific paths and is intentionally untracked. For the commands below
after restoring that helper, set `$headless = $pyfaHeadless` and
`$reference = $pyfaReference`.

Verify the wrapper JAR hash against `android/README.md`. If the wrapper's
10-second network timeout interrupts its distribution download, obtain the same
`https://services.gradle.org/distributions/gradle-8.13-bin.zip` with Windows
`Invoke-WebRequest -TimeoutSec 600`. Verify SHA-256
`20f1b1176237254a6fc204d8434196fa11a4cfb387567519c61556e8710aed78` before placing
it as `gradle-8.13-bin.zip` in the wrapper-created hash directory below
`$env:GRADLE_USER_HOME/wrapper/dists/gradle-8.13-bin/`. Then rerun the wrapper.
Its distribution URL, checksum and JAR stay unchanged.

## Build and inspect locally

Stop if any command fails; do not describe later commands as passing.

```powershell
& $headless android/prepare-dependencies.py
& $headless -I android/prepare-engine.py
Push-Location android
./gradlew.bat --version
./gradlew.bat --no-daemon --console=plain :app:assembleDebug :app:assembleDebugAndroidTest :app:lintDebug
& "$env:ANDROID_HOME/build-tools/35.0.0/apksigner.bat" verify --verbose --print-certs app/build/outputs/apk/debug/app-debug.apk
& $headless ci/verify-apk.py
Pop-Location
```

If a corrected `local.properties` still produces the previous lint finding,
force fresh analysis with `./gradlew.bat --no-daemon --console=plain
:app:lintAnalyzeDebug --rerun :app:lintDebug` (one command from `android/`).
Do not add a baseline or suppress the property-escaping check.

`verify-apk.py` needs GNU `readelf` on PATH. This machine has
`C:/Strawberry/c/bin/readelf.exe` (binutils 2.42). Add that directory to the current
PATH if needed. Keep its real ELF/dependency checks; if readelf is unavailable,
record APK inspection as pending CI rather than skipping its assertions.

Output: `android/app/build/outputs/apk/debug/app-debug.apk`, package
`io.github.sussic.pyfa.dev`. The instrumentation APK is under
`android/app/build/outputs/apk/androidTest/debug/`. Preparation receipts and APK
inspection live in `android/build/evidence/`; lint reports live in
`android/app/build/reports/`. Re-run engine preparation after source/data changes.
Do not install this debug APK over personal phone data; stable signing and tested
upgrades remain R02 work.

## Independent Windows host checks

Use a clean separate checkout at the original desktop commit, never the Android
working tree as its own oracle. One local option sharing the fork's Git objects:

```powershell
git worktree add --detach --no-checkout build/reference-upstream 8b04f3b271e614b3e103853b44a7851a63d79d0e
git -C build/reference-upstream sparse-checkout set --cone eos utils staticdata
git -C build/reference-upstream checkout --detach 8b04f3b271e614b3e103853b44a7851a63d79d0e
git -C build/reference-upstream status --short --branch
$run = Join-Path $env:TEMP ('pyfa-windows-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $run | Out-Null
& $reference -m unittest discover -s tools/android_reference/tests -v
& $reference -I tools/android_reference/reference.py --source build/reference-upstream --output "$run/reference" --check tools/android_reference/fixtures/vexor.json
$db = "$run/reference/eve.db"
& $reference -I tools/android_headless/check_desktop_migration.py --database $db
& $reference -I tools/android_reference/projection.py --source build/reference-upstream --database $db --output "$run/projection-reference" --check tools/android_reference/fixtures/projection.json
& $reference -I tools/android_reference/command.py --source build/reference-upstream --database $db --output "$run/command-reference" --check tools/android_reference/fixtures/command.json
& $headless -I tools/android_headless/check.py --database $db --output "$run/headless"
& $headless -I tools/android_headless/check.py --scenario projection --database $db --output "$run/projection"
& $headless -I tools/android_headless/check.py --scenario command --database $db --output "$run/command"
& $headless -I tools/android_headless/check_bridge.py --database $db --output "$run/bridge"
& $headless -I tools/android_headless/check_persistence.py --database $db --output "$run/persistence"
& $headless -I tools/android_headless/check_library.py --database $db --output "$run/library"
```

Reuse the existing clean reference worktree on subsequent runs. Run the timed
host suites after Gradle has finished; the initial concurrent
persistence attempt on this machine reported errors. Every output child directory
must be new and outside both checkouts. These scripts validate
integrity, independent raw values, forbidden desktop/network imports and fresh
process behavior; never substitute a personal fit database. The current total is
73 tests (eight utility, 29 headless, 14 bridge, 14 persistence, eight library),
plus independent desktop exports/repeats and the real migration/backup check.
The prepared workspace's ignored `build/check-windows.ps1` runs these gates with
failure checking and records the new evidence path in `build/windows-check-path.txt`.

## Required native evidence

A local APK, lint, signature, package inspection and host tests do not prove
Android runtime behavior. Preserve `.github/workflows/android.yml` and
`android/ci/native-test.sh` unchanged. Their fresh offline API 36 x86_64 emulator
sequence requires all **13 native executions**: five functional tests, separate
A10 performance and B01 contract, three B02 persistence phases, and three B03.1
library phases. Preserve raw-value validators, restart boundaries and screenshot
review. Do not run an unfiltered connected suite or this fresh-install script on
a personal phone. The supported full native harness uses Ubuntu/KVM and GNU
`timeout`; this setup does not port it to Windows or claim to have run it locally.

Docs-only setup changes need link/scope review and `git diff --check`; do not
manually dispatch an emulator run for them. Existing path filters also match
`tools/android_reference/README.md`, so editing that guide starts both PR
workflows automatically. Let any triggered required checks finish before merging;
do not weaken path filters or duplicate the run. Subsequent runtime changes
retain both native and host CI gates. Existing one-day retention, opt-in APK delivery, read-only
permissions, concurrency and billing settings remain unchanged. Physical ARM64,
older APIs and install-over-existing-data behavior remain separate unverified
work. See [STATUS](STATUS.md) for the actual checkpoint and next authorized action.
