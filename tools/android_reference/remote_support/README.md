# D02.2 original-only preflight

`cases.py` contains four finite three-fit schedules and fixture inputs only.
`preflight.py` imports the unchanged D02.1 original AST command plumbing, blocks
all adapter imports, loads original EOS with the retained read-only database, and
executes original commands/recalculation. It does not modify EOS or product code.

Data-only mode installs a fail-fast boundary before fit construction: capacitor
properties, tank properties, simulation helpers, and both simulator reset/run are
forbidden. It verifies original fitting restrictions plus CPU/PG/slot/hardpoint
resources, captures actual LOCAL extra/generated drains and all five repair-pair
lists, checks positive integer cycle denominators, and computes source-derived
conservative six-hour/one-hour event and saved-list work. The diagnostic is scoped
to the explicitly listed no-reload/non-injector fixtures. It is not a production
guard. Incoming drone/fighter admission is genuinely disabled for these graphs.

Measurement mode requires a separate successful reviewed capture receipt and exact
canonical source/data/harness/fixture/settings/input/stage binding. Each endpoint
is recalculated LOCAL and recaptured before observation. It permits at most one
original cap simulator call per numerical observation, checks measured iterations
and saved events against the source-derived bounds, and compares both endpoint
read orders. Measurement covers 39 snapshot fields, four complete tank dictionaries,
numeric capacitor details/stability/units, and four outgoing repair components.
It does not claim original desktop presentation or graph-curve parity.

Use the already provisioned environment, retained original source/database, one
serial EOS lane, timeout 180 seconds and one-GiB address space. Example from repo:

    source ../test-env.sh
    timeout 180 bash -c 'ulimit -v 1048576; exec python -I tools/android_reference/remote_support/preflight.py --source "$PYFA_REFERENCE_SOURCE" --database "$PYFA_DATABASE" --suite repair --output ../preflight-evidence/repair-capture.json'

Only after independent review, replay with `--measure` naming that exact capture
receipt and a fresh output path. Add `--reverse` for the repair and reciprocal
construction-order variants. Every output path is exclusive; preserve failures.
`test_preflight.py` has nine pure diagnostic/boundary tests with no EOS execution.
`verify.py` checks the final V4 receipts using JSON only, including causal witnesses,
source binding, completed cleanup and cross-construction parity.

The reviewed V4 capture/measurement evidence is outside the executable tree in the
candidate's `preflight-evidence/`. All six processes per mode cover 142 stages;
measurements contain 426 complete-fit records, 852 actual endpoint observations and
842 cap simulations. Peak measured iterations are 17,914, versus the maximum
22,865-event bound; peak process RSS is 90,700 KiB and elapsed time 8.25 seconds.
No unsafe ordinary case or product admission/formula/budget change was required.

Original profile nuance: after shared Shield Emission Systems 5→4→5, original
Character.setLevel materializes inactive Capital Shield Emission Systems and
Invulnerability Core Operation rows with activeLevel None. Evidence retains these
rows and the shared profile. Final reciprocal cleanup restores initial equipment,
edges and numerical results; it does not claim restoration of initial raw profile
identity. Other suite baselines restore complete recorded raw inputs and values.

The first capture serialization failure and the overstrict initial reciprocal
raw-profile checker assertion are retained. They are harness/evidence corrections,
not source safety failures. Reconstructed-source/supplemental-data qualification
limits remain. Candidate parity, transactions/restart, interleaving, desktop UI
formatting and native compilation/execution require their separate gates.
