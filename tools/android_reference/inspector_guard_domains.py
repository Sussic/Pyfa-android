#!/usr/bin/env python3
"""Source proofs and independent witnesses for three original non-executable guards.

Keep all return IDs. A proof classification never masquerades as a runtime hit.
"""
import argparse
import ast
import hashlib
from itertools import product
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source
from tools.android_reference.inspector_equipment_probes import Module
from tools.android_reference.inspector_equipment_coverage import observe_returns


def function(path, name):
    return next(node for node in ast.walk(ast.parse(path.read_text(encoding='utf-8')))
                if isinstance(node, ast.FunctionDef) and node.name == name)


def proofs(method):
    returns = sorted((node for node in ast.walk(method) if isinstance(node, ast.Return)), key=lambda node: node.lineno)
    compare(98, len(returns))
    results = []
    for index, names in ((62, ('lockRangeBonus', 'scanResBonus')),
                         (64, ('falloffRangeBonus', 'optimalRangeBonus', 'trackingSpeedBonus'))):
        target = returns[index]
        branch = next(node for node in ast.walk(method) if isinstance(node, ast.If)
                      and any(target is descendant for descendant in ast.walk(node))
                      and ast.unparse(node.test) == ' or '.join(names))
        expected = ast.parse('if ' + ' or '.join(names) + ':\n'
                             '    display = 0\n'
                             '    for bonus in (' + ', '.join(names) + '):\n'
                             '        if abs(bonus) > abs(display):\n'
                             '            display = bonus\n'
                             '    if not display:\n'
                             '        return "", None\n').body[0]
        compare(ast.dump(expected.test), ast.dump(branch.test))
        compare([ast.dump(node) for node in expected.body], [ast.dump(node) for node in branch.body[:3]])
        if returns[index] is not branch.body[2].body[0]: raise ValueError('Guard return identity changed')
        shape = ast.dump(ast.Module(body=[branch.test, *branch.body[:3]], type_ignores=[]))
        results.append(dict(return_id=f'misc.py:__getData:{index}', classification='non_executable_finite_numeric_guard',
            domain='Finite numeric values, including signed zero; missing values are separate exception witnesses.',
            reason='Entry requires at least one nonzero value. Starting at zero, the loop selects only strictly greater absolute magnitudes. '
                   'A finite nonzero entry therefore makes display nonzero, and later selections cannot restore zero. '
                   'A missing entry passed to abs raises before this guard.',
            source_shape_sha256=hashlib.sha256(shape.encode()).hexdigest()))
    guard = next(node for node in ast.walk(method) if isinstance(node, ast.If) and returns[40] in node.body)
    block = next(node.body for node in ast.walk(method) if isinstance(getattr(node, 'body', None), list) and guard in node.body)
    position = block.index(guard)
    expected = ast.parse('displayMax = max(grav, ladar, radar, magnet)\n'
                         'displayMin = min(grav, ladar, radar, magnet)\n'
                         'if grav is None or ladar is None or radar is None or magnet is None or displayMax is None:\n'
                         '    return "", None\n').body
    actual = block[position - 2:position + 1]
    compare([ast.dump(node) for node in expected], [ast.dump(node) for node in actual])
    results.append(dict(return_id='misc.py:__getData:40', classification='non_executable_numeric_or_missing_guard',
        domain='Each of the four strengths is finite numeric or missing (None).',
        reason='With four numeric values, max/min return numeric values and every None test is false. '
               'With any missing value, max over four numeric-or-None values raises TypeError before this guard. '
               'The original rejection is retained, not replaced with a fabricated zero.',
        source_shape_sha256=hashlib.sha256(ast.dump(ast.Module(body=actual, type_ignores=[])).encode()).hexdigest()))
    return sorted(results, key=lambda row: row['return_id'])


def inputs():
    values = (-100, -1e-9, -0.0, 0, 1e-9, 100, None)
    rows = []
    strengths = ('scanGravimetricStrengthBonus', 'scanLadarStrengthBonus', 'scanRadarStrengthBonus', 'scanMagnetometricStrengthBonus')
    for group, names in (('ECM', strengths),
                         ('Electronic Warfare Drone', ('maxTargetRangeBonus', 'scanResolutionBonus')),
                         ('Electronic Warfare Drone', ('falloffBonus', 'maxRangeBonus', 'trackingSpeedBonus'))):
        for combination in product(values, repeat=len(names)):
            attrs = dict.fromkeys(strengths, 0)
            attrs.update(dict(zip(names, combination)))
            rows.append(dict(group=group, values=attrs))
    return rows


def sample(request, method):
    rows = []
    forbidden = {'misc.py:__getData:' + str(index) for index in (40, 62, 64)}
    for row in request:
        stuff = Module(row['group'], row['values'])
        try:
            output = observe_returns(lambda: method(None, stuff), {'misc.py:__getData': method})
            if forbidden & set(output['returns']): raise AssertionError('A classified guard was actually executed')
            # Original misc returns tuples; the transport deliberately uses JSON arrays.
            output['value'] = None if output['value'] is None else list(output['value'])
            error = None
        except TypeError as failure:
            if None not in row['values'].values(): raise
            output, error = None, dict(type=type(failure).__name__, message=str(failure))
        rows.append(dict(input=row, output=output, error=error))
    return rows


def export(source, database):
    validate_source(source)
    config = bootstrap(source, database); config.gamedataCache = False
    import config as desktop_config
    desktop_config.pyfaPath = str(source)
    from tools.android_reference.inspector_equipment_oracle import load
    method = load(source).methods['misc.py:__getData']
    request = inputs()
    result = sample(request, method)
    if any(name.startswith('android_bridge') for name in sys.modules): raise ValueError('Android imported into original guard oracle')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source): raise ValueError('Guard oracle imported outside source: ' + name)
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(config.settings), proofs=proofs(function(source / 'gui/builtinViewColumns/misc.py', '__getData')),
                inputs=request, results=result)


def verify(database, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit']); compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    compare(inputs(), fixture['inputs'])
    compare(fixture['proofs'], proofs(function(ROOT / 'android_bridge/inspection_equipment.py', 'misc')))
    from tools.android_headless.check import NoDesktop
    sys.meta_path.insert(0, NoDesktop())
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database); compare(engine.settings, fixture['eos_settings'])
    from android_bridge.inspection_equipment import EquipmentColumns
    actual = sample(fixture['inputs'], EquipmentColumns.misc)
    compare(fixture['results'], actual)
    positive = sum(row['error'] is None for row in actual)
    print(f'PASS 3 unchanged source/algebra classifications; {len(actual)} independent domain witnesses '
          f'({positive} finite/missing outputs, {len(actual) - positive} explicit original missing-value exceptions)')
    print('Executed return coverage remains 111/114; classified guards are not runtime hits.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('export', 'verify')); parser.add_argument('--source', type=Path)
    parser.add_argument('--database', required=True, type=Path); parser.add_argument('--fixture', required=True, type=Path)
    args = parser.parse_args(); database = args.database.resolve()
    compare(json.loads((ROOT / 'tools/android_reference/fixtures/vexor.json').read_text())['database_logical_sha256'], logical_database_digest(database))
    if args.action == 'export':
        if args.source is None: parser.error('export requires pinned --source')
        result = export(args.source.resolve(), database)
        args.fixture.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(f'Exported {len(result["results"])} original guard-domain witnesses and3 source proofs')
    else: verify(database, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
