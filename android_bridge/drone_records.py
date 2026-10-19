"""Lossless existing-drone state; this exposes no mutation creation/edit action."""
import math


def validate(row):
    from .engine import _integer, _keys
    _keys(row, ('name', 'amount', 'active'), ('mutation',))
    if type(row['name']) is not str or not row['name']:
        raise ValueError('Invalid saved drone name')
    _integer(row['amount'], 1, 2**31 - 1)
    _integer(row['active'], 0, row['amount'])
    if 'mutation' not in row:
        return
    value = row['mutation']
    _keys(value, ('base_item_id', 'mutaplasmid_id', 'attributes'))
    _integer(value['base_item_id'], 1, 2**31 - 1)
    _integer(value['mutaplasmid_id'], 1, 2**31 - 1)
    if type(value['attributes']) is not list or not value['attributes']:
        raise ValueError('Saved drone mutation requires its complete attributes')
    ids = []
    for attr in value['attributes']:
        _keys(attr, ('attribute_id', 'value'))
        _integer(attr['attribute_id'], 1, 2**31 - 1)
        if type(attr['value']) not in (int, float) or not math.isfinite(attr['value']):
            raise ValueError('Invalid saved mutation value')
        ids.append(attr['attribute_id'])
    if ids != sorted(set(ids)):
        raise ValueError('Saved mutation attributes must be unique and ordered')


def capture(drone):
    row = dict(name=drone.item.name, amount=drone.amount, active=drone.amountActive)
    if drone.isMutated:
        row['mutation'] = dict(base_item_id=drone.baseItemID, mutaplasmid_id=drone.mutaplasmidID,
            attributes=[dict(attribute_id=key, value=mutator.value)
                        for key,mutator in sorted(drone.mutators.items())])
    validate(row)
    return row


def restore(engine, row):
    validate(row)
    import eos.db
    from eos.saveddata.drone import Drone
    item = engine._item(row['name'])
    if 'mutation' in row:
        value = row['mutation']
        base = eos.db.getItem(value['base_item_id'])
        mutaplasmid = eos.db.getDynamicItem(value['mutaplasmid_id'])
        from eos.db.gamedata.dynamicAttributes import dynamicApplicable_table
        compatible = eos.db.get_gamedata_session().query(dynamicApplicable_table).filter(
            dynamicApplicable_table.c.typeID == value['mutaplasmid_id'],
            dynamicApplicable_table.c.applicableTypeID == value['base_item_id']).first()
        if (base is None or mutaplasmid is None or compatible is None or
                mutaplasmid.resultingItem.ID != item.ID):
            raise ValueError('Saved mutation type, base or mutaplasmid is incompatible')
        drone = Drone(item, baseItem=base, mutaplasmid=mutaplasmid)
        if set(drone.mutators) != {attr['attribute_id'] for attr in value['attributes']}:
            raise ValueError('Saved mutation attributes differ from the dataset')
        for attr in value['attributes']:
            mutator = drone.mutators[attr['attribute_id']]
            mutator.value = attr['value']
            # EOS clamps out-of-range rolls. Preservation must reject rather
            # than silently alter stored inputs after a dataset change.
            if mutator.value != attr['value']:
                raise ValueError('Saved mutation value would be changed by EOS')
    else:
        drone = Drone(item)
    drone.amount, drone.amountActive = row['amount'], row['active']
    return drone
