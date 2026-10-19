"""Read-only inspector diagnostics on the existing serialized engine worker."""
from functools import cache


@cache
def _equipment_codes():
    """Immutable code metadata; avoid decoding all methods for every target."""
    import dis
    from android_bridge.inspection_equipment import EquipmentColumns
    methods = {name: getattr(EquipmentColumns, method) for name, method in (
        ('misc.py:__getData', 'misc'), ('maxRange.py:getText', 'range_text'),
        ('maxRange.py:getToolTip', 'range_tooltip'), ('capacitorUse.py:getText', 'capacitor_text'),
        ('capacitorUse.py:getToolTip', 'capacitor_tooltip'), ('attributeDisplay.py:getText', 'attribute_text'),
        ('propertyDisplay.py:getText', 'property_text'))}
    return {method.__code__: (name, sorted({instruction.positions.lineno
             for instruction in dis.get_instructions(method) if instruction.opname == 'RETURN_VALUE'}))
             for name, method in methods.items()}


def observe_equipment_call(call, names=None):
    """Trace actual column returns, restoring the caller's trace even on error."""
    import sys
    codes = _equipment_codes()
    if names is not None:
        codes = {code: info for code, info in codes.items() if info[0] in names}
    seen, last_line = set(), {}
    def trace(frame, event, arg):
        if frame.f_code in codes:
            if event == 'line': last_line[id(frame)] = frame.f_lineno
            elif event == 'return':
                name, lines = codes[frame.f_code]
                line = last_line.pop(id(frame), None)
                if line in lines: seen.add(name + ':' + str(lines.index(line)))
        return trace
    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        value = call()
    finally:
        sys.settrace(previous)
    return dict(value=value, returns=sorted(seen))


def equipment_observations(stuff, fit):
    from android_bridge.inspection import equipment
    return [observe_equipment_call(lambda: equipment(stuff, fit, effective))
            for effective in (False, True)]


def equipment_witnesses(engine, fit, selection):
    """Record real equipment returns without reading desktop/source files."""
    from android_bridge.inspection import target
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    stuff, item, charge = target(engine, fit, selection)
    codes = _equipment_codes()
    return dict(definitions={name: len(lines) for name, lines in codes.values()},
                observations=equipment_observations(stuff, fit))


def unit_witnesses(samples):
    """Exercise the inspector formatter with inputs, never reference expectations."""
    import math
    from types import SimpleNamespace
    import eos.db
    from eos.gamedata import Unit
    from android_bridge.inspection import _formatted

    if type(samples) is not list:
        raise ValueError('Unit samples must be a list')
    units = {unit.ID: unit for unit in eos.db.get_gamedata_session().query(Unit).order_by(Unit.ID).all()}
    def metadata(unit):
        return dict(id=unit.ID, name=unit.name, display=unit.displayName)
    witnesses = []
    for sample in samples:
        if type(sample) is not dict or set(sample) != {'unit_id', 'value'}:
            raise ValueError('Invalid unit sample fields')
        identity, value = sample['unit_id'], sample['value']
        if type(identity) is not int or identity not in units:
            raise ValueError('Unknown unit identity')
        if type(value) not in (int, float, bool) or not math.isfinite(value):
            raise ValueError('Unit sample must be a finite number or Boolean')
        unit = units[identity]
        witnesses.append(dict(unit=metadata(unit), value=value,
                              formatted=_formatted(value, SimpleNamespace(unit=unit))))
    return dict(units=[metadata(unit) for unit in units.values()], witnesses=witnesses)


def sql_roles(session, fit_id, complete=False):
    from sqlalchemy import select
    from eos.db.saveddata.fit import fits_table
    from eos.db.saveddata.module import modules_table
    from eos.db.saveddata.drone import drones_table
    from eos.db.saveddata.fighter import fighters_table

    def rows(table, columns, order, fit=False):
        identity = table.c.ID if fit else table.c.fitID
        query = select([table.c[name] for name in columns]).where(identity == fit_id)
        if not fit: query = query.where(table.c.projected == False)
        return [dict(row) for row in session.execute(query.order_by(table.c[order])).fetchall()]
    result = dict(
        fit=rows(fits_table, ['ID', 'name', 'shipID'], 'ID', fit=True),
        modules=rows(modules_table, ['ID', 'fitID', 'itemID', 'chargeID', 'position'], 'position'),
        drones=rows(drones_table, ['groupID', 'fitID', 'itemID', 'amount', 'amountActive'], 'groupID'),
        fighters=rows(fighters_table, ['groupID', 'fitID', 'itemID', 'amount', 'active'], 'groupID'))
    # SQLAlchemy's Boolean column decoder wraps SQLite's original 0/1 storage.
    # This diagnostic reports the raw SQL representation used by the oracle.
    for fighter in result['fighters']:
        if fighter['active'] is not None: fighter['active'] = int(fighter['active'])
    if len(result['fit']) != 1: raise ValueError('Missing or ambiguous SQL fit identity')
    if complete:
        # Raw SQLite membership avoids attribute getters and preserves original
        # Boolean storage values. Keep the inherited four-table contract intact.
        from sqlalchemy import text
        def raw(query):
            return [dict(row) for row in session.execute(text(query), {'fit_id': fit_id})]
        result.update(
            cargo=raw('SELECT ID, fitID, itemID, amount FROM cargo WHERE fitID=:fit_id ORDER BY ID'),
            implants=raw('SELECT i.ID, i.itemID, i.active FROM implants i JOIN fitImplants f ON f.implantID=i.ID WHERE f.fitID=:fit_id ORDER BY i.ID'),
            boosters=raw('SELECT ID, fitID, itemID, active FROM boosters WHERE fitID=:fit_id ORDER BY ID'),
            booster_side_effects=raw('SELECT s.boosterID, s.effectID, s.active FROM boosterSideEffects s JOIN boosters b ON b.ID=s.boosterID WHERE b.fitID=:fit_id ORDER BY s.boosterID,s.effectID'),
            mode=raw('SELECT modeID FROM fits WHERE ID=:fit_id'))
    return result
