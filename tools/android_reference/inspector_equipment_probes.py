#!/usr/bin/env python3
"""Original booster duration and absent legacy-family presentation witnesses.

Legacy objects are explicit synthetic test inputs, never production game types.
Booster inputs are the complete published pinned catalogue, using real EOS models.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, bootstrap, compare, logical_database_digest, validate_source
from tools.android_reference.inspector_equipment_coverage import observe_returns


class Module:
    """Read-only test double for branches whose published game types are absent."""
    def __init__(self, group, values, features=None):
        self.features = features or {}
        self.item = (None if self.features.get('no_item') else SimpleNamespace(group=SimpleNamespace(name=group),
                     category=SimpleNamespace(name=self.features.get('category', 'Module')),
                     effects=dict.fromkeys(self.features.get('effects', []))))
        self.values = values
        self.charge = None if 'charge_group' not in self.features else SimpleNamespace(group=SimpleNamespace(name=self.features['charge_group']))
        for name in ('numShots', 'rawCycleTime', 'hpBeforeReload', 'amount', 'capUse', 'falloff', 'maxRange'):
            if name in self.features: setattr(self, name, self.features[name])
    def getModifiedItemAttr(self, name, default=None): return self.values.get(name, default)
    def getModifiedChargeAttr(self, name, default=None): return self.features.get('charge_values', {}).get(name, default)
    def getCycleParameters(self):
        return None if self.features.get('cycle_time') is None else SimpleNamespace(averageTime=self.features['cycle_time'])
    def getSpoolData(self, *args, **kwargs): return self.features.get('spool', [0, 0])
    def getMiningYPS(self, **kwargs): return self.features.get('mining_yps', 0)
    def getMiningDPS(self, **kwargs): return self.features.get('mining_dps', 0)
    def getRemoteReps(self, **kwargs):
        return SimpleNamespace(**{name: self.features.get('remote_reps', {}).get(name, 0) for name in ('shield', 'armor', 'hull', 'capacitor')})


def conditional_inputs():
    rows = []
    def add(group, name, values=None, **features):
        rows.append(dict(group=group, name=name, values=values or {}, features=features, expected_error=None))
    add('No item', 'missing item', no_item=True)
    for group in ('Precursor Weapon', 'Vorton Projector', 'Salvager', 'Data Miners', 'Damage Control',
                  'Warp Scrambler', 'Stasis Web', 'Target Painter', 'Weapon Disruptor', 'Gyrostabilizer',
                  'Drone Damage Modules', 'Remote Sensor Booster', 'Cloaking Device', 'Shield Transporter',
                  'Remote Armor Repairer', 'Remote Hull Repairer', 'Electronic Warfare Drone',
                  'Energy Neutralizer Drone', 'Siege Module', 'Cargo Scanner', 'Command Burst'):
        add(group, 'missing values')
    add('Energy Neutralizer', 'missing cycle')
    add('Energy Neutralizer', 'zero cycle', dict(energyNeutralizerAmount=100), cycle_time=0)
    add('Energy Nosferatu', 'missing cycle')
    add('Energy Nosferatu', 'zero cycle', dict(powerTransferAmount=100), cycle_time=0)
    add('Sensor Dampener', 'missing values')
    add('Sensor Dampener', 'zero values', dict(maxTargetRangeBonus=0, scanResolutionBonus=0))
    add('Warp Scrambler', 'nonzero strength', dict(warpScrambleStrength=2))
    add('Damage Control', 'assault duration', dict(duration=25000))
    for group in ('Mutadaptive Remote Armor Repairer', 'Remote Shield Booster', 'Remote Capacitor Transmitter'):
        add(group, 'zero repairs')
    for group, kind in (('Ancillary Remote Armor Repairer', 'armor'), ('Ancillary Remote Shield Booster', 'shield')):
        add(group, 'uncharged repairs', numShots=0, rawCycleTime=0, hpBeforeReload=0, remote_reps={kind: 12.5})
    add('Electronic Warfare Drone', 'zero ECM', dict.fromkeys(('scanGravimetricStrengthBonus', 'scanLadarStrengthBonus',
        'scanRadarStrengthBonus', 'scanMagnetometricStrengthBonus'), 0))
    add('Cloaking Device', 'zero delay', dict(cloakingTargetingDelay=0))
    add('Subsystem', 'positive slots', dict(hiSlotModifier=2, medSlotModifier=1, lowSlotModifier=3), category='Subsystem')
    for group in ('Ancillary Armor Repairer', 'Ancillary Shield Booster', 'Capacitor Booster',
                  'Ancillary Remote Armor Repairer', 'Ancillary Remote Shield Booster'):
        add(group, 'no charges', numShots=0, rawCycleTime=0, hpBeforeReload=0)
        add(group, 'charged duration reload and multiplier',
            dict(reloadTime=60000, armorDamageAmount=200, shieldBonus=200, chargedArmorDamageMultiplier=3),
            numShots=8, rawCycleTime=5000, hpBeforeReload=400,
            charge_group='Test charge', charge_values=dict(capacitorBonus=200))
    add('Logistic Drone', 'zero repairs', amount=1)
    add('Mining Laser', 'zero mining')
    add('Mining Laser', 'zero drain', mining_yps=2, mining_dps=0)
    for group in ('Missile', 'Bomb', 'Scanner Probe', 'Unknown charge'):
        add('Charge launcher', 'missing ' + group, charge_group=group)
    add('Charge launcher', 'scanner probe', charge_group='Scanner Probe', charge_values=dict(baseSensorStrength=12.5, baseScanRange=4))
    add('Combat Drone', 'zero ECM effect', dict.fromkeys(('scanGravimetricStrengthBonus', 'scanLadarStrengthBonus',
        'scanRadarStrengthBonus', 'scanMagnetometricStrengthBonus'), 0), effects=['entityECMFalloff'])
    # The original ECM code calls max/min before checking None. Preserve its
    # rejection as an explicit source exception; never count it as a return hit.
    add('ECM', 'missing strength source exception')
    rows[-1]['expected_error'] = dict(type='TypeError', message="'>' not supported between instances of 'NoneType' and 'NoneType'")
    return rows


def legacy_inputs():
    rows = []
    def add(group, name, values): rows.append(dict(group=group, name=name, values=values))
    add('Ship Modifiers', 'empty', {})
    for values, label in (({}, 'missing'), ({'trackingSpeed': 0, 'optimalSigRadius': 40}, 'zero'),
                          ({'trackingSpeed': 0.2, 'optimalSigRadius': 40}, 'tracking')):
        add('Fighter Drone', label, values)
    for value in (None, 0, 40): add('Fighter Bomber', str(value), dict(optimalSigRadius=value))
    for values, label in (({}, 'missing'), ({'commandBonus': 0, 'commandBonusHidden': 0}, 'zero'),
                          ({'commandBonus': 12.5, 'commandBonusHidden': 7}, 'visible precedence'),
                          ({'commandBonus': 0, 'commandBonusHidden': 7}, 'hidden fallback')):
        add('Gang Coordinator', label, values)
    strengths = ('scanGravimetricStrengthPercent', 'scanLadarStrengthPercent',
                 'scanRadarStrengthPercent', 'scanMagnetometricStrengthPercent')
    for group in ('ECCM', 'Projected ECCM', 'Sensor Backup Array'):
        add(group, 'missing', {})
        add(group, 'zero', dict.fromkeys(strengths, 0))
        for strength in strengths:
            add(group, strength, {key: 25 if key == strength else 10 for key in strengths})
        add(group, 'all tied', dict.fromkeys(strengths, 25))
        add(group, 'grav radar tied', {key: 25 if key in (strengths[0], strengths[2]) else 10 for key in strengths})
    return rows


def inputs(database):
    import sqlite3
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        boosters = [dict(id=row[0], name=row[1]) for row in db.execute(
            "SELECT t.typeID,t.typeName FROM invtypes t JOIN invgroups g ON g.groupID=t.groupID "
            "WHERE g.name='Booster' AND t.published=1 ORDER BY t.typeID")]
        unit = db.execute("SELECT u.unitID,u.unitName,u.displayName FROM dgmattribs a JOIN dgmunits u ON u.unitID=a.unitID "
                          "WHERE a.attributeName='boosterDuration'").fetchone()
        if unit is None: raise ValueError('Missing original booster duration unit')
        mode = db.execute("SELECT t.typeID FROM invtypes t JOIN invgroups g ON g.groupID=t.groupID "
                          "WHERE g.name='Ship Modifiers' ORDER BY t.published DESC,t.typeID LIMIT 1").fetchone()
        if mode is None: raise ValueError('No original mode item for mode-column guards')
    return dict(legacy=legacy_inputs(), conditional=conditional_inputs(), boosters=boosters,
                booster_duration_unit=dict(id=unit[0], name=unit[1], display=unit[2]),
                columns=column_inputs(mode[0]))


def column_inputs(mode_id):
    rows = [dict(method=method, context='mode', mode_id=mode_id) for method in
            ('maxRange.py:getText', 'capacitorUse.py:getText', 'capacitorUse.py:getToolTip')]
    rows.append(dict(method='capacitorUse.py:getText', context='no_fit', value=12.5))
    for name in ('cpu', 'power', 'volume', 'arbitrary_configured_attribute'):
        for value in (None, 0, False, 12.345678, -12.345678, 123456789):
            for context in ('fitted', 'base', 'direct'):
                rows.append(dict(method='attributeDisplay.py:getText', context=context, name=name, value=value, amount=1))
    for amount in (0, 1, 5):
        rows.append(dict(method='attributeDisplay.py:getText', context='fitted', name='volume', value=12.5, amount=amount))
    for name in ('amount', 'amountActive', 'arbitrary_configured_property'):
        for value in (None, 0, False, 12.345678, -12.345678, 123456789):
            rows.append(dict(method='propertyDisplay.py:getText', context='property', name=name, value=value))
    return rows


def column_observer(methods, original):
    def observe(row, fit):
        from eos.saveddata.mode import Mode
        import eos.db
        method = methods[row['method']]
        selected_fit = None if row['context'] == 'no_fit' else fit
        view = SimpleNamespace(fit=selected_fit, fittingView=SimpleNamespace(getActiveFit=lambda: None if selected_fit is None else selected_fit.ID),
                               info=SimpleNamespace(name=row.get('name')), propertyName=row.get('name'), direct=row['context'] == 'direct',
                               directInfo={42: row.get('value')})
        if original:
            method.__globals__['Fit'] = SimpleNamespace(getInstance=lambda: SimpleNamespace(getFit=lambda identity: selected_fit))
        if row['context'] == 'mode': stuff = Mode(eos.db.getItem(row['mode_id']), owner=fit)
        elif row['context'] == 'no_fit': stuff = Module('Test module', {}, {'capUse': row['value']})
        elif row['context'] == 'fitted': stuff = Module('Test module', {row['name']: row['value']}, {'amount': row['amount']})
        elif row['context'] in ('base', 'direct'): stuff = SimpleNamespace(ID=42, getAttribute=lambda name: row['value'])
        else: stuff = SimpleNamespace(**{row['name']: row['value']})
        return observe_returns(lambda: method(view, stuff), {row['method']: method})
    return observe


def make_fit(original, engine=None):
    spec = json.loads((ROOT / 'tools/android_reference/fixtures/inspector-attributes.json').read_text())['cases'][0]['spec']
    spec = {**spec, 'name': 'Inspector booster duration probes', 'modules': [], 'drones': [],
            'fighters': [], 'cargo': [], 'environments': []}
    if not original: return engine.create_fit(spec)
    import eos.db
    from eos.const import ImplantLocation, FitSystemSecurity
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    fit = Fit(Ship(eos.db.getItem(spec['ship'])), name=spec['name'])
    fit.character = Character('Headless synthetic skills', defaultLevel=spec['skill_level'])
    fit.damagePattern = DamagePattern(**spec['damage_pattern'])
    fit.factorReload = spec['factor_reload']; fit.targetProfile = None
    fit.implantLocation = ImplantLocation.FIT; fit.systemSecurity = FitSystemSecurity[spec['security']['system']]
    fit.pilotSecurity = spec['security']['pilot']; fit.ignoreRestrictions = False
    eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
    fit.calculateModifiedAttributes()
    return fit


def sample(request, fit, observe, observe_column):
    import eos.db
    from eos.saveddata.booster import Booster
    legacy = [dict(input=row, output=observe(Module(row['group'], row['values']), fit)) for row in request['legacy']]
    conditional = []
    for row in request['conditional']:
        try:
            output = observe(Module(row['group'], row['values'], row['features']), fit)
            conditional.append(dict(input=row, output=output, error=None))
        except (KeyboardInterrupt, SystemExit): raise
        except Exception as error:
            conditional.append(dict(input=row, output=None, error=dict(type=type(error).__name__, message=str(error))))
        compare(row['expected_error'], conditional[-1]['error'], row['group'] + '/' + row['name'] + '.declared_exception')
    boosters = []
    for row in request['boosters']:
        booster = Booster(eos.db.getItem(row['id']))
        fit.boosters.append(booster)
        states = []
        for active in (True, False):
            booster.active = active
            fit.clear(); fit.calculateModifiedAttributes()
            states.append(dict(active=active, duration=dict(value=booster.getModifiedItemAttr('boosterDuration'),
                               unit=request['booster_duration_unit']),
                               output=observe(booster, fit)))
        fit.boosters.remove(booster)
        fit.clear(); fit.calculateModifiedAttributes()
        boosters.append(dict(input=row, states=states))
    columns = [dict(input=row, output=observe_column(row, fit)) for row in request['columns']]
    return dict(legacy=legacy, conditional=conditional, boosters=boosters, columns=columns)


def coverage(result):
    path = ROOT / 'tools/android_reference/fixtures/inspector-equipment-paths.json'
    base = json.loads(path.read_text(encoding='utf-8'))
    witnessed = set(base['coverage']['witnessed_return_ids'])
    witnessed.update(identity for row in result['legacy'] for mode in row['output'] for identity in mode['returns'])
    witnessed.update(identity for row in result['boosters'] for state in row['states'] for mode in state['output'] for identity in mode['returns'])
    witnessed.update(identity for row in result['conditional'] if row['output'] is not None for mode in row['output'] for identity in mode['returns'])
    witnessed.update(identity for row in result['columns'] for identity in row['output']['returns'])
    required = set(base['coverage']['required_return_ids'])
    if not witnessed <= required: raise ValueError('Probe returned an unknown original return identity')
    return dict(base_fixture_sha256=hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest(),
                required_return_ids=sorted(required), witnessed_return_ids=sorted(witnessed), remaining_return_ids=sorted(required - witnessed))


def export(source, database):
    validate_source(source)
    config = bootstrap(source, database); config.gamedataCache = False
    import config as desktop_config
    desktop_config.pyfaPath = str(source)
    from tools.android_reference.inspector_equipment_oracle import load
    observe = load(source)
    request = inputs(database)
    result = sample(request, make_fit(True), lambda stuff, fit: [
        observe_returns(lambda: observe(stuff, fit, effective), observe.methods) for effective in (False, True)],
        column_observer(observe.methods, True))
    if any(name.startswith('android_bridge') for name in sys.modules): raise ValueError('Android imported into original probes')
    for name, module in sys.modules.items():
        if name.split('.')[0] in ('eos', 'service', 'gui', 'config') and getattr(module, '__file__', None):
            if not Path(module.__file__).resolve().is_relative_to(source): raise ValueError('Original probe imported outside pinned source: ' + name)
    return dict(schema=1, sourceCommit=SOURCE_COMMIT, databaseLogicalSha256=logical_database_digest(database),
                eos_settings=dict(config.settings), inputs=request, results=result, coverage=coverage(result))


def verify(database, fixture):
    compare(SOURCE_COMMIT, fixture['sourceCommit']); compare(logical_database_digest(database), fixture['databaseLogicalSha256'])
    request = inputs(database); compare(request, fixture['inputs'])
    from tools.android_headless.check import NoDesktop
    sys.meta_path.insert(0, NoDesktop())
    from android_bridge import HeadlessEngine
    engine = HeadlessEngine(database); compare(engine.settings, fixture['eos_settings'])
    from tools.android_reference.inspector_equipment_coverage import android_observe
    from android_bridge.inspection_equipment import EquipmentColumns
    column_methods = {name: getattr(EquipmentColumns, method) for name, method in (
        ('maxRange.py:getText', 'range_text'), ('capacitorUse.py:getText', 'capacitor_text'),
        ('capacitorUse.py:getToolTip', 'capacitor_tooltip'), ('attributeDisplay.py:getText', 'attribute_text'),
        ('propertyDisplay.py:getText', 'property_text'))}
    result = sample(request, make_fit(False, engine), lambda stuff, fit: android_observe(stuff, stuff.item, fit),
                    column_observer(column_methods, False))
    compare(fixture['results'], result)
    compare(fixture['coverage'], coverage(result))
    from android_bridge.inspection import stack
    stack_count = 0
    for row in fixture['results']['columns']:
        request_row = row['input']
        if request_row['method'] != 'attributeDisplay.py:getText' or request_row.get('name') != 'volume' or request_row['context'] != 'fitted':
            continue
        value, amount = request_row['value'], request_row['amount']
        if type(value) is bool: continue  # Boolean is a configurable-column witness, not a physical volume.
        owner = Module('Test volume stack', {'volume': value}, {'amount': amount})
        actual_stack = stack(owner, owner.item)
        compare(value, actual_stack['volume'])
        compare(None if value is None else value * amount, actual_stack['total_volume'])
        compare('m³', actual_stack['unit'])
        if value is None: compare(None, actual_stack['display'])
        elif value != 0: compare(row['output']['value'], actual_stack['display'])
        else: compare('0 m³' + ('' if amount == 1 else ' (0 m³)'), actual_stack['display'])
        stack_count += 1
    witnessed = {identity for row in result['legacy'] for mode in row['output'] for identity in mode['returns']}
    witnessed.update(identity for row in result['boosters'] for state in row['states'] for mode in state['output'] for identity in mode['returns'])
    witnessed.update(identity for row in result['conditional'] if row['output'] is not None for mode in row['output'] for identity in mode['returns'])
    print(f'PASS {len(result["legacy"])} explicit legacy probes; {len(result["boosters"])} complete published boosters active/inactive; '
          f'{len(witnessed)} original return witnesses across raw/EHP probes')
    errors = [dict(input=row['input']['group'] + '/' + row['input']['name'], error=row['error']) for row in result['conditional'] if row['error'] is not None]
    print(f'{len(result["conditional"])} conditional probes; {len(errors)} explicit original exceptions (not return passes)')
    print(json.dumps(errors))
    print(f'{len(result["columns"])} exact configurable/mode/no-selected-fit column witnesses')
    print(f'{stack_count} worker volume/stack witnesses preserve original display and explicit missing/zero distinctions')
    print(f'Combined coverage: {len(fixture["coverage"]["witnessed_return_ids"])}/'
          f'{len(fixture["coverage"]["required_return_ids"])} returns; '
          f'{len(fixture["coverage"]["remaining_return_ids"])} explicitly outstanding')


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
        print(f'Exported {len(result["inputs"]["legacy"])} legacy and {len(result["inputs"]["boosters"])} published booster probes')
    else: verify(database, json.loads(args.fixture.read_text(encoding='utf-8')))


if __name__ == '__main__': main()
