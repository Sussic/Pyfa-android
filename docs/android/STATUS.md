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

## A01 completed and delivered

- [PR #1](https://github.com/Sussic/Pyfa-android/pull/1) merged as
  `675bb21e033de2c64d90a9bbf31e6111bfa64166` after successful Windows CI.
- [Passing run](https://github.com/Sussic/Pyfa-android/actions/runs/34691992984)
  tested code commit `8e6fa96b93985f5c78a3f4eb6b1cdf00d1f76b2c`.
- Eight focused tests passed on Linux and Windows. The same logical database and
  38 statistics in three states matched across both platforms. Independent Linux
  rebuilds and fresh processes also matched the committed fixture.
- [Reference commands and evidence](../../tools/android_reference/README.md).
  Windows CI exposed a SQLite handle cleanup error, now fixed with explicit closes;
  JSON is read as UTF-8. Expected numbers and tolerances were not loosened.
- An initial workspace database failed integrity; successful Linux builds used
  `/tmp`. Its cause remains unproven. Every reference build checks integrity.

## A02 completed and delivered

- Expanded the 23 scope families into [239 observable behavior rows](PARITY.md)
  with pinned source links, delivery owners, required checks and empty D/A evidence
  slots. Every Android behavior remains unimplemented.
- [Audit notes](PARITY_AUDIT.md) index 162 source surfaces and preserve nine
  unresolved investigation/disposition questions with explicit owners.
- Split four broad I tasks into 21 children. The roadmap now has 76 tracked rows:
  72 work items plus four parent rollups. A01 and A02 are done.
- Documentation validation covers IDs, source paths, owners/evidence slots,
  family/control/graph coverage, local links, acyclic task dependencies and
  whitespace. No runtime code, fixtures or workflows changed; no runtime tests run.
- [PR #2](https://github.com/Sussic/Pyfa-android/pull/2) merged as
  `53f36cad7937eebf3ff3e23c6664af8bc71591dd`; checked PR head
  `5704f0aa562bc4597e9e083b3b4d3feebea247b6` exactly matched the local validated tree.
  No Actions run was triggered for this documentation-only PR.

## Current work

- No implementation task is active. A02 is merged and its handover is complete.
- Next ready task: **A03 — minimal headless adapter**. Calculate the same A01
  synthetic fit without wx/UI initialization and compare the recorded raw values.
- [ROADMAP.md](ROADMAP.md) owns task state; [SCOPE.md](SCOPE.md) owns scope;
  [PARITY.md](PARITY.md) owns behavior-level coverage and evidence slots.

## Open technical questions

- Can this EOS plus required Python/native packages run on arm64 Android and an
  x86_64 emulator with the same calculation behavior? A03 and A07–A09 establish it.
- Can projections/commands recalculate within practical phone latency and memory?
  Measure in A10 before expanding the interface.
- Android SDK/toolchain pins and real-device performance evidence are not
  established yet. The host reference now has reproducible commands/data hashes.
- The user's exact phone model/API level has not been explicitly confirmed in this
  project. It does not block host work or an emulator-based feasibility build.

## Resume instruction

Read AGENTS.md and this file, verify live master and relevant open PRs, and select
A03. A01 is already verified and merged; A02 is the completed source audit. Keep
full offline Pyfa parity as the destination. Do not regenerate fixtures for a
documentation-only change.
Do not jump into the entire app, restart settled research or treat the setup
documentation as evidence that an APK has been built.
