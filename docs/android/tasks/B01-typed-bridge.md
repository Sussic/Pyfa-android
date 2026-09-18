# B01 — typed bridge operations and results

## Outcome and acceptance

Use one versioned request/response contract between Kotlin and Python. Preserve
EOS's raw values and units, give each fit a stable logical handle and revision,
serialize engine work off the Android UI thread, and leave the committed graph
intact when any stage of an edit fails. A10 selected the existing embedded EOS
approach; B01 does not replace formulas, broaden the statistics inventory or add
persistent storage.

Acceptance requires strict protocol/type checks, bulk-edit rejection, revision
conflicts and downstream invalidation, recovery after real mutations fail, and
native Kotlin-to-Python comparisons with the independent A01/A04/A05 fixtures.
The five existing native functional tests and separate A10 performance invocation
remain gates, along with the host references and source-refresh regressions.

## Contract version 1

`BridgeContract.kt` defines the Kotlin DTOs, sealed operations and strict codec.
`android_bridge/contract.py` owns dispatch and the committed graph. JSON is the
transport format; the app receives typed snapshots and structured errors.

Requests contain exactly `version`, `request_id`, `session_id`, `operation`,
`expected_revisions` and `arguments`. Unknown/duplicate/missing fields, malformed
JSON, wrong scalar types and nonfinite numbers are rejected. Request and session
identifiers are opaque, nonempty strings of at most 128 characters. The runtime
checks response correlation on its single worker. EOS/SQL identifiers are never
used as public fit handles.

| Operation | Arguments |
| --- | --- |
| `snapshot` | `fit_ids` (empty selects all; otherwise requested order) |
| `create_fit` | `spec` |
| `set_charges` | `fit_id`, `module_indices`, nullable `charge` |
| `set_module_states` | `fit_id`, `module_indices`, `state` |
| `set_skill_level` | `fit_id`, `skill`, `level` |
| `add_implant` | `fit_id`, `implant`, `active` |
| `set_implant_active` | `fit_id`, `slot`, `active` |
| `remove_implant` | `fit_id`, `slot` |
| `add_projection`, `configure_projection` | `source_id`, `target_id`, nullable `range_m`, `active`, `amount` |
| `remove_projection` | `source_id`, `target_id` |
| `add_command`, `set_command_active` | `source_id`, `target_id`, `active` |
| `remove_command` | `source_id`, `target_id` |

The initial fit specification models the existing adapter's supported fields:
name, hull, default skill level, reload factor, damage pattern, system/pilot
security, modules and drones. Unsupported base specification fields retain their
explicit null/empty values and fail if populated. Later tasks extend this contract
alongside their own reference cases.

Successful responses contain snapshots and a null error; failures contain an
empty snapshot list and `{code, message}`. Error codes distinguish invalid wire
requests, unsupported versions/operations, unknown fits, revision conflicts,
invalid edits, recovered engine failures and unavailable engines. Tracebacks are
not user error messages. The UI retains its last valid fit when an edit fails.

Each snapshot contains logical ID, revision, name, hull, raw statistics, modules,
actual skill overrides, implants and incoming projection/command links. Stat
values retain integer, decimal, boolean and text types; units are explicit. A
prerequisite edit can leave a dependent skill unset, represented as null rather
than a fabricated zero.

This version carries the **39-field sample view** already covered by the A04/A05
oracles. It requires at least one fitted module because that view includes the
first module's weapon attributes. Moduleless fit creation is explicitly rejected;
complete fit/statistic views remain C01–C03. No parity inventory row is removed or
marked complete merely because a transport exists.

## Revisions and publication

Creation starts at revision 1. Reads and rejected/failed edits leave revisions
unchanged. A successful mutation advances its named fit or source/target endpoints
and all transitive recipients across projection and command links. The dependency
set is the union of the graph before and after the edit, including inactive links;
former recipients therefore receive removal updates. Unrelated fits keep their
revisions. A successful no-op edit may advance revisions under the same rule.

Mutations require exactly the current revisions of their named endpoints.
Snapshot/create requests require an empty revision map. A different engine session
or stale revision fails before editing. An affected response is published as one
unit in registration order, after all affected snapshots are calculated and
serialized and the SQL transaction commits.

## Failure recovery

SQL rollback alone cannot undo EOS's mutable Python object graph. Charges,
calculated attributes and active skill levels can remain changed even when mapped
database fields are rolled back. Copying a Fit also shares mutable character and
relationship state, so it is not a transaction checkpoint.

The bridge keeps a declarative record of its last committed graph. Normal edits
reuse existing EOS objects. Only on failure after mutation begins does it roll back
and rebuild that graph, preserving logical handles, revisions and committed
snapshots. Recovery retains the existing in-memory SQLAlchemy session, clears its
object references and the saved-data cache dictionaries in place, and recreates
fits, actual skill levels, implants and links. It does not touch the read-only game
database or its caches. Replaying committed dependent skill nulls bypasses only the
prerequisite cascade already validated when that checkpoint was created.

The bridge exclusively owns the transient session. If recovery itself fails, the
session becomes unavailable and rejects further reads/edits. It never returns a
partially restored fit as valid. Persistence and recovery across process death
remain B02; version 1 session IDs intentionally change after restart.

Existing legacy parity and performance probes remain diagnostic paths with their
original comparison boundaries. The new contract suite runs in a separate fresh
process. It does not share an engine graph with those probes.

## Validation and delivery

Local validation passes 14 focused B01 contract tests, all 29 existing headless
cases and eight independent-reference utilities. A mobile runtime harness adopts
the sample, injects a failure after a real ammunition edit, verifies recovery and
then compares all three benchmark setups plus 120 edit snapshots with the
independent fixtures. Steady fit counts remain 1/5/9 and the game database is
unchanged. Two independent source reviews found no remaining blocker after fixes
for ORM integer module states, terminal transport faults and nullable ammunition.

Native build/emulator and Windows CI evidence are pending. Record their actual
runs and retained receipt here before marking B01 done.

Physical phones, ARM64 execution, older Android APIs, persistence, the fit library
and full Pyfa statistics/editing remain unverified or assigned to later tasks.
