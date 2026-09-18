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

Implementation and required checks are in progress. No B02 native result is
claimed until the exact PR head passes CI and the raw receipt is retained.
