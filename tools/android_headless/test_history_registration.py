"""History ownership, compound-input preservation and extension boundaries."""
from copy import deepcopy
import unittest
from android_bridge.contract import ARGUMENTS
from android_bridge.history import EditHistory, LABELS, MODULE_LABELS, NON_HISTORY, validate_operations


def record(name):
    return {'spec': {'name': name, 'modules': [], 'notes': 'Keep notes'},
        'skills': {}, 'implants': [], 'projections': [], 'commands': []}


class HistoryRegistrationTest(unittest.TestCase):
    def test_every_actual_operation_has_one_explicit_disposition(self):
        validate_operations(ARGUMENTS)
        self.assertFalse(set(LABELS) & set(NON_HISTORY))
        self.assertEqual(set(MODULE_LABELS), {
            'add_module', 'replace_module', 'remove_module', 'set_fit_restrictions',
            'set_charges', 'set_module_charge', 'set_bulk_charges', 'set_module_states',
            'set_bulk_states', 'fill_modules_item', 'fill_modules_clone', 'clone_selected_modules',
            'clone_module_at', 'change_variation', 'change_bulk_variations', 'remove_bulk_modules', 'swap_modules'})

    def test_future_operation_cannot_silently_escape_registration(self):
        with self.assertRaises(ValueError): validate_operations({**ARGUMENTS, 'new_mutation': ()})
        with self.assertRaises(ValueError): validate_operations({k: v for k, v in ARGUMENTS.items() if k != 'rename_fit'})

    def test_link_action_belongs_to_recipient_and_preserves_source_and_notes(self):
        for operation, field in (('add_projection', 'projections'), ('add_command', 'commands')):
            before = {'source': record('Source'), 'recipient': record('Recipient')}
            after = deepcopy(before)
            after['recipient'][field] = [{'source_id': 'source', 'active': True}]
            history = EditHistory().after_edit(operation, {'source_id': 'source', 'target_id': 'recipient'}, before, after, [])
            self.assertEqual(0, history.details('source')['undo_count'])
            self.assertEqual(1, history.details('recipient')['undo_count'])
            after['recipient']['spec']['notes'] = 'Later notes'
            restored, undone, _ = history.replay('recipient', False, after)
            self.assertEqual([], restored['recipient'][field])
            self.assertEqual(after['source'], restored['source'])
            self.assertEqual('Later notes', restored['recipient']['spec']['notes'])
            redone, _, _ = undone.replay('recipient', True, restored)
            self.assertEqual(after, redone)

    def test_compound_transfer_reverses_modules_and_cargo_as_one_action(self):
        before = {'fit': record('Transfer')}
        before['fit']['spec']['modules'] = [{'name': 'Synthetic gun', 'state': 'ACTIVE', 'charge': 'Synthetic ammo'}]
        before['fit']['spec']['cargo'] = []
        after = deepcopy(before)
        after['fit']['spec'].update(modules=[{'empty_slot': 'HIGH'}], cargo=[{'name': 'Synthetic gun', 'amount': 1}])
        history = EditHistory().after_edit('transfer_cargo', {'fit_id': 'fit'}, before, after, [1])
        self.assertEqual(1, history.details('fit')['undo_count'])
        restored, undone, used = history.replay('fit', False, after)
        self.assertEqual(before, restored)
        self.assertEqual([], used)
        redone, _, used = undone.replay('fit', True, restored)
        self.assertEqual(after, redone)
        self.assertEqual([1], used)

    def test_rename_does_not_erase_later_notes_or_other_fit_actions(self):
        before = {'fit': record('Before'), 'other': record('Other')}
        after = deepcopy(before); after['fit']['spec']['name'] = 'After'
        history = EditHistory().after_edit('rename_fit', {'fit_id': 'fit'}, before, after, [])
        newer = deepcopy(after); newer['other']['spec']['name'] = 'Other after'
        history = history.after_edit('rename_fit', {'fit_id': 'other'}, after, newer, [])
        newer['fit']['spec']['notes'] = 'New independent notes'
        restored, undone, _ = history.replay('fit', False, newer)
        self.assertEqual('Before', restored['fit']['spec']['name'])
        self.assertEqual('New independent notes', restored['fit']['spec']['notes'])
        self.assertEqual(newer['other'], restored['other'])
        self.assertEqual(1, undone.details('other')['undo_count'])

    def test_addition_variation_is_registered_and_labelled(self):
        before = {'fit': record('Addition')}
        before['fit']['implants'] = [{'name': 'Synthetic original', 'active': True}]
        after = deepcopy(before); after['fit']['implants'][0]['name'] = 'Synthetic variation'
        history = EditHistory().after_edit('change_variation', {'fit_id': 'fit', 'context': 'implant'}, before, after, [])
        self.assertEqual('Change addition variation', history.details('fit')['undo_label'])
        restored, _, _ = history.replay('fit', False, after)
        self.assertEqual(before, restored)

    def test_deleting_link_source_invalidates_only_conflicting_recipient_history(self):
        before = {'source': record('Source'), 'target': record('Target'), 'other': record('Other')}
        after = deepcopy(before); after['target']['commands'] = [{'source_id': 'source', 'active': True}]
        history = EditHistory().after_edit('add_command', {'source_id': 'source', 'target_id': 'target'}, before, after, [])
        renamed = deepcopy(after); renamed['other']['spec']['name'] = 'Changed'
        history = history.after_edit('rename_fit', {'fit_id': 'other'}, after, renamed, [])
        removed = deepcopy(renamed); del removed['source']; removed['target']['commands'] = []
        history = history.after_edit('delete_fit', {'fit_id': 'source'}, renamed, removed, [])
        self.assertEqual(0, history.details('target')['undo_count'])
        self.assertEqual(1, history.details('other')['undo_count'])

    def test_noop_registered_action_keeps_existing_redo(self):
        before = {'fit': record('Before')}; after = deepcopy(before); after['fit']['skills'] = {'Synthetic skill': 4}
        history = EditHistory().after_edit('set_skill_level', {'fit_id': 'fit'}, before, after, [])
        restored, history, _ = history.replay('fit', False, after)
        history = history.after_edit('set_skill_level', {'fit_id': 'fit'}, restored, restored, [])
        self.assertEqual(1, history.details('fit')['redo_count'])


if __name__ == '__main__':
    unittest.main()
