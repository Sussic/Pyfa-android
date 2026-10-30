"""C10 lossless local-module mutation inputs; EOS owns values and calculations."""
import math


def attributes(rows):
    if type(rows) is not list or not rows:
        raise ValueError('Provide every rolled attribute')
    ids = []
    for row in rows:
        if type(row) is not dict or set(row) != {'attribute_id', 'value'}:
            raise ValueError('Malformed rolled attribute')
        key, value = row['attribute_id'], row['value']
        if type(key) is not int or not 1 <= key <= 2**31 - 1:
            raise ValueError('Invalid rolled attribute identity')
        try:
            finite = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError('Rolled values must be finite numbers')
        ids.append(key)
    if ids != sorted(set(ids)):
        raise ValueError('Rolled attributes must be complete, unique and ordered')


def validate(value):
    if type(value) is not dict or set(value) != {'base_item_id', 'mutaplasmid_id', 'attributes'}:
        raise ValueError('Malformed saved module mutation')
    for key in ('base_item_id', 'mutaplasmid_id'):
        if type(value[key]) is not int or not 1 <= value[key] <= 2**31 - 1:
            raise ValueError('Invalid saved mutation identity')
    attributes(value['attributes'])


def capture(thing):
    if not thing.isMutated:
        return {}
    value = dict(base_item_id=thing.baseItemID, mutaplasmid_id=thing.mutaplasmidID,
        attributes=[dict(attribute_id=key, value=mutator.value)
                    for key, mutator in sorted(thing.mutators.items())])
    validate(value)
    return {'mutation': value}


def restore_module(engine, row):
    """Restore before state/charge/spool/RAH, without losing existing inputs."""
    import eos.db
    from eos.saveddata.module import Module
    from eos.db.gamedata.dynamicAttributes import dynamicApplicable_table
    value = row['mutation']
    validate(value)
    item = engine._item(row['name'])
    base = eos.db.getItem(value['base_item_id'])
    mutaplasmid = eos.db.getDynamicItem(value['mutaplasmid_id'])
    compatible = eos.db.get_gamedata_session().query(dynamicApplicable_table).filter(
        dynamicApplicable_table.c.typeID == value['mutaplasmid_id'],
        dynamicApplicable_table.c.applicableTypeID == value['base_item_id']).first()
    if (base is None or mutaplasmid is None or compatible is None or
            mutaplasmid.resultingItem.ID != item.ID):
        raise ValueError('Saved module type, base or mutaplasmid is incompatible')
    module = Module(item, baseItem=base, mutaplasmid=mutaplasmid)
    if set(module.mutators) != {row['attribute_id'] for row in value['attributes']}:
        raise ValueError('Saved module rolls differ from the dataset')
    for roll in value['attributes']:
        mutator = module.mutators[roll['attribute_id']]
        mutator.value = roll['value']
        if mutator.value != roll['value']:
            raise ValueError('Saved module roll would be changed by EOS')
    return module
