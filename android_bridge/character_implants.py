"""C07.2 character implant records and exact EOS reconstruction.

The ledger owns row identities. Each fit materializes independent character
objects; local inspector identity remains exclusively in inspection_identity.
"""
from copy import deepcopy
import re
import uuid
import unicodedata


def _require(ok, message):
    if not ok:
        raise ValueError(message)


class IneligibleImplant(ValueError):
    pass


def row_id(value):
    _require(type(value) is str and re.fullmatch('[0-9a-f]{32}', value), 'Invalid character implant identity')
    return value


def catalogue(identity):
    _require(type(identity) is int and 1 <= identity < 2**31, 'Invalid implant item identity')
    import eos.db
    from eos.saveddata.implant import Implant
    item = eos.db.getItem(identity)
    if item is None or not item.isImplant: raise IneligibleImplant('Choose a genuine implant')
    _require(type(item.name) is str and bool(item.name) and all(unicodedata.category(c) != 'Cc' and not 0xD800 <= ord(c) <= 0xDFFF for c in item.name), 'Invalid pinned implant name')
    slot = Implant(item).slot
    if type(slot) is not int or not 1 <= slot < 2**31: raise IneligibleImplant('Invalid implant slot')
    return item, slot


def validate(rows, *, display=False, metadata=True):
    _require(type(rows) is list, 'Invalid character implant collection')
    ids, slots = set(), set()
    for row in rows:
        _require(type(row) is dict and set(row) == ({'implant_id', 'item_id', 'slot', 'active'} | ({'name'} if display else set())),
                 'Invalid character implant fields')
        row_id(row['implant_id'])
        _require(row['implant_id'] not in ids, 'Duplicate character implant identity')
        _require(type(row['item_id']) is int and 1 <= row['item_id'] < 2**31 and
                 type(row['slot']) is int and 1 <= row['slot'] < 2**31 and type(row['active']) is bool,
                 'Invalid character implant values')
        _require(row['slot'] not in slots, 'Duplicate character implant slot')
        ids.add(row['implant_id']); slots.add(row['slot'])
        if display:
            _require(type(row['name']) is str and bool(row['name']) and all(unicodedata.category(c) != 'Cc' and not 0xD800 <= ord(c) <= 0xDFFF for c in row['name']),
                     'Invalid character implant name')
        if metadata:
            item, slot = catalogue(row['item_id'])
            _require(slot == row['slot'] and (not display or item.name == row['name']), 'Character implant metadata differs')
    return rows


def display(rows):
    validate(rows)
    return [dict(row, name=catalogue(row['item_id'])[0].name) for row in rows]


def copied(rows):
    return [dict(row, implant_id=uuid.uuid4().hex) for row in rows]


def restore(fit, record):
    """Populate both lists before selecting source; caller calculates afterwards."""
    if 'implant_source' not in record:
        return
    from eos.const import ImplantLocation
    from eos.saveddata.implant import Implant
    validate(record['character_implants'], display=True)
    _require(record['implant_source'] in ('FIT', 'CHARACTER'), 'Invalid implant source')
    _require(not fit.character.implants, 'Character implants already materialized')
    for row in record['character_implants']:
        obj = Implant(catalogue(row['item_id'])[0])
        obj.active = row['active']
        fit.character.implants.append(obj)
        _require(obj in fit.character.implants, 'EOS rejected character implant')
    fit._offline_character_implants = deepcopy(record['character_implants'])
    fit.implantLocation = ImplantLocation[record['implant_source']]


def capture(fit):
    from eos.const import ImplantLocation
    rows = getattr(fit, '_offline_character_implants', None)
    if rows is None:
        _require(not fit.character.implants and fit.implantLocation == ImplantLocation.FIT,
                 'Unowned character implant inputs')
        return {}
    validate(rows, display=True)
    live = [(obj.itemID, obj.item.name, obj.slot, obj.active) for obj in fit.character.implants]
    expected = [(r['item_id'], r['name'], r['slot'], r['active']) for r in rows]
    _require(live == expected, 'Character implant inputs changed outside their profile')
    return dict(implant_source=ImplantLocation(fit.implantLocation).name, character_implants=deepcopy(rows))


def refresh_order(fit):
    from eos.const import ImplantLocation
    return (tuple(obj.itemID for obj in fit.implants), tuple(obj.itemID for obj in fit.character.implants),
            ImplantLocation(fit.implantLocation).name)


def restore_refresh_order(fit, saved):
    from eos.const import ImplantLocation
    for rows, order in ((fit.implants, saved[0]), (fit.character.implants, saved[1])):
        current = [obj.itemID for obj in rows]
        _require(len(current) == len(order) and len(set(current)) == len(current) and set(current) == set(order),
                 'Implant membership changed during refresh')
        ordinal = {key: index for index, key in enumerate(order)}
        list.sort(rows, key=lambda obj: ordinal[obj.itemID])
    _require(ImplantLocation(fit.implantLocation).name == saved[2], 'Implant source changed during refresh')


def catalog_response(engine, dataset):
    """Read-only metadata for no-fit discovery and native authority validation."""
    from android_bridge.contract import _json
    code = 'catalogue_unavailable'
    try:
        engine._check_thread()
        _require(type(dataset) is str and re.fullmatch('[0-9a-f]{64}', dataset), 'Dataset unavailable')
        import eos.db
        rows = []
        for value in eos.db.getItemsByCategory('Implant'):
            if not value.isImplant:
                continue
            # Expected ineligibility is the same rule used by authority. An
            # unexpected metadata failure remains a complete read failure.
            try:
                item, slot = catalogue(value.ID)
            except IneligibleImplant:
                continue
            rows.append(dict(item_id=item.ID, name=item.name, slot=slot))
        rows.sort(key=lambda row: row['item_id'])
        _require(len({row['item_id'] for row in rows}) == len(rows), 'Duplicate implant catalogue identity')
        result = dict(version=1, ok=True, dataset_sha256=dataset, implants=rows, error=None)
        if len(_json(result).encode('utf-8')) > 524288:
            code = 'response_size'
            raise ValueError('Implant catalogue exceeds bounded response size')
        return result
    except Exception:
        valid_dataset = dataset if type(dataset) is str and re.fullmatch('[0-9a-f]{64}', dataset) else None
        return dict(version=1, ok=False, dataset_sha256=valid_dataset, implants=[],
                    error=dict(code=code, message='Implant catalogue exceeds bounded response size' if code == 'response_size' else 'Implant catalogue could not be loaded'))
