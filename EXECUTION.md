# Pyfa execution and delivery

Read `execution-policy.json` before setup, generated writes, builds or validation.
It is the sole current source for Pyfa's RAM estimates/reserves, CPU concurrency,
storage threshold and deadlines on Initia and MSI. This policy supersedes older
machine budgets and runner prohibitions in handoffs, STATUS history and receipts.
Changing a resource setting means editing that file and validating the loader;
launch arguments and old run state cannot restore a different numeric policy.
Historical results keep their as-run policy and never authorize a future launch.

## Develop while validation waits

Initia holds the primary working copy. Continue independent implementation,
refactoring, documentation, fixtures, test authoring and cheap static checks while
an environment, heavy slot or MSI job is unavailable. Use small coherent changes,
stable interfaces, dependency injection and fakes at real seams. A missing test
result blocks only work depending on that result. Resource admission applies to
commands that consume resources, rather than editing or source inspection.

Maintain the compact pending-validation ledger under the policy's results root.
Each entry names the source snapshot, command/test selection, required capability,
queued job or issue, status and what remains unverified. Keep frozen queued inputs
separate from the moving development branch. Focused checks support iteration;
the relevant broad, native/offline/restart and usability checks still gate claims
of verification or delivery. A queued, skipped or unavailable test is pending.
Investigate a failed check before retrying; reuse valid unchanged proof.

## Run and store work

Use Initia for its environment installation, small admitted host checks and
interactive Windows, GUI or physical-device checks. Prefer MSI for compatible
heavy builds, broad/repeated suites and emulator work after verifying the needed
SDK, virtualization, image and device capabilities. Native evidence identifies
the actual host/device and source. Capability shortages keep that job queued.

`android/verify-local.ps1` loads the policy through `android/ci/local_verification.py`.
The launcher records policy identity, admits physical RAM and commit together,
uses the shared physical-host heavy lock and monitors sustained memory pressure.
All projects share that lock; actual admission also includes memory used by API
work and other applications. CPU concurrency comes from the policy, clamped to
available processors. Workload estimates are admission estimates, not process
commit caps. Stop/requeue only the owned job under real sustained pressure.

Use the policy's `locations` for scratch, environments, caches and results.
MSI jobs use isolated per-job checkouts. Existing source and frozen migration
evidence stay in place. Standard ignored Gradle build directories remain the
repository-generated outputs named in the policy and are included in accounting. The artifact ledger counts checkouts, environments,
caches and evidence by resolved ownership without counting shared tools twice.
Project consumption exceeding the JSON threshold requires the owner's storage
decision; routine storage below it does not. Physical free-disk admission includes
the next operation's forecast. Preserve failed evidence and unrelated processes.

Keep SDKs, virtual environments, AVD/Docker data, credentials, personal fit stores,
bulk logs and reproducible build outputs out of Git. Never substitute personal
saved-fit data for the pinned synthetic dataset. SDK/JDK/reference overrides select
existing qualified installations; they do not alter resource policy.

## GitHub and MSI queue

Use `Sussic/Pyfa-android`, a scoped task/WIP branch and reviewable commits. Push a
coherent source/policy/checkpoint before offloading work or leaving it for another
host. WIP can be pushed with explicit pending or failed validation. Preserve
unrelated dirty/staged paths, avoid force-push, and keep default-branch merge,
release and deployment decisions separate. Large reproducible artifacts belong
in suitable Actions artifacts/releases, rather than Git history.

MSI availability is optional. Queue durable descriptors in GitHub issues on the
policy's coordinator repository; a queued Actions run is not the durable queue.
The existing MSI registration belongs to the coordinator repository, not this
Pyfa repository. Use the shared queue worker and the policy-guarded Pyfa launcher.
An unavailable MSI is pending, not a failure or a reason to stop implementation;
never silently move a queued MSI job to Initia.

Queue exact inner commands such as a selected Python unittest invocation or the
Gradle wrapper with policy worker settings. The shared worker wraps those commands
with `scripts/run_project_job.py`; the local verification launcher already holds
its own host lease and must not be nested inside another policy wrapper.

A queue descriptor binds project `pyfa`, source repository and full immutable
commit SHA, exact argv vector, workload profile, `policy_path`, policy SHA256,
required capabilities, estimated disk writes and an idempotency key. Include
the intended dirty changes in that commit. Until that snapshot exists, record
`awaiting_snapshot`; testing an older HEAD is not validation of dirty source.
Retain truthful queued, blocked-capability, running and terminal evidence states.

## Pyfa boundaries and handoff

C10's external candidate remains separate until its own reviewed integration.
Do not overlay it while updating setup/policy. Preserve reference/data identities
and every product assertion; host checks never become Android acceptance.

At a meaningful checkpoint, update STATUS and the selected ROADMAP row with the
implemented outcome, source/branch, actual checks, pending-validation ledger and
next ready implementation work. Live handoffs link this document and the policy;
they do not copy resource numbers. Dated receipts and old machine rules remain
historical. Access/security restrictions, ownership-safe cleanup and product
acceptance remain effective; this policy authorizes no privilege bypass.
