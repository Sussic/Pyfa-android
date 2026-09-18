# A10 — Embedding feasibility

Status: **done**, 2026-09-18. [PR #10](https://github.com/Sussic/Pyfa-android/pull/10),
merged as `7d16aa226df1b80e5e2f21740ac2587b3e0ac1f3`. Tested head: `ca331deb09756e3d3ccaec175a16dd52553746aa`.
[Native CI](https://github.com/Sussic/Pyfa-android/actions/runs/35288937092) and
[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35288937029) passed on the first run.
[Raw values, timings, memory, provenance and checks](../evidence/a10-native.json).

## Question and unchanged scope

Can the existing EOS engine, embedded locally with Chaquopy and a serialized
Kotlin worker, support continued development of offline Android Pyfa? This gate
must measure startup, individual edit/recalculation latency, process memory and
APK size, preserve the independent A01/A04/A05 comparisons, and identify device
and dependency limits. It does not certify full feature parity or release usability.

## Decision: retain the embedded engine for B01

Continue with Kotlin/Compose, Chaquopy 17.0.0 and the existing EOS on a single
serialized worker. The actual Android build calculates the independent ammunition,
projection and command cases offline. After repairing source refresh, the bounded
edit timings and process-memory snapshots support continued development. There is
no observed blocker here that warrants replacing EOS or introducing a server.

This is a feasibility decision, not a release or usability acceptance. The source
refresh bug shows why longer-lived fit graphs and independent comparisons must
remain gates. Keep the supported pins below; B01 must preserve serialized access
and explicit invalidation. Later work must verify lifecycle/release of fits,
persistence, physical ARM64 and older supported APIs, release builds, large fleets,
graphs and UI latency, long sessions and upgrades before personal-use releases.

## Measured native results

API 36 x86_64 Google APIs emulator, Pixel 2 profile, KVM, two CPUs and 2,048 MiB RAM
on an Ubuntu 24.04 GitHub runner. Airplane mode and disabled Wi-Fi/mobile data;
no Internet permission. Debug version 0.1.0-a10. Raw samples are in the receipt.

| Startup observation | Result |
| --- | --- |
| First installation: process start to ready fit draw | 2,959.652 ms (one sample) |
| New process, database retained | 1,984.182 / 2,347.359 / 1,994.769 / 2,020.307 ms |
| Median of those four subsequent process launches | 2,007.538 ms |
| Database validation/copy phase on first launch | 1,117.523 ms |
| Median subsequent database validation phase | 528.650 ms |
| Median subsequent Python start / boot + snapshot phases | 309.845 / 929.166 ms |
| First-install ADB request to completed receipt | 3,680.089 ms, including ADB/write/poll overhead |

Medians of separate phases need not sum to the median whole launch. First-install
app data is fresh; the emulator and OS caches were already used by the functional
suite. These five launches do not include the test runner in the app process.

| Edit operation | Median | Observed p95 | Maximum | Retained fits |
| --- | --- | --- | --- | --- |
| Both guns’ ammunition | 10.258 ms | 10.568 ms | 10.697 ms | 1 |
| Command charge, both recipients | 35.950 ms | 39.115 ms | 41.032 ms | 9 |
| Remove/reapply both command links | 60.140 ms | 67.893 ms | 69.012 ms | 9 |
| Remove/reapply both projection links | 60.421 ms | 66.571 ms | 68.870 ms | 5 |
| Both projection ranges | 21.703 ms | 23.275 ms | 23.460 ms | 5 |

Each row has 20 measured samples plus four warmups: **100 measured edits and 20
warmups**, all compared with the desktop fixtures, plus three setup snapshots.
Graph setup/initial snapshots take 311.210 ms for projections and 308.980 ms for
commands in the already-running process. This includes preparation/provenance,
not only a pure EOS calculation. The operation timing does not include UI frames.

| Process memory snapshot | PSS | Private dirty |
| --- | --- | --- |
| Normal first-launch ready fit | 189,254 kB (184.8 MiB) | 155,220 kB |
| Normal later ready-fit launches | 157,784–158,630 kB (154.1–154.9 MiB) | 124,792–126,720 kB |
| Instrumented single fit, before benchmarks | 188,284 kB (183.9 MiB) | 155,200 kB |
| After projection edits, five fits retained | 229,056 kB (223.7 MiB) | 195,812 kB |
| After command setup, nine fits retained | 236,897 kB (231.3 MiB) | 203,568 kB |
| After command edits, nine fits retained | 205,328 kB (200.5 MiB) | 171,732 kB |

The instrumented cumulative snapshots fluctuate with allocation/collection and
include test reporting. They establish neither peak memory nor leak absence. The correction is
for source calculations, not a demonstrated memory-leak repair.

The dual-ABI debug APK is **70,395,255 bytes (70.4 MB)**, SHA-256
`6a924f1e13bf8fbec487e2c861578e69bea5088156ceafa303212e91f8172b19`.
Its bundled game database is 99,897,344 bytes uncompressed and is copied into
app-private storage on first launch. APK size is not installed disk usage.
Both ABIs contain 73 verified native libraries; only x86_64 was executed.

Five existing native JUnit tests pass with no failures/errors/skips, and the
separate performance invocation reports exactly one passing test (8.108 s).
Windows passes 29 headless tests plus eight utility tests, all three independent
reference exports/repeats and the genuine 48-to-49 migration/backup check.
Four native screenshots were reviewed. The 239 parity rows and their remaining
UI/persistence/coverage requirements are preserved. Exact next task: **B01**.

## Reproducible measurement boundaries

Run `bash ci/native-test.sh` on a fresh disposable API 36 x86_64 emulator after the
pinned build steps in [android/README.md](../../../android/README.md). Networking is
turned off before installation. The existing five native functional tests run
first and retain their JUnit/raw reports. The performance class is excluded from
that invocation so their engine state cannot contaminate the measurements.

After AGP removes that installation, install the same debug app and test APKs:

1. Launch the actual app normally once with no installed game database, then four
   times after force-stop while retaining the verified database. No instrumentation
   runs inside these five app processes. Require a new PID for each launch and
   the expected database-copy flag. Delete each previous receipt before launching.
2. Measure from Android's process-start timestamp to the ready Compose draw.
   `ReportDrawnWhen` waits for the first calculated fit; the loading screen does
   not count as ready. The worker separately times its queue, database validation/
   copy, Python startup and module import/boot/first JSON snapshot. End that last
   phase when the snapshot is ready, before publishing UI state.
3. Retain the ADB request-to-receipt elapsed time and raw `am start -W` output.
   The former includes transport, writing the receipt and polling; the latter
   measures initial display, which may still show loading. Process-to-ready-draw
   excludes earlier system dispatch/zygote work and is not official launch-intent
   TTFD or tap-to-ready latency. OS disk/page caches are not cleared between runs.
4. Force-stop, then invoke the separate `PerformanceTest` once with `am instrument`.
   Require exactly one passing test and a fresh receipt from another PID. Launch
   the activity, wait for its complete startup receipt, then measure reusable fits.
5. Prepare and measure ammunition with one fit retained; add four projection fits
   and measure at five retained fits; add four command fits and measure at nine.
   Each graph contains a source, two linked identical recipients and an unlinked
   control. Earlier graphs remain alive. Commands include the active reference
   mindlink required by A05's harmonizing state.
6. For each operation, make four warmup edits and twenty measured edits, alternating
   both directions. Time Kotlin submission through parsed JSON: worker queue, JNI,
   mutation, refreshed EOS snapshots, Python serialization and Kotlin parsing.
   Compare all values and units against the unchanged desktop fixture after every
   call, outside its timed region. Keep the sample order, last actual snapshot for
   each state, direction-specific summaries and exact fit-count/link/pending-bonus
   assertions. No manual recipient refresh or expected value enters the app.

| Operation | One timed call | Statistics returned |
| --- | --- | --- |
| Ammunition | Change both Vexor guns between Iron and Antimatter | 38 on one fit |
| Projection range | Change both dampener links between 100 km and zero | 39 on each of four fits |
| Projection links | Remove or reapply both dampener links | 39 on each of four fits |
| Command charge | Change source between Shield Harmonizing and Extension | 39 on each of four fits |
| Command links | Remove or reapply both command links | 39 on each of four fits |

Memory uses `Debug.getMemoryInfo` PSS and private dirty kB; separate Java/native
allocation counters retain byte units. Normal-startup and instrumented memory
are reported separately. These are current process snapshots, not peaks, a leak
test, Python-only memory or isolated per-fit costs. Protected graphics allocations
may be omitted. Instrumented snapshots include the runner, assertions and reports.
No forced collection is performed. Fit counts must remain fixed within each stage.

These are debug/emulator feasibility measurements. Twenty edit samples provide an
observed median/p95/min/max, not a reliable estimate of phone tail latency. Four
subsequent startups are too few for a startup percentile claim. No warm/hot activity
launch, device reboot, physical ARM64, older Android, competing edit queue, large
fleet, graph rendering, long session or optimized release build is measured here.
Do not add an arbitrary speed threshold after seeing results.

## Correctness issue found by the longer benchmark

The interleaved host run exposed a source-module lifetime issue in the adapter's
relationship operations. SQLAlchemy `refresh(source)` can expire and reload its
module relationship, discarding calculated in-memory module attributes while the
fit still reports itself calculated. After ammunition edits, adding a projection
could leave the Celestis railgun's cycle/capacitor/CPU/damage values unmodified.
A short run that happened to retain the module objects did not expose it.

A10 adds source recalculation immediately after all four add/remove relationship
refreshes. Two forced-collection regressions fail on the previous adapter and pass
with the correction; all 29 headless tests and 123 interleaved benchmark snapshots
pass on the host. Android and independent Windows desktop CI also pass with the correction. Retaining hidden
benchmark references, disabling garbage collection or relaxing the fixture would
hide the issue. EOS formulas and the independent fixtures must stay unchanged.

## Source and dependency controls

The desktop source, source-data/logical database hashes and A01/A04/A05 fixture
hashes remain pinned and independent. `verify-apk.py` checks the actual database,
all staged EOS/adapter sources and every mobile Python source against the APK,
keeps expected values out of the app, and verifies native dependency closure for
arm64-v8a and x86_64. The APK byte count and SHA identify this build.

Keep the [working toolchain and six Python wheel pins](../../../android/README.md#toolchain):
Chaquopy 17.0.0 / Python 3.11, Logbook 1.7.0.post0, SQLAlchemy 1.4.50 pure Python,
Android Greenlet 3.0.1 build 1 and chaquopy-libcxx 180000 build 0. Desktop Greenlet
remains 3.0.3. Broader version compatibility is not inferred from these pins.

## Primary measurement references

Checked 2026-09-17:

- [Process start clock](https://developer.android.com/reference/android/os/Process#getStartElapsedRealtime()): API 24 timestamp before application code.
- [Ready UI reporting](https://developer.android.com/topic/performance/vitals/launch-time): initial display versus fully drawn state and Compose reporting.
- [Current-process memory](https://developer.android.com/reference/android/os/Debug#getMemoryInfo(android.os.Debug.MemoryInfo)) and [PSS/private-dirty units](https://developer.android.com/reference/android/os/Debug.MemoryInfo).
- [Instrumentation process lifecycle](https://source.android.com/docs/core/tests/development/instrumentation): the runner executes inside a restarted app process.
- [Runner class filters](https://developer.android.com/reference/androidx/test/runner/AndroidJUnitRunner) and [ADB test-APK installation](https://developer.android.com/tools/adb#move).
