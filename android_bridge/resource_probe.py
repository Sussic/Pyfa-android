"""Real provisional EOS resource inputs for isolated diagnostics, never saved fits.

Some original over-hardpoint states cannot be seeded through new-fit creation.
Fighter editing/persistence is C05. This probe constructs those real EOS inputs
without changing the accepted bridge operation or durable input contract.
Android's entry point must require an ephemeral engine process before calling it.
"""
from .engine import _keys, _integer
from .resources import details


def run(engine, spec, fighters):
    engine._check_thread()
    if type(fighters) is not list:
        raise ValueError('Fighter diagnostic inputs must be a list')
    # Validate all supported declarative inputs normally; modules are then placed
    # directly as in the original desktop diagnostic, including invalid capacity.
    fit = engine.create_fit({**spec, 'modules': []})
    from eos.const import FittingModuleState
    from eos.saveddata.module import Module
    from eos.saveddata.fighter import Fighter
    import eos.db
    for row in spec['modules']:
        _keys(row, ('name','state'), ('charge',))
        module = Module(engine._item(row['name']))
        state = FittingModuleState[row['state']]
        if not module.isValidState(state): raise ValueError('Invalid diagnostic module state')
        module.state = state
        if row.get('charge') is not None:
            charge = engine._item(row['charge'])
            if not module.isValidCharge(charge): raise ValueError('Invalid diagnostic charge')
            module.charge = charge
        fit.modules.append(module)
    for row in fighters:
        _keys(row, ('name','amount','active'));_integer(row['amount'],1,2**31-1)
        if type(row['active']) is not bool: raise ValueError('Invalid fighter activity')
        fighter = Fighter(engine._item(row['name']))
        fighter.amount, fighter.active = row['amount'], row['active']
        fit.fighters.append(fighter)
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    return details(engine,fit)['resources']
