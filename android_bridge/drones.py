"""Worker-owned drone edits matching the pinned desktop local-drone commands.

Capacity/bandwidth overruns remain EOS resource warnings. The desktop command
checks drone.fits(), which enforces hull group restrictions, not free bay space.
Split/merge conserve active counts under the recorded F08.03 user decision.
"""
from copy import deepcopy


MAX_AMOUNT = 2**31 - 1
ORIGINAL_OPERATIONS = frozenset(('add_drone', 'add_drone_stack', 'set_drone_amount',
                        'remove_drones', 'toggle_drones', 'clone_drone'))
OPERATIONS = ORIGINAL_OPERATIONS | {'split_drone', 'merge_drones'}


def stack_amount(fit, item):
    # gui/fitCommands/helpers.py:droneStackLimit (pinned 8b04f3b2).
    hard_limit = max(5, fit.extraAttributes['maxActiveDrones'])
    release_limit = fit.getReleaseLimitForDrone(item)
    return int(min(hard_limit, release_limit if release_limit > 0 else hard_limit))


def _positions(fit, positions):
    from .engine import _integer
    if type(positions) is not list or not positions:
        raise ValueError('Choose drone stacks')
    for position in positions:
        _integer(position, 0, MAX_AMOUNT)
        if position >= len(fit.drones):
            raise ValueError('Drone stack was removed')
    if len(set(positions)) != len(positions):
        raise ValueError('Choose each drone stack once')
    return positions


def _append(fit, drone, ignore_restrictions=False):
    if not ignore_restrictions and not drone.fits(fit):
        raise ValueError('Drone does not fit this hull')
    fit.drones.append(drone)
    if drone not in fit.drones:
        raise ValueError('EOS rejected the drone')


def change(engine, fit, operation, arguments):
    engine._check_fit(fit)
    from .engine import _integer
    from .fitting import item, _fill
    from eos.saveddata.drone import Drone
    used = []
    if operation in ('add_drone', 'add_drone_stack'):
        selected = item(engine, arguments['item_id'])
        drone = Drone(selected)
        amount = (stack_amount(fit, selected) if operation == 'add_drone_stack'
                  else arguments['amount'])
        _integer(amount, 1, MAX_AMOUNT)
        limit = stack_amount(fit, selected)
        existing = next((d for d in fit.drones.find(selected) if d is not None
                         and d.amountActive == 0 and d.amount + amount <= limit), None)
        if existing is not None:
            existing.amount += amount
        else:
            drone.amount, drone.amountActive = amount, 0
            _append(fit, drone)
        used = [selected.ID]
    elif operation == 'set_drone_amount':
        position = _positions(fit, [arguments['position']])[0]
        amount = arguments['amount']
        _integer(amount, 0, MAX_AMOUNT)
        drone = fit.drones[position]
        if amount == 0:
            fit.drones.remove(drone)
        else:
            previous = drone.amount
            drone.amount = amount
            if drone.amountActive > 0:
                drone.amountActive = max(min(drone.amountActive + amount - previous, amount), 0)
    elif operation == 'remove_drones':
        positions = _positions(fit, arguments['positions'])
        amount = arguments['amount']
        _integer(amount, 1, MAX_AMOUNT)
        for position in sorted(positions, reverse=True):
            drone = fit.drones[position]
            used.append(drone.itemID)
            drone.amount = max(drone.amount - amount, 0)
            drone.amountActive = min(drone.amountActive, drone.amount)
            if drone.amount == 0:
                fit.drones.remove(drone)
    elif operation == 'toggle_drones':
        positions = list(arguments['positions'])
        if positions:
            _positions(fit, positions)
        main = _positions(fit, [arguments['main_position']])[0]
        if main not in positions:
            positions.append(main)
        deactivate = fit.drones[main].amountActive > 0
        for position in positions:
            drone = fit.drones[position]
            if deactivate:
                drone.amountActive = 0
            elif drone.amountActive == 0:
                drone.amountActive = drone.amount
    elif operation == 'clone_drone':
        position = _positions(fit, [arguments['position']])[0]
        # EOS deepcopy preserves the original type and rolled mutators. The
        # bridge owns transaction replay and assigns the clone a fresh identity.
        _append(fit, deepcopy(fit.drones[position]))
    elif operation == 'split_drone':
        position = _positions(fit, [arguments['position']])[0]
        drone = fit.drones[position]
        amount = arguments['amount']
        _integer(amount, 1, drone.amount - 1)
        moved_active = min(amount, drone.amountActive)
        remaining_active = drone.amountActive - moved_active
        separated = deepcopy(drone)
        separated.amount, separated.amountActive = amount, moved_active
        drone.amount -= amount
        drone.amountActive = remaining_active
        # Redistribute an existing stack even if an imported fit exceeds current
        # hull restrictions. Its stored/active totals and exact rolls do not grow.
        _append(fit, separated, ignore_restrictions=True)
    elif operation == 'merge_drones':
        source, destination = _positions(fit, [arguments['source_position'], arguments['destination_position']])
        src, dst = fit.drones[source], fit.drones[destination]
        from .drone_records import capture
        def identity(drone):
            row = capture(drone)
            return drone.itemID, row.get('mutation')
        if identity(src) != identity(dst):
            raise ValueError('Only identical drone types and mutation rolls can merge')
        amount, active = src.amount + dst.amount, src.amountActive + dst.amountActive
        _integer(amount, 1, MAX_AMOUNT)
        dst.amount, dst.amountActive = amount, active
        fit.drones.remove(src)
    else:
        raise ValueError('Unknown drone operation')
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
    _fill(fit)
    return used
