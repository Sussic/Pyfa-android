"""Choose actual pinned items for every original miscellaneous dispatch family."""
import ast
from copy import deepcopy
from pathlib import Path
import json
import sqlite3


def dispatch_items(source):
    import eos.db
    tree = ast.parse((Path(source) / 'gui/builtinViewColumns/misc.py').read_text(encoding='utf-8'))
    groups, effects = set(), set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if isinstance(node.left, ast.Name) and node.left.id == 'itemGroup':
            for comparator in node.comparators:
                groups.update(value.value for value in ast.walk(comparator)
                              if isinstance(value, ast.Constant) and isinstance(value.value, str))
        if any(isinstance(value, ast.Attribute) and isinstance(value.value, ast.Name)
               and value.value.id == 'item' and value.attr == 'effects' for value in node.comparators):
            if isinstance(node.left, ast.Constant) and isinstance(node.left.value, str):
                effects.add(node.left.value)
    from eos.gamedata import Item, Group
    items = eos.db.get_gamedata_session().query(Item).join(Group).filter(
        Group.name.in_(groups), Item.published.is_(True), Item.marketGroupID.isnot(None)).all()
    by_family = {}
    for item in sorted(items, key=lambda value: value.ID):
        signature = (item.group.name, tuple(sorted(set(item.effects) & effects)))
        by_family.setdefault(signature, item)
    absent = sorted(groups - {item.group.name for item in items})
    return list(by_family.values()), absent


def specifications(source, database, base, make_fit):
    """Select legal original EOS hull/item combinations, not adapter results."""
    import eos.db
    from eos.const import FittingModuleState
    from eos.saveddata.module import Module
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from eos.saveddata.citadel import Citadel
    items, absent = dispatch_items(source)
    hulls = ('Vexor', 'Dominix', 'Rifter', 'Caracal', 'Procurer', 'Rodiva', 'Vedmak',
             'Nighthawk', 'Orca', 'Rorqual', 'Revelation', 'Erebus', 'Avatar',
             'Leviathan', 'Ragnarok', 'Loki', 'Legion', 'Proteus', 'Tengu',
             'Astrahus', 'Fortizar', 'Keepstar', 'Raitaru', 'Sotiyo')
    catalog = json.loads((Path(__file__).with_name('fixtures') / 'catalog.json').read_text(encoding='utf-8'))
    hulls = tuple(dict.fromkeys((*hulls, *(row['name'] for row in catalog['hulls']))))
    eligibility = {}
    for hull in hulls:
        hull_item = eos.db.getItem(hull)
        eligibility[hull] = Fit(Ship(hull_item) if hull_item.category.name == 'Ship' else Citadel(hull_item))
    cases, unmatched = [], []
    for item in items:
        if item.category.name == 'Module' or item.category.name in ('Structure Module', 'Subsystem'):
            module = Module(item)
            state = module.getMaxState(proposedState=FittingModuleState.ACTIVE).name
            for hull in hulls:
                if not eligibility[hull].canFit(item):
                    continue
                spec = {**deepcopy(base), 'name': 'Inspector family: ' + item.name, 'ship': hull,
                        'modules': [dict(name=item.name, state=state)], 'drones': [], 'fighters': [],
                        'cargo': [], 'environments': []}
                try:
                    fit = make_fit(spec)
                except (ValueError, AssertionError):
                    continue
                if fit.canFit(item) and fit.fits and any(m.item == item for m in fit.modules):
                    cases.append(spec)
                    break
            else:
                unmatched.append(dict(id=item.ID, name=item.name, group=item.group.name,
                                      category=item.category.name, reason='No verified legal hull in candidate set'))
        elif item.category.name == 'Drone':
            spec = {**deepcopy(base), 'name': 'Inspector family: ' + item.name, 'ship': 'Dominix',
                    'modules': [], 'drones': [dict(name=item.name, amount=1, active=1)],
                    'fighters': [], 'cargo': [], 'environments': []}
            if make_fit(spec).fits:
                cases.append(spec)
            else:
                unmatched.append(dict(id=item.ID, name=item.name, group=item.group.name,
                                      category=item.category.name, reason='Drone fit rejected by original EOS'))
        else:
            unmatched.append(dict(id=item.ID, name=item.name, group=item.group.name,
                                  category=item.category.name, reason='Requires addition-specific fixture construction'))
    from eos.gamedata import Item, Group
    burst_items = eos.db.get_gamedata_session().query(Item).join(Group).filter(
        Group.name == 'Command Burst', Item.published.is_(True), Item.marketGroupID.isnot(None)).all()
    burst_modules = [Module(item) for item in sorted(burst_items, key=lambda value: value.ID)]
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as connection:
        charge_ids = [row[0] for row in connection.execute(
            "SELECT DISTINCT ta.typeID FROM dgmtypeattribs ta JOIN dgmattribs a ON a.attributeID=ta.attributeID "
            "JOIN invtypes t ON t.typeID=ta.typeID JOIN invgroups g ON g.groupID=t.groupID "
            "JOIN invcategories c ON c.categoryID=g.categoryID WHERE a.attributeName LIKE 'warfareBuff%ID' "
            "AND c.name='Charge' AND ta.value != 0 AND t.published=1 AND t.marketGroupID IS NOT NULL ORDER BY ta.typeID")]
    charge_coverage = []
    for identity in charge_ids:
        charge = eos.db.getItem(identity)
        module = next((value for value in burst_modules if value.isValidCharge(charge)), None)
        if module is None:
            raise ValueError('Published burst charge has no compatible original module: ' + charge.name)
        selected = None
        for hull in hulls:
            if not eligibility[hull].canFit(module.item):
                continue
            spec = {**deepcopy(base), 'name': 'Inspector burst charge: ' + charge.name, 'ship': hull,
                    'modules': [dict(name=module.item.name, state='ACTIVE', charge=charge.name)],
                    'drones': [], 'fighters': [], 'cargo': [], 'environments': []}
            try:
                make_fit(spec)
            except (ValueError, AssertionError):
                continue
            selected = spec
            break
        if selected is None:
            raise ValueError('No legal original burst-charge fit: ' + charge.name)
        cases.append(selected)
        charge_coverage.append(dict(id=identity, name=charge.name, module_id=module.item.ID,
                                    buffs=[dict(position=n, id=charge.getAttribute(f'warfareBuff{n}ID'),
                                                value=charge.getAttribute(f'warfareBuff{n}Value')) for n in range(1, 5)]))
    return cases, dict(absent_groups=absent, unmatched=unmatched,
                       selected_item_ids=[item.ID for item in items], command_charges=charge_coverage)
