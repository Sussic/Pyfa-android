# B09.2 supported mutation dispositions

Selected from master 0685bb32 on 2026-10-02. This covers every current bridge
operation. Paths identify pinned source behavior to execute; static inspection
is not passing parity evidence. B09.1 already verifies local-module commands.
B09.2 must independently verify all remaining reversals, atomicity, restart and
native controls before delivery. Notes remain outside fitting command history.
Skills expose a direct desktop profile-input gap; Android already supports
fit-scoped overrides. Create/copy/delete are library boundaries; copies start
empty and deleted sources cannot be revived by stale recipient history.

Linked-effect history belongs to the recipient, matching original GUI/calc
commands and Android graph storage. Compound fitted/cargo transfers remain one
action. Addition variations include every supported module/drone/implant context;
future contexts need independent and native cases. EOS owns all calculations.

| Operation | History disposition | Owner | Pinned boundary | Verification disposition |
| --- | --- | --- | --- | --- |
| `snapshot` | query | lifecycle/query disposition | `service/fit.py` | library/query/cursor boundary |
| `create_fit` | new fit has empty history | lifecycle/query disposition | `service/fit.py` | library/query/cursor boundary |
| `rename_fit` | session action | fit (`fit_id`) | `gui/fitCommands/gui/fitRename.py` | original command; independent reversal comparison pending |
| `duplicate_fit` | copy has empty history | lifecycle/query disposition | `service/fit.py` | library/query/cursor boundary |
| `set_notes` | direct note write | lifecycle/query disposition | `service/fit.py` | direct notes write, preserved through fitting undo |
| `undo` | move cursor | lifecycle/query disposition | `service/fit.py` | library/query/cursor boundary |
| `redo` | move cursor | lifecycle/query disposition | `service/fit.py` | library/query/cursor boundary |
| `delete_fit` | prune fit and invalid references | lifecycle/query disposition | `service/fit.py` | library/query/cursor boundary |
| `add_module` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `replace_module` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `remove_module` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `add_cargo` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `set_cargo_quantity` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `remove_cargo` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `set_cargo_quantities` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `remove_cargos` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `add_cargo_preset` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `fill_cargo` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `change_cargo_variations` | session action | fit (`fit_id`) | `gui/fitCommands/gui/cargo/` | original command; independent reversal comparison pending |
| `transfer_cargo` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModuleCargo/` | original command; independent reversal comparison pending |
| `set_fit_restrictions` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `change_mode` | session action | fit (`fit_id`) | `gui/fitCommands/gui/shipModeChange.py` | original command; independent reversal comparison pending |
| `set_subsystem` | session action | fit (`fit_id`) | `gui/fitCommands/calc/module/localAdd.py` | original command; independent reversal comparison pending |
| `set_charges` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `set_module_charge` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `set_bulk_charges` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `set_bulk_states` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `fill_modules_item` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `fill_modules_clone` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `clone_selected_modules` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `clone_module_at` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `change_variation` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `change_bulk_variations` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `remove_bulk_modules` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `swap_modules` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `set_module_states` | session action | fit (`fit_id`) | `gui/fitCommands/gui/localModule/` | original command; independent reversal comparison pending |
| `set_skill_level` | session action | fit (`fit_id`) | `eos/saveddata/character.py` | original activeLevel input; direct profile edit gap, fit-scoped reversible override |
| `add_implant` | session action | fit (`fit_id`) | `gui/fitCommands/gui/implant/add.py` | original command; independent reversal comparison pending |
| `set_implant_active` | session action | fit (`fit_id`) | `gui/fitCommands/gui/implant/toggleStates.py` | original command; independent reversal comparison pending |
| `remove_implant` | session action | fit (`fit_id`) | `gui/fitCommands/gui/implant/remove.py` | original command; independent reversal comparison pending |
| `add_projection` | session action | recipient (`target_id`) | `gui/fitCommands/calc/projectedFit/` | original command; independent reversal comparison pending |
| `configure_projection` | session action | recipient (`target_id`) | `gui/fitCommands/calc/projectedFit/` | original command; independent reversal comparison pending |
| `remove_projection` | session action | recipient (`target_id`) | `gui/fitCommands/calc/projectedFit/` | original command; independent reversal comparison pending |
| `add_command` | session action | recipient (`target_id`) | `gui/fitCommands/gui/commandFit/` | original command; independent reversal comparison pending |
| `set_command_active` | session action | recipient (`target_id`) | `gui/fitCommands/gui/commandFit/` | original command; independent reversal comparison pending |
| `remove_command` | session action | recipient (`target_id`) | `gui/fitCommands/gui/commandFit/` | original command; independent reversal comparison pending |

The registry guard rejects added/removed operations without explicit dispositions.
Every later mutation task must extend independent reference states, host failure/
restart cases and native controls/raw validators. Adding a label is not parity.
