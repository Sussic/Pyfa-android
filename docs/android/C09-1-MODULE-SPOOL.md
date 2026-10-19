# C09.1 local module spool overrides and heat precision

## Integrated scope

A local-module spool screen exposes the original supported groups only:
Precursor Weapon and Mutadaptive Remote Armor Repairer. EOS supplies current,
default, minimum and maximum cycles and seconds; the original menu step-selection
algorithm supplies choices. Native code does not calculate spool multipliers,
cycles, times or repair/weapon output.

Selecting zero sets an explicit zero-cycle override. Reset clears both source
spool fields and uses the unchanged global default. The display distinguishes a
raw requested override from effective cycles: EOS can clamp the latter, while
saved inputs must retain the former across skill/profile/variation changes.
The menu always includes current effective cycles, and includes the default
choice under the original not-overridden rule.

Optional occupied-module `spool_cycles` is a strict nonnegative Int32. Old records
remain absent and reset omits the field. Capture/rebuild, ordinary edits,
variations, clones, profile changes, linked publication, undo/redo and restart
retain it. EOS maps its amount to a Float column, so capture canonicalizes only
exact integral finite ORM values; it never rounds fractional values. Unsupported
non-cycle live overrides fail explicitly instead of silently losing data.

The new `set_module_spool` ordinary operation uses existing revision checks and
atomic durable graph/history. Null means reset; invalid choices, empty or
unsupported modules and stale edits are rejected. Source query results must be
finite and nonnegative. A degenerate or pathological source range (maximum over
100,000 cycles) fails explicitly rather than inheriting the desktop zero-division
or allowing an unbounded menu loop. No values are fabricated or truncated.

EFT preview emits a specific spool-loss diagnostic, including for explicit zero.
EFT remains interchange rather than a backup.

Existing rack heat details now expose the full EOS cycle/time values and existing
sample probabilities, alongside rounded display. Samples represent heat-damage
probability at time t, not probability of already burning out. No new heat model
or simulation is introduced.

## Remaining C09 work and qualification

This slice does not close all C09 rows. Global reload and default spool settings
need separate durable settings design: desktop reload affects all loaded fits,
and current saved graphs pin EOS settings. A selected-fit-only switch would not
be exact desktop semantics. C09.2 adds the three local RAH inputs (fit pattern,
disabled adaptation, explicit built-in); named pattern management remains D05.
D01.2 implements individual projected-module spool override/reset through the
projected-module details and editor UI, including exact zero versus reset and
durable replay. See [D01.2](D01-2-PROJECTED-MODULES.md). Its device qualification
remains open; this does not add global spool defaults or projected RAH.

The C08 reviewed artifact remains frozen. New tests use the pinned logical game
data with reconstructed-source provenance, not a clean pinned Git claim. See
package receipts for actual host/reference/runtime/compiler checks. Device,
upgrade, usability and release qualification and the missing inspector fixtures
remain open; compilation does not imply Android execution.
