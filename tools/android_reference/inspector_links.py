#!/usr/bin/env python3
"""Original affected-by trees through the complete A04/A05 edit/reversal sequences."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, compare, logical_database_digest, validate_source
from tools.android_reference.inspector_attributes import contexts


def original_observer(source):
    from tools.android_reference.inspector_affector_oracle import load
    from tools.android_reference.inspector_attribute_oracle import load as attribute_load
    from tools.android_reference.inspector_equipment_oracle import load as equipment_load
    observe = load(source)
    attribute_oracle = attribute_load(source)
    equipment = equipment_load(source)
    return lambda fit: [dict(context=kind, item_id=item.ID, trees=observe(stuff, item, fit),
                            attributes=attribute_oracle['observe'](stuff, item, charge), equipment=equipment(stuff, fit))
                        for kind, stuff, item, charge in contexts(fit)]


def export(kind, source, database, fixture):
    validate_source(source)
    compare(json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256'],
            logical_database_digest(database))
    from tools.android_reference import projection, command
    (projection if kind == 'projection' else command).export(
        SimpleNamespace(source=source, database=database, output=fixture), original_observer)
    result = json.loads(fixture.read_text(encoding='utf-8'))
    result['databaseLogicalSha256'] = logical_database_digest(database)
    fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Exported {kind}: {len(result["states"])} complete linked inspector states')


def verify(kind, database, fixture):
    compare(SOURCE_COMMIT, fixture['source_commit'])
    compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare(json.loads((ROOT / f'tools/android_reference/{kind}.json').read_text()), fixture['inputs'])
    compare(sorted(['initial', *[step['name'] for step in fixture['inputs']['steps']]]), sorted(fixture['states']))
    from tools.android_headless.check import NoDesktop
    sys.meta_path.insert(0, NoDesktop())
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database)
    compare(fixture['eos_settings'], engine.settings)
    from android_bridge.inspection_affectors import views
    from android_bridge.inspection import attributes, equipment
    from tools.android_reference.inspector_affectors import flatten
    source, target = (engine.create_fit(fixture['inputs'][name]) for name in ('source', 'target'))
    count, attribute_count = 0, 0

    def sample(name):
        nonlocal count, attribute_count
        for role, fit in (('source', source), ('target', target)):
            expected = dict(fixture['states'][name][role])
            expected_trees = expected.pop('inspection')
            compare(expected, engine.projection_snapshot(fit), name + '.' + role + '.values')
            actual = []
            for context, stuff, item, charge in contexts(fit):
                attrs = attributes(stuff, item, charge)
                rows = {row['name']: row for row in attrs['rows']}
                projected = {'precise': [{key: row[key] for key in ('name', 'id', 'current', 'base', 'unit')}
                                         for row in attrs['rows']]}
                for mode in ('normal', 'raw'):
                    projected[mode] = [dict(name=entry['name'], groups=entry['groups'], label=entry['label'],
                                           current=rows[entry['name']]['raw_current' if mode == 'raw' else 'display_current'],
                                           base=rows[entry['name']]['raw_base' if mode == 'raw' else 'display_base'])
                                       for entry in attrs[mode]]
                    attribute_count += len(projected[mode])
                actual.append(dict(context=context, item_id=item.ID, attributes=projected, equipment=equipment(stuff, fit),
                                   trees={key: flatten(nodes) for key, nodes in views(stuff, item, fit).items()}))
            compare(expected_trees, actual, name + '.' + role + '.inspection')
            count += sum(len(tree) for row in actual for tree in row['trees'].values())

    sample('initial')
    for step in fixture['inputs']['steps']:
        op = step['operation']
        if op == 'add':
            if kind == 'projection': engine.add_projection(source, target, **{key: step[key] for key in ('range_m', 'active', 'amount')})
            else: engine.add_command(source, target)
        elif op == 'configure': engine.configure_projection(source, target, **{key: step[key] for key in ('range_m', 'active', 'amount')})
        elif op == 'charges': engine.set_charges(source, step['module_indices'], step['charge'])
        elif op == 'remove': (engine.remove_projection if kind == 'projection' else engine.remove_command)(source, target)
        elif op == 'command_state': engine.set_command_active(source, target, step['active'])
        elif op == 'skill': engine.set_skill_level(source, step['skill'], step['level'])
        elif op == 'implant_add': engine.add_implant(source, step['implant'])
        elif op == 'implant_state': engine.set_implant_active(source, step['slot'], step['active'])
        elif op == 'implant_remove': engine.remove_implant(source, step['slot'])
        elif op == 'module_state': engine.set_module_states(source, step['module_indices'], step['state'])
        else: raise ValueError('Unsupported linked inspector operation: ' + op)
        sample(step['name'])
    print(f'PASS {kind}: {len(fixture["states"])} full edit/reversal states; {count} original tree rows, '
          f'{attribute_count} ordered normal/raw attribute rows, precise values, equipment and fitting values')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify'))
    parser.add_argument('--kind', required=True, choices=('projection', 'command'))
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args()
    if args.action == 'export':
        if args.source is None: parser.error('export requires pinned --source')
        export(args.kind, args.source.resolve(), args.database.resolve(), args.fixture.resolve())
    else: verify(args.kind, args.database.resolve(), json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
