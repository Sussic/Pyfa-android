"""C09.1 local spool-cycle inputs and source-backed menu details.

GPL-3.0-or-later; Pyfa contributors, see LICENSE. Menu choice selection is
adapted from gui/builtinContextMenus/moduleSpool.py; EOS owns spool calculations.
"""
import math
GROUPS = frozenset(('Precursor Weapon', 'Mutadaptive Remote Armor Repairer'))


def validate(value):
    if type(value) is not int or not 0 <= value <= 2**31 - 1:
        raise ValueError('Spool cycles must be a nonnegative integer')


def restore(module, record):
    if 'spool_cycles' not in record:
        return
    validate(record['spool_cycles'])
    if module.item.group.name not in GROUPS:
        raise ValueError('This module does not support spool-cycle overrides')
    from eos.const import SpoolType
    module.spoolType = SpoolType.CYCLES
    module.spoolAmount = record['spool_cycles']


def capture(module):
    if module.spoolType is None and module.spoolAmount is None:
        return {}
    from eos.const import SpoolType
    if module.spoolType != SpoolType.CYCLES:
        raise ValueError('This editor cannot save a non-cycle spool override')
    # EOS maps spoolAmount to Float; an ORM refresh returns 0.0 for input 0.
    # Canonicalize exact integral values only, never round fractional state.
    amount = module.spoolAmount
    if type(amount) is float and math.isfinite(amount) and amount.is_integer():
        amount = int(amount)
    validate(amount)
    if module.item.group.name not in GROUPS:
        raise ValueError('This module does not support spool-cycle overrides')
    return dict(spool_cycles=amount)


def find_cycles(val1, val2):
    # Original nested findCycles body, retaining its integer step selection.
    maxSteps = 20
    valDiff = val2 - val1
    valScale = valDiff / maxSteps
    minStep = math.ceil(round(valScale, 9))
    maxStep = math.floor(round(valDiff / 4, 9))
    for currentStep in range(minStep, maxStep + 1):
        if valDiff % currentStep == 0:
            return set(range(val1, val2 + currentStep, currentStep))
    else:
        cycles = set()
        while val2 >= val1:
            cycles.add(val1)
            cycles.add(val2)
            val1 += minStep
            val2 -= minStep
        return cycles


def row(fit, module, index):
    from eos.const import SpoolType
    from eos.utils.spoolSupport import SpoolOptions
    import eos.config
    from .inspection_identity import identity
    default = eos.config.settings['globalDefaultSpoolupPercentage']
    values = dict(current=module.getSpoolData(SpoolOptions(SpoolType.SPOOL_SCALE, default, False)),
                  default=module.getSpoolData(SpoolOptions(SpoolType.SPOOL_SCALE, default, True)),
                  minimum=module.getSpoolData(SpoolOptions(SpoolType.SPOOL_SCALE, 0, True)),
                  maximum=module.getSpoolData(SpoolOptions(SpoolType.SPOOL_SCALE, 1, True)))
    for cycles, seconds in values.values():
        validate(cycles)
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Spool time is unavailable')
    low, high = values['minimum'][0], values['maximum'][0]
    # The desktop choice loop assumes a nonempty range. Reject an unavailable
    # or pathological source result rather than divide by zero or block the UI.
    if not low < high <= 100000:
        raise ValueError('Spool cycle range is unavailable or exceeds the bounded editor')
    explicit = capture(module).get('spool_cycles')
    choices = find_cycles(low, high) | {values['current'][0]}
    if explicit is None:
        choices.add(values['default'][0])
    result = dict(index=index, object_key=identity(fit, module), item_id=module.itemID,
                  name=module.item.name, override_cycles=explicit, choices=sorted(choices))
    for label, (cycles, seconds) in values.items():
        result[label + '_cycles'] = cycles
        result[label + '_seconds'] = seconds
    return result


def details(engine, fit):
    engine._check_fit(fit)
    if not fit.calculated:
        fit.calculateModifiedAttributes()
    return dict(modules=[row(fit, module, index) for index, module in enumerate(fit.modules)
                         if not module.isEmpty and module.item.group.name in GROUPS])


def change(engine, fit, position, cycles):
    from .fitting import _position, _fill
    from eos.const import SpoolType
    engine._check_fit(fit)
    module = _position(fit, position, occupied=True)
    if module.item.group.name not in GROUPS:
        raise ValueError('Choose a supported spool module')
    if cycles is not None:
        validate(cycles)
        if cycles not in row(fit, module, position)['choices']:
            raise ValueError('Choose one of the source spool-cycle options')
    module.spoolType = None if cycles is None else SpoolType.CYCLES
    module.spoolAmount = cycles
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    _fill(fit)
