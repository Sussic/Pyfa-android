# W02 — Complete Windows local verification

Selected 2026-10-01. The current goal ends at verified setup delivery; stop afterward.
Branch `codex/windows-local-verification` starts at `e916e054`; existing feature
work remains intact. Deliver a focused setup PR into the B09.1 branch, then stop.
The active setup-only goal requires later explicit authorisation before feature
delivery or roadmap continuation. No feature task is removed.

## Outcome and acceptance

- [x] Reuse installed JDK17, SDK, separate Python environments and Gradle wrapper;
  verify WHPX and prepare a disposable API36 Google APIs x86_64 emulator.
- [x] Run every desktop/reference and host check locally, then both APK builds,
  lint, signature and full package/ABI inspection without concurrent timed suites.
- [x] Port the Linux launcher while preserving every native execution, fresh
  offline installation, all assertions, process boundaries, raw-result validators
  and required screenshots. Run the complete suite on Windows and review images.
- [x] Retain local full logs, APKs, screenshots and raw results tied to the exact
  clean tested commit, source/data/tool identities and emulator identity.
- [x] Provide repeatable focused and complete commands, safe explicit pause/resume
  at verified boundaries, and truthful local result reporting. Never label an
  unexecuted Actions check as passed; preserve coverage when changing gates.
- [x] Demonstrate the local replacement before retiring hosted checks; prepare
  any access-dependent repository change and its exact remaining owner action.
- [x] Update existing instructions, review, commit/push/merge the setup PR after
  applicable checks, record B09.1 delivery and B09.2 as subsequent work, then stop.

No unattended self-hosted runner on the public repository, CPU/RAM caps, paid
service, alternative CI platform, release, phone installation or billing change.
Shared SDK packages may be reused; the test AVD and app data are disposable.
Report remaining hosted work, possible charges and exact start/pause/resume steps.

## Verified execution and retained failures

Full local verification passed 78/78 gates: 48 independent reference/host,
five build/package and 25 native including the aggregate summary. The 53 host/build
gates retain `f7d2ad31`; 24 native execution gates retain `6792b03e`; the final
summary executed at `5952c1bf` in 2.156 seconds. All 77 reused records and original
attempts are unchanged. Fifty-two instrumentation executions passed. All 125
required screenshots plus one clearly labelled failure diagnostic were reviewed.
See the [receipt](../evidence/w02-local.json) for exact commits, APK/log hashes,
source/data/tool identities and the retained local evidence path.

The original UTP gRPC/readiness failures and 900-second history failure remain
recorded. The user approved Windows-only 2400-second prepare/restored deadlines;
Linux remains 900. The single diagnostic retry passed history (prepare 1903.248s,
restored 181.903s; gate 2146.218s). Case 14 was visible at 988.875s and case 15 at
1080.828s, with the same process CPU increasing 17:19 to 18:56 and valid supplemental
database modification timestamps advancing 80 seconds. Original diagnostic stat
format errors remain preserved; the tested colon format is used for future runs.
All functional assertions, numerical tolerances, operation limits, restart checks,
screenshots and A10 requirements remain unchanged.

Three aggregate failures are retained: attempt 109 missing package report (9.25s),
110 contract normalized-hash mismatch (0.36s), and 111 persistence normalized-hash
mismatch (0.422s). The archived `apk-contents.json` was verified against the original
build/run, retained/build APKs, database/source/library bytes, actual ELF dependencies
and native engine reports, then restored byte-for-byte. Native restart now preserves
package/lint evidence. Completed runs reject resume before any mutation.

The authorized correction inspected every final-summary validator. Only contract
and persistence contained the confirmed fixture-hash assumption. Both now require
reported SHA256 to equal exact fixture bytes from the retained verified test APK,
and those bytes to equal the correct reference after CRLF-to-LF normalization only.
Persistence retains its manifest/report equality checks. No data, APK or reported
hash was changed. Fourteen focused regressions accept LF/CRLF equivalents and reject
wrong hashes, missing fixtures, content/other whitespace changes even with updated
matching hashes, manifest inconsistencies and unrelated verifier edits. Twelve
routing/control tests and 20 reporting/parser tests also passed. Whole-source
comparison permits only exact authorized deltas. No completed stage was replayed
for summary recovery; attempt 112 passed.

## Delivery boundary

The demonstrated replacement permits retirement of automatic hosted PR triggers
on this stacked setup/B09.1 branch. Manual hosted fallback retains all job bodies,
pins, permissions, timeouts, concurrency, one-day diagnostics and deliberate APK
uploads. Default master retains prior policy until PR #33 is separately delivered.
No protection/ruleset access blocker was found. Instructions and repeatable
[start/pause/resume/report commands](../LOCAL-VERIFICATION.md) are updated.
[Setup PR #34](https://github.com/Sussic/Pyfa-android/pull/34) merged into
`codex/b09-1-edit-history` as `3a33bfbe`, from reviewed head `7cc25ba2`.
Its exact head had a passing `local/full-verification` result. Setup is delivered;
STATUS and the Windows checkpoint are updated. Stop here.
PR #33 feature delivery and B09.2 require a later explicit instruction.
