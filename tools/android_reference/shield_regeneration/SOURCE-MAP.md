# G04 original source map

All references below are to the retained original source root from `test-env.sh`.
Extracted AST bodies and imported EOS modules must byte-match the candidate's
unchanged upstream files, and receipts bind both by SHA-256. No candidate graph
or Android calculation module supplies expected results.

- `graphs/data/fitShieldRegen/graph.py`: complete FitShieldRegenGraph, including
  raw/effective selectors, percentage X only, three inputs, source column names,
  normalizer/limiter/getter/denormalizer tables. The sole GUI shim supplies current
  `showEffective`; all definitions and calculations execute original bodies.
- `graphs/data/base/graph.py`: complete FitGraph; full getPlotPoints/_calcPlotPoints
  range workflow and original zero-capacity percentage fallback. A fresh graph
  per fit/request avoids desktop cache assumptions without changing calculations.
  Recording normalized/limited inputs calls the same original methods separately.
  `_calcPoint`/x marks do not clamp X; those shared actions belong to G11.
- `graphs/data/base/defs.py`: unchanged Input/XDef/YDef classes and mappings.
- `graphs/data/base/getter.py`: unchanged PointGetter and SmoothPointGetter,
  200 intervals and zero refinement; `_xIterLinear` min/max sorting, underflow
  singleton and repeated rounding coordinates are retained.
- `graphs/data/fitShieldRegen/getter.py`: complete four getter classes and two
  closed-form helpers; no reimplementation. Shield amount→amount is supported.
- `gui/builtinViewColumns/attributeDisplayGraph.py`: original ShieldAmountColumn
  and ShieldTimeColumn `_getValue`; raw capacity HP, recharge milliseconds/1000 s.
- `eos/saveddata/damagePattern.py`: imported original effectivify for real fits;
  exact extracted method for scalar helper cases. Damage components retain original
  order and zero-total/zero-divider fallback; no invented percent normalization.
- `eos/utils/float.py`: exact floatUnerr with original seven-digit constant context,
  used by original base fallback; production sources are unmodified.
- `graphs/gui/ctrlPanel.py:300-315,512-543` and `gui/utils/inputs.py`: actual control
  wiring and original parser classes. No negative typed endpoint assumption.
- `tools/android_reference/fixtures/defenses.json`: all14 retained defense specs;
  numerical expectations in that file are not reused as graph expected results.
- `tools/android_reference/multisource/oracle.py`: unchanged read-only DB bootstrap,
  original service/command AST extraction, original item lookup and fit creation.
  Its GUI/Market shims do not perform calculations. Namespace guards prevent
  android_bridge/mobile_runtime imports and a socket audit blocks network access.
- `service/fit.py`, `gui/fitCommands/helpers.py`, local-module change-state
  command classes and `eos/saveddata/{fit,module,character}.py`: actual
  recalc, fill, state/history and character APIs. All loaded/transitive original
  files are receipt-bound, even inherited command families not exercised here.

Source preflight uses original LOCAL recalc and forbids CapSimulator.reset/run,
cap/tank/drain APIs and cycle iterators. This independently qualifies the source
path only. Candidate preparation keeps its own existing admission semantics and
must be separately measured; no universal no-reset claim follows from this file.
