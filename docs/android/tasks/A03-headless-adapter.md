# A03 — minimal headless adapter

Dependency: A01. Outcome: the same fitted ship and reversible ammunition edit
calculate without desktop/UI initialization, using unchanged EOS formulas.

## Acceptance

- Configure the explicit game-data path and in-memory saved-data path before EOS
  database imports; never touch personal data or download data during calculation.
- Independently implement the minimal fit/charge/sample boundary and match A01's
  38 statistics, three states, item IDs, settings and game-data identity.
- Prove wx, gui, service and root desktop config are neither imported nor mocked;
  run in a separate environment with only required pinned host packages.
- Reject unsupported scenario inputs and invalid bulk edits without partial
  modification. Verify fresh-process initialization and restored values.
- Preserve desktop migration backup behavior with a meaningful regression check.
- Document dependencies, import order, data paths, supported API and unverified
  capabilities. Obtain required host CI before delivery; do not claim Android.

## Implementation and evidence

- [Adapter boundary and compatibility change](../../../android_bridge/README.md).
- [Commands, tests and CI](../../../tools/android_headless/README.md).
- Local Linux: ten headless tests plus the repeated scenario passed; real desktop
  schema-48-to-49 migration preserved backup bytes and user row, then became a no-op.
- Windows CI is pending. A01's expected values, tolerances and exporter are unchanged.

Next task after verified delivery: **A04 — projected-effect reference cases**.
