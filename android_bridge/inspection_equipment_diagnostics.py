"""DEBUG-only input probes for original equipment columns; no oracle imports."""
from types import SimpleNamespace


class Module:
    """Explicit synthetic input for branches absent from the published catalogue."""
    def __init__(self, group, values, features=None):
        self.features = features or {}
        self.item = (None if self.features.get('no_item') else SimpleNamespace(
            group=SimpleNamespace(name=group),
            category=SimpleNamespace(name=self.features.get('category', 'Module')),
            effects=dict.fromkeys(self.features.get('effects', []))))
        self.values = values
        self.charge = (None if 'charge_group' not in self.features else
                       SimpleNamespace(group=SimpleNamespace(name=self.features['charge_group'])))
        for name in ('numShots', 'rawCycleTime', 'hpBeforeReload', 'amount', 'capUse', 'falloff', 'maxRange'):
            if name in self.features: setattr(self, name, self.features[name])

    def getModifiedItemAttr(self, name, default=None): return self.values.get(name, default)
    def getModifiedChargeAttr(self, name, default=None): return self.features.get('charge_values', {}).get(name, default)
    def getCycleParameters(self):
        value = self.features.get('cycle_time')
        return None if value is None else SimpleNamespace(averageTime=value)
    def getSpoolData(self, *args, **kwargs): return self.features.get('spool', [0, 0])
    def getMiningYPS(self, **kwargs): return self.features.get('mining_yps', 0)
    def getMiningDPS(self, **kwargs): return self.features.get('mining_dps', 0)
    def getRemoteReps(self, **kwargs):
        return SimpleNamespace(**{name: self.features.get('remote_reps', {}).get(name, 0)
                                  for name in ('shield', 'armor', 'hull', 'capacitor')})


def guard_domains(request):
    """Actual finite/missing column outputs; source proofs remain independent."""
    import math
    from .inspection_equipment import EquipmentColumns
    from .inspection_diagnostics import observe_equipment_call
    if type(request) is not list: raise ValueError('Guard domains must be a list')
    strengths = {'scanGravimetricStrengthBonus', 'scanLadarStrengthBonus',
                 'scanRadarStrengthBonus', 'scanMagnetometricStrengthBonus'}
    extras = ({'maxTargetRangeBonus', 'scanResolutionBonus'},
              {'falloffBonus', 'maxRangeBonus', 'trackingSpeedBonus'})
    for row in request:
        if type(row) is not dict or set(row) != {'group', 'values'} or type(row['values']) is not dict:
            raise ValueError('Invalid guard domain fields')
        names = set(row['values'])
        if not (row['group'] == 'ECM' and names == strengths or
                row['group'] == 'Electronic Warfare Drone' and any(names == strengths | extra for extra in extras)):
            raise ValueError('Unknown guard domain')
        if any(value is not None and (type(value) not in (int, float) or not math.isfinite(value))
               for value in row['values'].values()):
            raise ValueError('Guard values must be finite numeric or missing')
    results = []
    for row in request:
        stuff = Module(row['group'], row['values'])
        try:
            output = observe_equipment_call(lambda: EquipmentColumns.misc(None, stuff), {'misc.py:__getData'})
            output['value'] = None if output['value'] is None else list(output['value'])
            error = None
        except TypeError as failure:
            if None not in row['values'].values(): raise
            output, error = None, dict(type=type(failure).__name__, message=str(failure))
        results.append(dict(input=row, output=output, error=error))
    return results


def equipment_probes(engine, fit, request):
    """Consume inputs only; evaluate actual columns and bundled EOS models."""
    import eos.db
    from eos.saveddata.booster import Booster
    from eos.saveddata.mode import Mode
    from .inspection_equipment import EquipmentColumns
    from .inspection_diagnostics import equipment_observations, observe_equipment_call, _equipment_codes
    if type(request) is not dict or set(request) != {'legacy', 'conditional', 'boosters', 'columns'}:
        raise ValueError('Invalid equipment probe fields')
    for family in request.values():
        if type(family) is not list: raise ValueError('Equipment probes must be lists')
    for row in request['legacy']:
        if type(row) is not dict or set(row) != {'group', 'name', 'values'}:
            raise ValueError('Invalid legacy probe fields')
    for row in request['conditional']:
        if type(row) is not dict or set(row) != {'group', 'name', 'values', 'features'}:
            raise ValueError('Invalid conditional probe fields')
    for row in request['boosters']:
        if type(row) is not dict or set(row) != {'id', 'name'} or type(row['id']) is not int:
            raise ValueError('Invalid booster probe fields')
        item = eos.db.getItem(row['id'])
        if item is None or item.name != row['name'] or item.group.name != 'Booster':
            raise ValueError('Booster catalogue identity mismatch')
    column_methods = {name: getattr(EquipmentColumns, method) for name, method in (
        ('maxRange.py:getText', 'range_text'), ('capacitorUse.py:getText', 'capacitor_text'),
        ('capacitorUse.py:getToolTip', 'capacitor_tooltip'), ('attributeDisplay.py:getText', 'attribute_text'),
        ('propertyDisplay.py:getText', 'property_text'))}
    fields = {'mode': {'method', 'context', 'mode_id'}, 'no_fit': {'method', 'context', 'value'},
              'fitted': {'method', 'context', 'name', 'value', 'amount'},
              'base': {'method', 'context', 'name', 'value', 'amount'},
              'direct': {'method', 'context', 'name', 'value', 'amount'},
              'property': {'method', 'context', 'name', 'value'}}
    for row in request['columns']:
        if (type(row) is not dict or row.get('context') not in fields or
                set(row) != fields[row['context']] or row['method'] not in column_methods):
            raise ValueError('Invalid column probe fields')
    engine._check_fit(fit)
    if not fit.calculated: fit.calculateModifiedAttributes()
    legacy = [dict(input=row, output=equipment_observations(Module(row['group'], row['values']), fit))
              for row in request['legacy']]
    conditional = []
    for row in request['conditional']:
        try:
            output = equipment_observations(Module(row['group'], row['values'], row['features']), fit)
            conditional.append(dict(input=row, output=output, error=None))
        except (KeyboardInterrupt, SystemExit): raise
        except Exception as error:
            conditional.append(dict(input=row, output=None, error=dict(type=type(error).__name__, message=str(error))))
    unit = eos.db.getAttributeInfo('boosterDuration', eager='unit').unit
    unit_metadata = dict(id=unit.ID, name=unit.name, display=unit.displayName)
    boosters = []
    for row in request['boosters']:
        booster = Booster(eos.db.getItem(row['id']))
        fit.boosters.append(booster)
        states = []
        try:
            for active in (True, False):
                booster.active = active
                fit.clear(); fit.calculateModifiedAttributes()
                states.append(dict(active=active, duration=dict(value=booster.getModifiedItemAttr('boosterDuration'),
                                   unit=unit_metadata), output=equipment_observations(booster, fit)))
        finally:
            fit.boosters.remove(booster)
            fit.clear(); fit.calculateModifiedAttributes()
        boosters.append(dict(input=row, states=states))
    columns = []
    for row in request['columns']:
        selected_fit = None if row['context'] == 'no_fit' else fit
        view = SimpleNamespace(fit=selected_fit,
            fittingView=SimpleNamespace(getActiveFit=lambda: None if selected_fit is None else selected_fit.ID),
            info=SimpleNamespace(name=row.get('name')), propertyName=row.get('name'),
            direct=row['context'] == 'direct', directInfo={42: row.get('value')})
        if row['context'] == 'mode': stuff = Mode(eos.db.getItem(row['mode_id']), owner=fit)
        elif row['context'] == 'no_fit': stuff = Module('Test module', {}, {'capUse': row['value']})
        elif row['context'] == 'fitted': stuff = Module('Test module', {row['name']: row['value']}, {'amount': row['amount']})
        elif row['context'] in ('base', 'direct'): stuff = SimpleNamespace(ID=42, getAttribute=lambda name: row['value'])
        else: stuff = SimpleNamespace(**{row['name']: row['value']})
        method = column_methods[row['method']]
        columns.append(dict(input=row, output=observe_equipment_call(lambda: method(view, stuff), {row['method']})))
    return dict(definitions={name: len(lines) for name, lines in _equipment_codes().values()},
                results=dict(legacy=legacy, conditional=conditional, boosters=boosters, columns=columns))
