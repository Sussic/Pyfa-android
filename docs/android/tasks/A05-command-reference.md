# A05 — command-burst reference cases

Dependency: A03. Status: done and merged.

## Acceptance

- Generate the command source/recipient oracle using clean unmodified desktop EOS
  at the A01 pin, verified game data and genuine desktop dependencies.
- Record all raw values/units across source skill and implant changes, burst
  module and command-link states, charge changes, disabling and repeated removal.
- Compare the headless adapter with the independent fixture in fresh processes;
  reject desktop imports/network attempts and prove game data is unchanged.
- Verify all recipients update after source edits, independent links remain
  independent, invalid edits cause no partial changes, and removal restores the
  baseline without reverse relationships or pending command bonuses.
- Preserve A01/A03/A04 checks and desktop migration compatibility. Obtain Windows
  CI before merging and retain host evidence. Native command parity belongs to A09.

## Implementation and evidence

[Independent case, commands and evidence](../../../tools/android_reference/COMMANDS.md).
[Adapter methods and limits](../../../android_bridge/README.md).

The Vulture/Vexor case records 39 statistics per fit in 19 stages. Linux passes
nine new command tests plus the existing ten ammunition and eight projection
tests. Fresh processes match the desktop fixture, and disabled/removed sources
restore the recipient. No EOS formulas or A01/A04 expected values were changed.

[PR #5](https://github.com/Sussic/Pyfa-android/pull/5) merged as
`ac3eb238e2314b7afee08f5c1d8c5d8628fe44af` after the first
[Windows CI run](https://github.com/Sussic/Pyfa-android/actions/runs/34760339495)
passed for head `96d8d4749c9723f89f60b1cee66a551a2b7ece39`. Windows passed all
27 headless behavioral tests, eight reference utility checks, independent desktop
A01/A04/A05 references and the genuine desktop migration/backup regression.
Linux and Windows agree on normalized source/input/fixture and logical data hashes.
Retained evidence records the actual CI merge checkout separately from delivery.

Next task: **A06 — Android skeleton and native CI**.
