#!/usr/bin/env python3
"""Finite C07.3 actual-dispatch comparison and raw native-wire exporter.

Parent admission is mandatory. This file is not a general runner. Each R1--R4
reopen is a separate guarded process. Expected values are read only from the
accepted original receipt, never calculated by a candidate expectation helper.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import uuid
from unittest.mock import patch

sys.dont_write_bytecode = True
REPO = Path(os.environ['PYFA_CURRENT_REPO']).resolve()
sys.path[:0] = [str(REPO), os.environ['PYFA_REFERENCE_SOURCE']]

SCHEDULE_SHA = '194b123cb0d06ce26cd25c62b858c23790cacd308c6fd06becd7351f861406e7'
ORIGINAL_SHA = '893030da0954ee4b8d0e8d8893ef5d25d4a22cb265763d6c29ff16d1b0c9191e'
CATALOGUE_SHA = 'b11cd1dfe4b074c9a92e2bef8ccf6fcbfa9f577b9177e77b2d627cf17c834fda'
FROZEN_SHA = 'fd4a9ab6804bcbbea341fac7249b114d2a5908256a81e56867af67a1ccca5138'
MAX_FILE = 16 * 1024**2
MAX_EVIDENCE = 10 * 1024**2


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def scalar(value):
    assert type(value) in (int, float) and math.isfinite(value)
    return dict(kind='integer' if type(value) is int else 'decimal', value=value,
                float_hex=value.hex() if type(value) is float else None)


def exact(expected, actual, path='root'):
    """Strict kinds and every float bit pattern, including signed zero."""
    assert type(expected) is type(actual), (path, type(expected), type(actual))
    if type(expected) is dict:
        assert expected.keys() == actual.keys(), (path, expected.keys(), actual.keys())
        for key in expected:
            exact(expected[key], actual[key], path + '.' + key)
    elif type(expected) is list:
        assert len(expected) == len(actual), (path, len(expected), len(actual))
        for index, (left, right) in enumerate(zip(expected, actual)):
            exact(left, right, path + '.' + str(index))
    elif type(expected) is float:
        assert expected.hex() == actual.hex(), (path, expected.hex(), actual.hex())
    else:
        assert expected == actual, (path, expected, actual)


def meaning(value):
    if type(value) is list:
        return [meaning(row) for row in value]
    if type(value) is dict:
        return {key: meaning(row) for key, row in value.items()
                if key not in ('identity', 'original_orm_id', 'original_character_orm_id', 'profile_identity')}
    return value


def verify_imports():
    """Bind actual application import origins to the parent's reviewed manifest."""
    manifest = json.loads(Path(os.environ['C073_INPUT_MANIFEST']).read_text())
    reference = Path(manifest['reference_root']).resolve()
    result = {}
    for name, module in tuple(sys.modules.items()):
        location = getattr(module, '__file__', None)
        if not location:
            continue
        path = Path(location).resolve()
        if path.suffix != '.py':
            continue
        if path.is_relative_to(REPO):
            expected = manifest['source_files'].get(str(path.relative_to(REPO)))
        elif path.is_relative_to(reference):
            expected = manifest['reference_files'].get(str(path.relative_to(reference)))
        elif name.split('.')[0] in {'android_bridge', 'eos', 'graphs', 'utils', 'mobile_runtime'}:
            raise AssertionError('Unbound application import origin: ' + str(path))
        else:
            continue
        assert expected is not None and sha(path) == expected, (name, str(path), expected)
        result[str(path)] = expected
    return result


class Evidence:
    def __init__(self, root):
        self.root = root

    def reserve(self, amount):
        used = sum(path.stat().st_size for path in self.root.rglob('*') if path.is_file())
        assert used + amount <= MAX_EVIDENCE, ('bounded evidence budget exceeded', used, amount)

    def write(self, name, value):
        data = (value if type(value) is str else encode(value)) + '\n'
        raw = data.encode('utf-8')
        assert len(raw) <= MAX_FILE
        self.reserve(len(raw))
        with (self.root / name).open('xb') as stream:
            stream.write(raw)

    def append(self, name, value):
        raw = (encode(value) + '\n').encode('utf-8')
        path = self.root / name
        assert (path.stat().st_size if path.exists() else 0) + len(raw) <= MAX_FILE
        self.reserve(len(raw))
        with path.open('ab') as stream:
            stream.write(raw)


class Lane:
    def __init__(self, engine, dataset, evidence, catalogue, name, store=None):
        from android_bridge.offline.native_session import NativeSession
        self.engine, self.dataset, self.evidence, self.catalogue = engine, dataset, evidence, catalogue
        self.name, self.index = name, 0
        self.path = store or evidence.root / (name + '.sqlite')
        self.session = NativeSession(engine, self.path, dataset, None)
        self.fits, self.profiles, self.recipes = {}, {}, {}

    def close(self):
        self.session.graph._bridge._reset_storage()

    def reset_session(self):
        from android_bridge.offline.native_session import NativeSession
        self.close()
        self.session = NativeSession(self.engine, self.path, self.dataset, None)
        assert self.session.history.rows == {}

    def label(self, operation):
        self.index += 1
        return self.name + '-' + str(self.index) + '-' + operation

    def auxiliary(self, route, request, response):
        # Setup/feature/source operations are actual raw dispatches too. Their
        # full request plus exact response digest and status are retained once;
        # finite named/intermediate observations retain the relevant result.
        result = json.loads(response)
        self.evidence.append('dispatches.jsonl', dict(route=route, request=request,
            response_sha256=hashlib.sha256(response.encode('utf-8')).hexdigest(),
            status=result.get('status'), ok=result.get('ok'), committed=result.get('committed')))
        return result

    def bridge(self, operation, arguments):
        session = self.session
        ids = {arguments[key] for key in ('fit_id', 'source_id', 'target_id') if key in arguments}
        request = encode(dict(version=1, request_id=self.label(operation), session_id=session.session_id,
            operation=operation, expected_revisions={key: session._revisions[key] for key in ids}, arguments=arguments))
        result = self.auxiliary('bridge', request, session.dispatch(request))
        assert result['status'] == 'ok', result
        return result

    def feature(self, operation, arguments, anchor=None):
        request = encode(dict(version=2, request_id=self.label(operation), context=self.session.context(),
            operation=operation, arguments=arguments, anchor_fit_id=anchor))
        result = self.auxiliary('feature', request, self.session.feature_dispatch(request))
        assert result['ok'], result
        return result

    def sets(self, operation='read', arguments=None, *, anchor=None, selected=None,
             profile=None, target='library', offset=0, limit=1, retain=True, ok=True, fault=None):
        session = self.session
        arguments = {} if arguments is None else arguments
        selected = arguments.get('set_id', selected)
        profile = arguments.get('profile_id', profile)
        if operation == 'apply_fit':
            target = anchor
        request = dict(version=1, request_id=self.label(operation), context=session.context(),
            anchor_fit_id=anchor, view=dict(query='', offset=offset, limit=limit,
            selected_set_id=selected, target_profile_id=profile, history_target=target),
            operation=operation, arguments=arguments)
        previous = None
        if operation != 'read':
            prior = dict(request, request_id=self.label('before'), operation='read', arguments={})
            prior_raw = encode(prior)
            prior_response = session.implant_sets_dispatch(prior_raw)
            assert json.loads(prior_response)['ok'], prior_response
            previous = dict(request=prior_raw, response=prior_response)
        features = encode(session.feature_state(anchor))
        bridge = session.bootstrap()
        raw = encode(request)
        durable = sha(self.path)
        before_graph = deepcopy(session.graph._state)
        old_history = session.history
        old_floors = deepcopy({key: value for key, value in vars(session).items() if key.endswith('_floor')})
        graph_floor = deepcopy(session.graph._revision_floor)
        if fault:
            with patch.object(session._store, 'confirm', side_effect=RuntimeError('deliberate uncertain acknowledgement')):
                response = session.implant_sets_dispatch(raw)
        else:
            response = session.implant_sets_dispatch(raw)
        result = json.loads(response)
        assert result['ok'] is ok, result
        after = encode(session.feature_state(result['state']['anchor_fit_id'])) if result['ok'] else None
        if retain:
            self.evidence.append('events.jsonl', dict(label=request['request_id'], request=raw, response=response,
                features_before=features, features_after=after, bridge_before=bridge, before_set_state=previous))
        else:
            self.auxiliary('implant_sets_setup', raw, response)
        if result['ok'] and not result['committed'] or not result['ok'] and not result['reopen_required']:
            assert sha(self.path) == durable and session.graph._state == before_graph
            assert session.history is old_history and session.graph._revision_floor == graph_floor
            exact(old_floors, {key: value for key, value in vars(session).items() if key.endswith('_floor')})
        if result['ok']:
            assert result['state']['context']['generation'] == request['context']['generation'] + int(result['committed'])
            if operation == 'read':
                assert after == features and result['bridge'] is None
            else:
                assert result['bridge']['request_id'] == 'bootstrap'
        return result

    def revision(self, key):
        return 0 if key.startswith('builtin:') else self.session.graph._state['implant_sets']['sets'][key]['revision']

    def change(self, key, operation, *, retain=True, **arguments):
        return self.sets(operation, dict(set_id=key, revision=self.revision(key), **arguments), retain=retain)

    def add(self, key, item, *, retain=True):
        rows = self.session.graph._state['implant_sets']['sets'][key]['item_ids']
        from android_bridge.character_implants import catalogue
        occupant = next((value for value in rows if catalogue(value)[1] == item['slot']), None)
        return self.change(key, 'add_item', item_id=item['id'], replace_item_id=occupant, retain=retain)

    def observe(self, phase, order=None, graph=False):
        from eos.const import ImplantLocation
        session = self.session
        order = phase['read_order'] if order is None else order
        for fit in session._fits.values():
            fit.clear()
        result = {}
        owned = []
        for key in order:
            fit_id = self.fits[key]
            fit = self.engine.prepare_read(session._fits[fit_id])
            record = session._records[fit_id]
            profile_id = session.graph._state['profiles']['bindings'][fit_id]['profile_id']
            assert profile_id == self.profiles[phase['fixtures'][key]['profile']]
            for kind, field, live in [('projection', 'projections', fit.projectedFitDict),
                                      ('command', 'commands', fit.commandFitDict)]:
                links = [row for row in phase.get('links', []) if row['kind'] == kind and row['target'] == key]
                expected_links = []
                for link in links:
                    edge = dict(source_id=self.fits[link['source']], active=link['active'])
                    if kind == 'projection':
                        edge.update(range_m=link['range_m'], amount=link['amount'])
                    expected_links.append(edge)
                if kind == 'command':
                    expected_links.sort(key=lambda row: row['source_id'])
                exact(expected_links, record[field], key + '.' + field)
                assert {id(value) for value in live.values()} == {id(session._fits[self.fits[row['source']]]) for row in links}
            local = [dict(identity=record['inspection_ids']['implants'][index], item_id=row.itemID,
                          slot=row.slot, active=row.active) for index, row in enumerate(fit.implants)]
            assert len(record['inspection_ids']['implants']) == len(record['implants']) == len(local)
            exact(record['implants'], [dict(name=row.item.name, slot=row.slot, active=row.active) for row in fit.implants],
                  key + '.durable_and_live_local')
            character = [dict(identity=row['implant_id'], item_id=row['item_id'], slot=row['slot'], active=row['active'])
                         for row in record['character_implants']]
            exact([{key: value for key, value in row.items() if key != 'name'} for row in record['character_implants']],
                  session.graph._state['profiles']['profiles'][profile_id]['implants'],
                  key + '.character_projection_and_authority')
            exact([row['name'] for row in record['character_implants']], [row.item.name for row in fit.character.implants],
                  key + '.character_display_names')
            exact([{key: value for key, value in row.items() if key != 'identity'} for row in character],
                  [dict(item_id=row.itemID, slot=row.slot, active=row.active) for row in fit.character.implants],
                  key + '.durable_and_live_character')
            source = ImplantLocation(fit.implantSource).name
            result[key] = dict(identity=key, profile_identity=profile_id, source=source, local_implants=local,
                character_implants=character, applied_implants=local if source == 'FIT' else character,
                maxVelocity=scalar(fit.ship.getModifiedItemAttr('maxVelocity')),
                scanResolution=scalar(fit.ship.getModifiedItemAttr('scanResolution')), shieldHP=scalar(fit.hp['shield']),
                projection_count=len(fit.projectedFits), command_count=len(fit.commandFits))
            owned += [id(row) for row in fit.implants] + [id(row) for row in fit.character.implants]
        assert len(set(owned)) == len(owned), 'Materialized implant objects are not independently owned'
        if graph:
            points = []
            for time in (0.0, 1.0, 10.0, 30.0):
                request = encode(dict(version=1, request_id=self.label('g07'), context=session.context(),
                    fits=[dict(fit_id=self.fits['A'], revision=session._revisions[self.fits['A']])],
                    x=dict(quantity='time', unit='s', range=[time, time]), y=dict(quantity='speed', unit='m/s'),
                    resolution=1, budget_ms=10000, target_mass_mkg=None, target_inertia=None))
                response = session.mobility_samples(request)
                value = self.auxiliary('g07', request, response)
                assert value['ok'], value
                points.append(dict(time_s=time, raw=scalar(value['series'][0]['y'][0])))
            result['A']['g07_speed'] = points
        return result


def setup(lane, phase, schedule):
    items = schedule['known_items']
    for key in phase['initial_profiles']:
        name = 'C07.3 ' + phase['id'] + ' ' + key
        result = lane.feature('create_profile', dict(name=name, source='builtin:all5'))
        lane.profiles[key] = next(row['profile_id'] for row in result['state']['profiles'] if row['name'] == name)
    for key, fixture in phase['fixtures'].items():
        spec = dict(name='C07.3 ' + phase['id'] + ' ' + key, ship=items[fixture['ship']]['name'], skill_level=5,
            factor_reload=False, damage_pattern=dict(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25),
            target_profile=None, security=dict(system='HISEC', pilot=0.0), implants=[], boosters=[], projections=[],
            commands=[], environments=[], modules=[dict(name=items[row['item']]['name'], state=row['state'],
                charge=items[row['charge']]['name'] if row['charge'] else None) for row in fixture['modules']],
            drones=[], cargo=[], ignore_restrictions=False)
        previous = set(lane.session._fits)
        lane.bridge('create_fit', dict(spec=spec))
        created = set(lane.session._fits) - previous
        assert len(created) == 1
        fit_id = lane.fits[key] = created.pop()
        lane.feature('assign_profile', dict(fit_id=fit_id, profile_id=lane.profiles[fixture['profile']]), fit_id)
        for row in fixture['local_implants']:
            lane.bridge('fit_implant', dict(fit_id=fit_id, item_id=items[row['item']]['id']))
            if not row['active']:
                lane.bridge('toggle_implants', dict(fit_id=fit_id,
                    main_position=len(lane.session._records[fit_id]['implants']) - 1, positions=[]))
        lane.feature('set_implant_source', dict(fit_id=fit_id, fit_revision=lane.session._revisions[fit_id], source=fixture['source']), fit_id)
    # The existing editor intentionally has no character-implant active toggle.
    # This ONE graph-owned detached draft/save seeds the sole nonempty initial
    # shared profile. It is never used for a scheduled transition or expected value.
    populated = [(key, rows) for key, rows in phase['initial_profiles'].items() if rows]
    assert len(populated) == 1
    key, rows = populated[0]
    seed_rows = [dict(implant_id=uuid.uuid4().hex, item_id=items[row['item']]['id'],
                     slot=items[row['item']]['slot'], active=row['active']) for row in rows]
    def seed(model):
        draft = model.begin(lane.profiles[key])
        draft.values['implants'] = deepcopy(seed_rows)
        return model.save(draft)
    lane.session.graph._profile_change(seed)
    lane.evidence.append('seeds.jsonl', dict(phase=phase['id'], profile=lane.profiles[key], rows=seed_rows,
        authority='Initial fixture only: NativeSession.graph._profile_change -> Profiles.begin -> detached implants -> Profiles.save',
        schedule_sha256=SCHEDULE_SHA, exporter_sha256=sha(__file__),
        profile_graph_sha256=sha(REPO / 'android_bridge/offline/profile_graph.py'),
        profiles_sha256=sha(REPO / 'android_bridge/offline/profiles.py')))
    for link in phase.get('links', []):
        arguments = dict(source_id=lane.fits[link['source']], target_id=lane.fits[link['target']], active=link['active'])
        if link['kind'] == 'projection':
            arguments.update(range_m=link['range_m'], amount=link['amount'])
        lane.bridge('add_' + link['kind'], arguments)
    for key, members in schedule['recipes'].items():
        result = lane.sets('create', dict(name='C07.3 ' + key), retain=False)
        lane.recipes[key] = result['state']['detail']['set_id']
        for member in members:
            lane.add(lane.recipes[key], items[member], retain=False)
    lane.recipes.update({key: 'builtin:implant-set:' + str(value['set_id']) for key, value in schedule['selected_presets'].items()})
    lane.reset_session()  # Rebuild floors and start genuine empty session history.


def identity_checks(states, phase):
    def collections(name, fit):
        return {key: states[name][fit][key] for key in ('local_implants', 'character_implants', 'applied_implants', 'source')}
    first = phase['states'][0]['name']
    for state in states:
        exact(states[first]['I'], states[state]['I'], state + '.independent')
    if phase['id'] == 'merge_and_save':
        for left, right in [('M01', 'M02'), ('M02', 'M03'), ('M04', 'M05'), ('M12', 'M13'), ('M11', 'M14'), ('M12', 'M15')]:
            for fit in phase['fixtures']:
                exact(collections(left, fit), collections(right, fit), left + '/' + right + '.' + fit)
        old = states['M00']['A']['local_implants']
        new = states['M01']['A']['local_implants']
        assert new[0] == old[1] and new[1] == old[2] and not new[0]['active']
        assert states['M08']['T']['local_implants'] == []
    else:
        for state in states:
            for fit in phase['fixtures']:
                exact(states['C00'][fit]['local_implants'], states[state][fit]['local_implants'],
                      state + '.' + fit + '.dormant_local_preserved')
            for fit in ('B', 'C', 'S'):
                exact(states[state]['A']['character_implants'], states[state][fit]['character_implants'],
                      state + '.' + fit + '.shared_character_authority')
                assert states[state]['A']['profile_identity'] == states[state][fit]['profile_identity']
        for left, right in [('C02', 'C03'), ('C03', 'C05'), ('C01', 'C06'), ('C00', 'C07'), ('C01', 'C08')]:
            for fit in phase['fixtures']:
                exact(collections(left, fit), collections(right, fit), left + '/' + right + '.' + fit)
        before = states['C01']['A']['character_implants']
        after = states['C02']['A']['character_implants']
        assert before[0] == after[0] and before[0]['slot'] == 79 and not before[0]['active']
        assert all(left['identity'] != right['identity'] for left, right in zip(before[1:], after[1:]))


def snapshot(lane, case, phase, state, observation, *, legacy=False):
    from android_bridge.offline.profile_store import GraphStore
    authority = deepcopy(lane.session.graph._state)
    path = lane.evidence.root / (case + '.sqlite')
    if legacy:
        authority['version'] = 5
        del authority['implant_sets']
        # A separate fixture store, not a mutation of live candidate authority.
        store = GraphStore(path)
        attempt = store.prepare(authority)
        store.write(attempt)
        assert store.confirm(attempt) == 'new'
        store.accept(attempt)
    else:
        lane.evidence.reserve(lane.path.stat().st_size)
        shutil.copyfile(lane.path, path)
    lane.evidence.write(case + '-seed.json', dict(case=case, phase=phase, source_state=state,
        fits=lane.fits, profiles=lane.profiles, recipes=lane.recipes, authority=authority,
        observation=observation, store_sha256=sha(path), legacy_fixture=legacy))


def catalogue_check(lane, original):
    assert original['ok'] and len(original['rows']) == 56
    entries = []
    for offset in (0, 50):
        entries += lane.sets(offset=offset, limit=50)['state']['page']['entries']
    expected = {}
    for row in original['rows']:
        key = 'builtin:implant-set:' + str(row['set_id'])
        expected[key] = dict(set_id=key, kind='builtin', name=((row['grade'] + ' ') if row['grade'] else '') + row['family'],
            family=row['family'], grade=row['grade'], revision=0, item_count=len(row['resolved']))
        actual = lane.sets(selected=key)['state']['detail']
        exact(expected[key], {k: v for k, v in actual.items() if k != 'items'}, key)
        exact([dict(item_id=value['item_id'], name=value['name'], slot=value['slot']) for value in row['resolved']], actual['items'], key + '.items')
        assert [value['item_id'] for value in actual['items']] == row['stored_order']
        assert not row['repeated_slots']
    assert len(entries) == len(expected) and {row['set_id'] for row in entries} == expected.keys()
    for row in entries:
        exact(expected[row['set_id']], row)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--reopen', choices=('R1', 'R2', 'R3', 'R4'))
    args = parser.parse_args()
    assert os.environ.get('C073_PARENT_HEAVY_LANE') == 'granted', 'Parent exclusive admission required'
    reference = args.reference.resolve()
    for name, digest in [('ORACLE-SCHEDULE.json', SCHEDULE_SHA), ('FROZEN-INPUTS.json', FROZEN_SHA),
                         ('original-attempt-1/receipt.json', ORIGINAL_SHA), ('catalogue-attempt-1/receipt.json', CATALOGUE_SHA)]:
        assert sha(reference / name) == digest, name
    schedule = json.loads((reference / 'ORACLE-SCHEDULE.json').read_text())
    original = json.loads((reference / 'original-attempt-1/receipt.json').read_text())
    assert original['ok'] and original['database_unchanged']
    from android_bridge.engine import HeadlessEngine
    from android_bridge.character_implants import catalog_response
    database = Path(os.environ['PYFA_DATABASE'])
    assert sha(database) == '68fb9ea965cb046e426f7c068c7508b55a4e82d2a3dceeed3cb948585d6e7203'
    dataset = os.environ['PYFA_DATASET_SHA']
    engine = HeadlessEngine(database)
    assert dict(engine.settings) == schedule['settings']['eos_settings']
    output = args.output_dir.resolve()
    if args.reopen:
        return reopen(engine, dataset, output, schedule, original, args.reopen)
    output.mkdir(parents=True, exist_ok=False)
    evidence = Evidence(output)
    catalogue = encode(catalog_response(engine, dataset))
    assert json.loads(catalogue)['ok']
    evidence.write('events.jsonl', dict(schema='c073-implant-set-wire-v1', catalogue=catalogue))
    catalogue_lane = Lane(engine, dataset, evidence, catalogue, 'catalogue')
    catalogue_check(catalogue_lane, json.loads((reference / 'catalogue-attempt-1/receipt.json').read_text()))
    catalogue_lane.close()
    all_states, mutations, count, graph_count = {}, [], 0, 0
    for phase in schedule['phases']:
        lane = Lane(engine, dataset, evidence, catalogue, phase['id'])
        setup(lane, phase, schedule)
        states, deleted_recipes = {}, {}
        for state in phase['states']:
            for index, operation in enumerate(state['operations']):
                kind = operation['operation']
                fit = lane.fits.get(operation.get('fit'))
                recipe = lane.recipes.get(operation.get('recipe'))
                if kind == 'fit_set_command':
                    lane.sets('apply_fit', dict(set_id=recipe, revision=lane.revision(recipe), fit_revision=lane.session._revisions[fit]), anchor=fit)
                elif kind in ('undo_fit_set_command', 'redo_fit_set_command', 'undo_source_command'):
                    lane.sets('redo' if kind.startswith('redo') else 'undo', anchor=fit, target=fit)
                elif kind == 'source_command':
                    lane.feature('set_implant_source', dict(fit_id=fit, fit_revision=lane.session._revisions[fit], source=operation['source']), fit)
                elif kind == 'save_current_recipe':
                    value = lane.sets('save_current', dict(name=operation['name'], fit_revision=lane.session._revisions[fit]), anchor=fit)
                    lane.recipes[operation['recipe']] = value['state']['detail']['set_id']
                elif kind == 'rename_recipe':
                    lane.change(recipe, 'rename', name=operation['name'])
                elif kind == 'edit_recipe':
                    lane.add(recipe, schedule['known_items'][operation['add_item']])
                elif kind == 'delete_recipe':
                    deleted_recipes[recipe] = deepcopy(lane.session.graph._state['implant_sets']['sets'][recipe])
                    lane.change(recipe, 'delete')
                elif kind == 'character_set_apply':
                    if state['name'] == 'C08':
                        lane.sets('redo', profile=lane.profiles['P'])
                    else:
                        profile = lane.profiles[operation['profile']]
                        lane.sets('apply_profile', dict(set_id=recipe, revision=lane.revision(recipe), profile_id=profile,
                            profile_revision=lane.session.graph._state['profiles']['profiles'][profile]['revision']), anchor=lane.fits['A'])
                elif kind == 'restore_character_inputs':
                    lane.sets('undo', profile=lane.profiles[operation['profile']])
                else:
                    raise AssertionError(kind)
                observation = lane.observe(phase)
                expected = next(row['fits'] for row in original['phases'][phase['id']]['mutations']
                                if row['state'] == state['name'] and row['operation_index'] == index)
                exact(meaning(expected), meaning(observation), phase['id'] + '.' + state['name'] + '.intermediate.' + str(index))
                mutations.append(dict(phase=phase['id'], state=state['name'], operation_index=index,
                                      operation=operation, observation=observation))
            observation = lane.observe(phase, graph=state['name'] in phase['graph_states'])
            expected = original['phases'][phase['id']]['states'][state['name']]
            exact(meaning(expected), meaning(observation), phase['id'] + '.' + state['name'])
            states[state['name']] = observation
            count += len(observation)
            graph_count += len(observation['A'].get('g07_speed', []))
            if state['name'] in schedule['observations']['alternate_read_order_states']:
                alternate = lane.observe(phase, list(reversed(phase['read_order'])), graph=True)
                exact(observation, alternate, state['name'] + '.alternate_read_order')
            for name, source, legacy in [('R1', 'M16', False), ('R2', 'C01', False), ('R3', 'M12', True)]:
                if state['name'] == source:
                    snapshot(lane, name, phase, source, observation, legacy=legacy)
            if state['name'] == 'M09':
                duplicate = lane.sets('save_current', dict(name='Saved fit', fit_revision=lane.session._revisions[lane.fits['A']]),
                                     anchor=lane.fits['A'], ok=False)
                assert duplicate['error']['code'] == 'duplicate_name'
            if state['name'] == 'M13':
                # Native-only undo-delete witness is not an additional named
                # original state. Redo deletion keeps M14 detached-recipe proof.
                recipe = lane.recipes['CONFLICTING_SUBSET']
                floor = lane.session._implant_set_floor[recipe]
                restored = lane.sets('undo', selected=recipe)['state']['detail']
                saved = deleted_recipes[recipe]
                assert restored['set_id'] == recipe and restored['revision'] > floor > saved['revision']
                assert restored['name'] == saved['name'] and [row['item_id'] for row in restored['items']] == saved['item_ids']
                exact(observation, lane.observe(phase), 'M13.undo_template_delete_preserves_every_fit')
                lane.sets('redo', selected=recipe)
                assert recipe not in lane.session.graph._state['implant_sets']['sets']
                exact(observation, lane.observe(phase), 'M13.redo_template_delete_preserves_every_fit')
        identity_checks(states, phase)
        all_states[phase['id']] = states
        lane.close()
    assert sum(map(len, all_states.values())) == 26 and count == 114 and count * 3 == 342 and graph_count == 24
    wire_only(engine, dataset, evidence, catalogue, schedule)
    evidence.write('observations.json', all_states)
    evidence.write('mutations.json', mutations)
    evidence.write('imports.json', verify_imports())
    evidence.write('result.json', dict(ok=True, named_states=26, named_fit_observations=count,
        named_raw_scalars=count * 3, named_g07_points=graph_count, original_sha256=ORIGINAL_SHA,
        original_catalogue_sha256=CATALOGUE_SHA, schedule_sha256=SCHEDULE_SHA,
        qualifications=['Host Python only; actual Kotlin consumption and four fresh processes remain separate gates.',
            'Initial inactive shared-profile rows use one graph-owned detached Profiles draft/save per numerical phase.',
            'R3 is a disclosed separate synthetic v5 envelope, not an original desktop store.',
            'C06/C07 compare equivalent original inputs to actual native undo; C08 executes actual native redo.',
            'Reconstructed/supplemental source and dataset qualifications remain; no Android/device/release claim.']))


def wire_only(engine, dataset, evidence, catalogue, schedule):
    lane = Lane(engine, dataset, evidence, catalogue, 'wire-only')
    value = lane.sets('create', dict(name='Wire supplementary \U0001f680'))
    key = value['state']['detail']['set_id']
    lane.add(key, schedule['known_items']['NAV1'])
    lane.add(key, schedule['known_items']['AU79'])
    copied = lane.change(key, 'duplicate', name='Wire copy')['state']['detail']['set_id']
    lane.change(copied, 'remove_item', item_id=schedule['known_items']['AU79']['id'])
    lane.change(copied, 'rename', name='Wire copy')  # Deliberate native same-name no-op.
    created = lane.feature('create_profile', dict(name='Wire unassigned', source='builtin:all5'))
    pid = next(row['profile_id'] for row in created['state']['profiles'] if row['name'] == 'Wire unassigned')
    lane.profiles['P'] = pid
    lane.sets('apply_profile', dict(set_id=key, revision=lane.revision(key), profile_id=pid,
        profile_revision=lane.session.graph._state['profiles']['profiles'][pid]['revision']))
    snapshot(lane, 'R4', None, None, {})
    lane.change(copied, 'delete')
    lane.sets('undo', selected=copied)
    lane.sets('redo', selected=copied)
    # Existing actual feature history, viewed/replayed via the new wire.
    created = lane.feature('create_profile', dict(name='Wire disappearing profile', source='builtin:all5'))
    gone = next(row['profile_id'] for row in created['state']['profiles'] if row['name'] == 'Wire disappearing profile')
    lane.sets('undo', profile=gone)
    preview_request = encode(dict(version=1, request_id=lane.label('import-preview'), profile_id='builtin:all5',
        documents=[dict(label='Synthetic wire-only EFT', text='[Rifter, C07.3 disappearing fit]\n')]))
    preview = lane.auxiliary('import_preview', preview_request, lane.session.import_preview(preview_request))
    assert preview['ok'], preview
    imported = lane.auxiliary('import', encode(preview['request']), lane.session.import_execute(encode(preview['request'])))
    assert imported['ok'], imported
    fit = next(iter(lane.session._fits))
    lane.sets('undo', anchor=fit, target=fit)
    lane.sets('read', selected='implant-set:' + 'f' * 32, profile='profile:' + 'f' * 32)
    lane.sets('apply_profile', dict(set_id=key, revision=lane.revision(key), profile_id='builtin:all5', profile_revision=1), ok=False)
    # Native uniqueness differs from the original save-current GUI route; the
    # same duplicate-name validator is also exercised here without inventing a fit.
    lane.sets('create', dict(name='Wire supplementary \U0001f680'), ok=False)
    uncertain = lane.sets('create', dict(name='Wire uncertain'), ok=False, fault=True)
    assert uncertain['committed'] is None and uncertain['reopen_required'] and not lane.session._available
    lane.close()


def reopen(engine, dataset, output, schedule, original, case):
    seed = json.loads((output / (case + '-seed.json')).read_text())
    path = output / (case + '.sqlite')
    assert sha(path) == seed['store_sha256']
    evidence = Evidence(output)
    lane = Lane(engine, dataset, evidence, None, 'reopen-' + case, path)
    lane.fits, lane.profiles, lane.recipes = seed['fits'], seed['profiles'], seed['recipes']
    session = lane.session
    assert session.history.rows == {} and session.graph._state['version'] == 6
    expected_authority = deepcopy(seed['authority'])
    if case == 'R3':
        expected_authority['version'] = 6
        expected_authority['implant_sets'] = dict(version=1, sets={})
    exact(expected_authority, session.graph._state, case + '.authority')
    assert session.graph.migration_pending is (case == 'R3')
    observation = lane.observe(seed['phase'], graph='g07_speed' in seed['observation'].get('A', {})) if seed['phase'] else {}
    exact(seed['observation'], observation, case + '.persisted_observation')
    if seed['phase']:
        expected = original['phases'][seed['phase']['id']]['states'][seed['source_state']]
        exact(meaning(expected), meaning(observation), case + '.original')
    # Read-only reopen and read/no-op must leave every original store byte intact.
    raw_before = sha(path)
    lane.sets(retain=False)
    assert sha(path) == raw_before and session.history.rows == {}
    assert session.graph.migration_pending is (case == 'R3')
    if case == 'R3':
        fit = lane.fits['A']
        current = session._records[fit]['implant_source']
        lane.feature('set_implant_source', dict(fit_id=fit, fit_revision=session._revisions[fit], source=current), fit)
        assert session.graph.migration_pending and sha(path) == raw_before and session.history.rows == {}
        lane.sets('create', dict(name='First authorized v6 edit'), retain=False)
        assert not session.graph.migration_pending and json.loads(session._store.current.payload)['version'] == 6
        exact({key: value for key, value in expected_authority.items() if key != 'implant_sets'},
              {key: value for key, value in session.graph._state.items() if key != 'implant_sets'},
              case + '.migration_preserves_all_other_authority')
        after = lane.observe(seed['phase'], graph=True)
        exact(observation, after, case + '.migration_preserves_fits')
    else:
        assert sha(path) == seed['store_sha256']
    evidence.write(case + '-reopen.json', dict(ok=True, case=case, source_state=seed['source_state'],
        history_empty_on_open=True, observation=observation, read_preserved_bytes=True,
        migration_checked=case == 'R3', before_store_sha256=seed['store_sha256'], after_store_sha256=sha(path),
        imported_sources=verify_imports()))
    lane.close()


if __name__ == '__main__':
    main()
