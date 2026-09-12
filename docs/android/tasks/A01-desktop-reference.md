# A01 — establish a reproducible desktop reference

State is owned by [ROADMAP.md](../ROADMAP.md). Dependencies: none.

## Outcome

From a clean environment, run the pinned upstream calculation for one synthetic
fitted ship and capture meaningful raw statistics with enough provenance for later
Android comparison tests. This task establishes the reference, not the Android UI.

## Read first

- [STATUS.md](../STATUS.md), [DEVELOPMENT.md](../DEVELOPMENT.md).
- Root CONTRIBUTING.md, requirements.txt, db_update.py and scripts/compile_lang.py.
- eos/config.py, eos/db/__init__.py and the minimum fit-construction code needed.
- Legacy tests only to understand their setup gaps, not as presumed passing gates.

The reference commit is `8b04f3b271e614b3e103853b44a7851a63d79d0e`.
Use an isolated checkout/environment and disposable saved-data directory. The
current Android working tree must not generate both expected and actual results.

## Work

1. Establish Python 3.11 and document required system/display dependencies. Inspect
   imports before installing every desktop dependency in an unsuitable environment.
2. Generate the database from the source's bundled static data and translations as
   needed. Record the dataset identity/hash and command outputs relevant to success.
3. Create a synthetic fitted ship with actual modules/ammunition and explicit
   skills/settings. Select a representative drone-capable hull so drone control
   range can be recorded alongside CPU, powergrid, damage, capacitor and defenses.
4. Add a small reproducible reference-export command/harness and checked-in text
   fixture, recording raw units, source/data provenance and the exact input fit.
5. Exercise one meaningful edit (such as module state or ammunition) and show that
   the appropriate output changes and restores after reversal. Repeat from a fresh
   process to show the fixture is not accidental shared state.
6. Record working setup/export commands in DEVELOPMENT and update task/status.

## Acceptance

- A fresh process can reproduce the fixture using the documented commands.
- Values come from the pinned upstream engine with explicit inputs, not hard-coded
  guessed EVE statistics or the future mobile adapter.
- Fixture metadata identifies source commit, source-data hash, generated database
  hash, relevant settings and dependency/runtime versions. A binary database hash
  can differ due to serialization; explain it and verify logical data identity.
- Missing fixtures, skipped tests, early returns and GUI/display requirements are
  reported accurately. A successful import alone does not complete this task.
- No personal fits/tokens, generated database blobs or large runtime archives are
  committed. Keep generated data reproducible and disposable.

## Boundaries and blockers

Do not build Android screens, redesign EOS, rewrite every inherited test, fetch an
unversioned live dataset or repair unrelated desktop issues in A01. If this host
cannot run the reference, prepare a focused reproducible hosted-runner command
and obtain its evidence if authorized and available. If access/quota prevents it,
save the exact blocker and leave A01 blocked; do not invent expected numbers.

Next intended task after verification: A02, the detailed feature audit. A03 is
also dependency-ready then, but start only one task at a time by default.
