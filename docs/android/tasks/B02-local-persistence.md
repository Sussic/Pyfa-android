# B02 — local fit persistence

## Outcome and acceptance

Save the committed fit graph on the phone and reopen it after process death with
the same fit identities, revisions, inputs and projection/command relationships.
Recalculate through EOS and compare the results with the independent A01/A04/A05
references. No PC, account, network or first-launch download is required.

Acceptance includes fresh host processes and three separate Android processes,
with app data retained between launches. Tests cover active/inactive links, source
edits affecting two recipients, an unlinked control, relationship removal, grouped
ammunition, skill overrides, implants and drones. Existing host, native parity,
typed-contract and performance gates remain required.

## Storage boundary

EOS retains its private in-memory session and B01 recovery rules. A separate
SQLite database stores one versioned declarative graph: ordered fit records,
stable IDs/revisions, the sample ID, logical dataset identity and EOS settings.
Calculated statistics and process session IDs are never saved. Startup validates
the store, reconstructs EOS and recalculates every fit before publishing results.
An invalid or incompatible existing store fails visibly and is not reset.

An edit prepares its response and graph, commits transient EOS, then commits the
whole durable graph in one SQLite transaction before publication. A generation
check rejects stale writers. If a commit raises after possibly succeeding, a fresh
connection must confirm the old or candidate graph. Confirmed old data permits
B01 recovery and a save error; confirmed new data permits success. An unknown
outcome stops the session until restart. Never publish an older graph while newer
data may already be committed.

Initial installation builds a complete temporary database first. On POSIX,
including Android, a permanent sibling lock coordinates all app-private creators;
under that lock, an existing destination is refused before atomic rename. Windows
rename already refuses an existing destination. The lock inode is never deleted,
and process death releases the operating-system lock. Android prohibits app hard
links, so initial installation does not use them. This protocol coordinates this
app's writers; other code must not write directly into the private store directory.

Production uses app-private `noBackupFilesDir/fits/graph.sqlite3`, excluded from
Android automatic backup/transfer. Existing direct-engine diagnostic probes run
in explicitly ephemeral processes; they cannot mutate a user's saved graph.
The B02 native phases use normal production storage without uninstalling or
clearing app data between phases.

## Limits

This task persists the existing adapter/39-field bridge capabilities. The fit
library and complete editing/statistics remain B03 and later tasks; all 239 parity
rows remain. Schema/dataset/settings mismatches fail closed. Dataset migration,
user backup/restore and install-over-upgrade verification belong to I05 and R02.
Stable release signing and physical/ARM64/older-API execution remain unverified.

## Validation and delivery

Delivered in [PR #12](https://github.com/Sussic/Pyfa-android/pull/12), merged as
`9d96e0d8e8fc0fcb0a6a03023fb7cfe1a8ed8238`. Tested head: `225d0d15d8195e148aca5233c88b8b3a57086495`;
tree: `1790d1fae40ab21c78fb5e67cde50275887c5575`. The [durable receipt](../evidence/b02-native.json)
retains the actual CI checkout, complete native values, process/session identities,
request/response pairs, host checks and packaging provenance.

[Android CI](https://github.com/Sussic/Pyfa-android/actions/runs/35389186247) passes build, lint, signing and actual APK/source/data/ABI
inspection. All ten native test executions pass: the original five, separate A10
performance and B01 contract tests, and three B02 phases with app data retained.
Nine fits survive both restarts with unchanged IDs/revisions and newly assigned
process session IDs. The 45 B02 snapshots match 39 raw desktop statistics and units
each, including strict scalar types. Active/inactive projections and commands,
two-recipient source edits, link removal, unlinked controls, grouped ammunition,
skill override removal, an active mindlink, Unicode fit names and drones persist.

[Windows CI](https://github.com/Sussic/Pyfa-android/actions/runs/35389186269) passes 65 host tests: 29 engine regressions, 14 contract
tests, 14 persistence tests and eight reference utilities. All independent desktop
references and the real migration/backup check pass. Local Linux checks pass the
same 65 tests and a three-process mobile-runtime save/reopen/isolation check.
The new fault tests cover commit interruption, ambiguous acknowledgement,
confirmed-save publication failure, stale writers, interrupted initialization and
preservation of twelve invalid/incompatible store variants. These tests terminate
host processes and inject errors; physical power-loss behavior is not claimed.

The first Android attempt passed the five existing functional tests but could not
create the production store. Its initial-install hard link is prohibited by
[Android app policy](https://android.googlesource.com/platform/system/sepolicy/+/android16-release/private/app_neverallows.te).
Replacing it with the locked rename protocol resolved that incompatibility; three
new tests protect simultaneous creation and death before/after installation.
The failed attempt and its disposition remain in the receipt. No required check
was weakened or removed.

The Android store generations are 1 → 15 → 25 → 25 across preparation,
reopen/edit and final verification. The earlier diagnostic suites leave the
one-sample production store untouched. No EOS formula, independent fixture or
parity inventory row changed. A10 edit timings continue to measure ephemeral
engine operations and exclude durable-save latency.

Debug APK: 70,443,139 bytes, SHA-256
`df47b594d77638f87cec59d20073fa0cf5ba7d61d7ebf84d3cb5091a72697190`. Version 0.1.0-b02 / code 7. Native execution is verified
only on API 36 x86_64; ARM64 contents are verified but execution is not. Artifact
retention remains one day and APK delivery is manual opt-in. B03 is the exact next
task; this implementation is not full Pyfa parity or usability sign-off.
