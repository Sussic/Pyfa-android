#!/usr/bin/env python3
"""Independent ALPHA1 witness from clean original8b04 EOS and qualified data.

Authored only. Run later in an admitted reference lane, using -I -B. This tool
never imports android_bridge and does not build or replace the pinned database.
"""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import platform
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference


def generate(source, database, expected_dataset, max_clones):
    # bootstrap selects source/data only; the standalone generator must retain
    # the qualified runtime gate normally enforced by reference.main.
    if sys.version_info[:2] != (3, 11):
        raise ValueError('Use Python 3.11 for the pinned desktop reference')
    versions = {name: importlib.metadata.version(name) for name in reference.DEPENDENCIES}
    reference.compare(reference.DEPENDENCIES, versions, 'dependencies')
    runtime = dict(python=platform.python_version(), platform=platform.platform(),
                   sqlite=sqlite3.sqlite_version, dependencies=versions)
    reference.validate_source(source)
    dataset = reference.logical_database_digest(database)
    if dataset != expected_dataset:
        raise ValueError('Reference dataset digest does not match the explicitly selected dataset')
    config = reference.bootstrap(source, database)
    import eos.db
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.drone import Drone
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    case = json.loads(Path(reference.__file__).with_name('vexor.json').read_text(encoding='utf-8'))
    case.pop('edit')
    case['name'] = 'ALPHA1 original synthetic Vexor'
    resolved = {}
    def item(name):
        value = eos.db.getItem(name)
        if value is None: raise ValueError('Missing original reference item: ' + name)
        resolved[name] = value.ID
        return value

    fit = Fit(Ship(item(case['ship'])), name=case['name'])
    fit.character = Character('Original Alpha witness', defaultLevel=5)
    fit.character.alphaCloneID = None
    fit.damagePattern = DamagePattern(**case['damage_pattern'])
    fit.targetProfile = None
    fit.factorReload = case['factor_reload']
    fit.implantLocation = ImplantLocation.FIT
    fit.systemSecurity = FitSystemSecurity[case['security']['system']]
    fit.pilotSecurity = case['security']['pilot']
    fit.ignoreRestrictions = False
    for row in case['modules']:
        module = Module(item(row['name']))
        if row.get('charge'): module.charge = item(row['charge'])
        module.state = FittingModuleState[row['state']]
        module.owner = fit; fit.modules.append(module)
    for row in case['drones']:
        drone = Drone(item(row['name']))
        drone.amount = row['amount']; drone.amountActive = row['active']
        drone.owner = fit; fit.drones.append(drone)
    skills = Character.getSkillIDMap()
    clones = eos.db.getAlphaCloneList()
    if not clones or len(clones) > max_clones:
        raise ValueError('Missing/empty catalogue or source clones exceed the explicit work bound')
    identities = set(); results = []
    def inputs(character):
        return {str(skill.itemID): skill.activeLevel for skill in character.skills}
    learned = inputs(fit.character)
    for clone in sorted(clones, key=lambda row: row.ID):
        if type(clone.ID) is not int or not 0 < clone.ID <= 2**31-1 or clone.ID in identities:
            raise ValueError('Malformed source clone identity')
        identities.add(clone.ID)
        if type(clone.alphaCloneName) is not str or not clone.alphaCloneName.strip() or not clone.skills:
            raise ValueError('Malformed source clone name or empty cap table')
        rows = []; row_ids = set()
        for row in clone.skills:
            if (type(row.typeID) is not int or row.typeID not in skills or row.typeID in row_ids or
                type(row.level) is not int or not 0 <= row.level <= 5 or
                type(row.alphaCloneID) is not int or row.alphaCloneID != clone.ID):
                raise ValueError('Malformed original cap row')
            row_ids.add(row.typeID); rows.append(dict(skill_id=row.typeID, cap=row.level))
        middle = next((row for row in rows if 1 <= row['cap'] <= 4), None)
        absent = next((i for i in skills if i not in row_ids), None)
        if middle is None or absent is None:
            raise ValueError('Source cannot furnish required below/equal/above/absent witness')
        skill_cases = []
        for value in (None, 0, middle['cap']-1, middle['cap'], middle['cap']+1):
            character = Character('Original learned state witness', defaultLevel=5)
            character.getSkill(middle['skill_id']).setLevel(value, persist=True, ignoreRestrict=True)
            character.alphaCloneID = clone.ID
            skill = character.getSkill(middle['skill_id'])
            skill_cases.append(dict(skill_id=middle['skill_id'], cap=middle['cap'], learned=skill.activeLevel,
                                    effective=skill.level))
        character = Character('Original absent skill witness', defaultLevel=5)
        character.alphaCloneID = clone.ID
        skill_cases.append(dict(skill_id=absent, cap=None, learned=character.getSkill(absent).activeLevel,
                                effective=character.getSkill(absent).level))
        states = {}
        for label, identity in (('omega', None), ('capped', clone.ID), ('restored', None)):
            fit.character.alphaCloneID = identity
            fit.clear(); fit.calculateModifiedAttributes()
            states[label] = reference.snapshot(fit)
            reference.compare(learned, inputs(fit.character), 'learned_inputs_' + label)
        reference.compare(states['omega'], states['restored'], 'uncap_restoration')
        changed = [key for key in states['omega'] if
                   states['omega'][key]['value'] != states['capped'][key]['value']]
        if not changed:
            raise ValueError('Original witness must contain a meaningful changed fitting output')
        results.append(dict(alpha_clone_id=clone.ID, name=clone.alphaCloneName,
                            cap_rows=sorted(rows, key=lambda row: row['skill_id']),
                            skill_cases=skill_cases, changed_outputs=changed, **states))
    imported = {}
    for name, module in sorted(sys.modules.items()):
        if name == 'eos' or name.startswith('eos.') or name in ('config', 'utils'):
            path = getattr(module, '__file__', None)
            if path is None: continue
            path = Path(path).resolve()
            relative = path.relative_to(source).as_posix()  # Fail if source was shadowed.
            imported[name] = dict(path=relative, sha256=reference.digest_file(path))
    if any(name == 'android_bridge' or name.startswith('android_bridge.') for name in sys.modules):
        raise ValueError('Mobile implementation contaminated original-reference witness')
    return dict(schema_version=1, source_commit=reference.SOURCE_COMMIT, dataset_sha256=dataset,
                reference_runtime=runtime,
                source_data_sha256=reference.source_data_digest(source), reference_imports=imported,
                generator_sha256=reference.digest_file(Path(__file__).resolve()),
                reference_helper_sha256=reference.digest_file(Path(reference.__file__).resolve()),
                input_fixture_sha256=reference.digest_file(Path(reference.__file__).with_name('vexor.json')),
                spec=deepcopy(case), learned=learned, resolved_item_ids=resolved,
                eos_settings=dict(config.settings), clones=results,
                tolerances=dict(relative=reference.REL_TOL, absolute=reference.ABS_TOL))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--dataset-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-clones', type=int, default=32)
    args = parser.parse_args()
    if len(args.dataset_sha256) != 64 or any(c not in '0123456789abcdef' for c in args.dataset_sha256):
        parser.error('Expected an exact logical dataset SHA256')
    if not 1 <= args.max_clones <= 128: parser.error('max-clones must be between 1 and 128')
    if args.output.exists(): parser.error('Choose a new output; preserve existing reference evidence')
    result = generate(args.source.resolve(), args.database.resolve(), args.dataset_sha256, args.max_clones)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+'\n', encoding='utf-8')


if __name__ == '__main__': main()
