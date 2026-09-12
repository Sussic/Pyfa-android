# Android project status

Updated: 2026-09-12.

## Verified baseline

- Personal fork: <https://github.com/Sussic/Pyfa-android>, default branch `master`.
- Starting source: `8b04f3b271e614b3e103853b44a7851a63d79d0e`.
  This matched upstream master on 2026-09-12. It includes changes after the latest
  release, `v2.68.0`; do not substitute that release binary as an exact oracle.
- Baseline tree: `8db82315f8312b124dd24ef103e43496cee50b4a`.
- No existing Android project, Gradle wrapper, GitHub Actions workflow or AGENTS
  file was present in the starting tree. Upstream desktop AppVeyor config exists.
- Upstream CONTRIBUTING recommends Python 3.11. Desktop requirements include
  wxPython. `service/fit.py` imports wx, while EOS has configurable database paths.
- Legacy `tox.ini` references absent `requirements_test.txt` and `tests2/`.
  Some tests in `tests/test_modules/test_eos/test_saveddata/test_fit_2.py` return
  before exercising calculations. The inherited suite is not a verified oracle.

## Completed

- Documentation setup: root agent instructions, agreed scope, initial feature
  families, provisional architecture, task queue, first-task brief, development
  evidence rules, and task/PR templates.
- Setup validation: whitespace, local link targets, task IDs/dependencies and
  feature-family coverage checked before committing. No runtime code changed.

## Current work

- No implementation task is active.
- Next ready task: **A01 — establish a reproducible desktop reference**.
  Read [its brief](tasks/A01-desktop-reference.md), then the relevant source only.
- [ROADMAP.md](ROADMAP.md) is the authoritative task-state list. The feature matrix
  in [SCOPE.md](SCOPE.md) tracks coverage, not duplicate task progress.

## Open technical questions

- Can this EOS plus required Python/native packages run on arm64 Android and an
  x86_64 emulator with the same calculation behavior? A03 and A07–A09 establish it.
- Can projections/commands recalculate within practical phone latency and memory?
  Measure in A10 before expanding the interface.
- Working desktop test commands, Android SDK/toolchain pins, game-data digest and
  real-device performance evidence are not established yet.
- The user's exact phone model/API level has not been explicitly confirmed in this
  project. It does not block host work or an emulator-based feasibility build.

## Resume instruction

Read AGENTS.md and this file, verify live master and relevant open PRs, and complete
A01 with its focused checks. Keep full offline Pyfa parity as the destination.
Do not jump into the entire app, restart settled research or treat the setup
documentation as evidence that an APK has been built.
