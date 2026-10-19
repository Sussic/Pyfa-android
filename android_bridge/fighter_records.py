"""Backward-compatible fighter quantities and exact ability-state records."""
def validate(row):
    if type(row) is not dict or not {'name','amount','active'}<=set(row) or set(row)-{'name','amount','active','abilities'}:
        raise ValueError('Invalid fighter fields')
    if type(row['name']) is not str or not row['name'] or type(row['amount']) is not int or not 0<=row['amount']<=2**31-1 or type(row['active']) is not bool:
        raise ValueError('Invalid fighter name, quantity or state')
    if 'abilities' in row:
        rows=row['abilities']
        if type(rows) is not list or len(rows)>128:raise ValueError('Invalid fighter ability list')
        ids=[]
        for ability in rows:
            if type(ability) is not dict or set(ability)!={'effect_id','active'} or type(ability['effect_id']) is not int or not 1<=ability['effect_id']<=2**31-1 or type(ability['active']) is not bool:
                raise ValueError('Invalid fighter ability state')
            ids.append(ability['effect_id'])
        if ids!=sorted(set(ids)):raise ValueError('Fighter abilities must be unique and ordered')

def states(fighter):return [dict(effect_id=a.effectID,active=a.active) for a in sorted(fighter.abilities,key=lambda a:a.effectID)]

def restore_states(fighter,row):
    if 'abilities' not in row:return
    expected={a.effectID:a for a in fighter.abilities}
    if set(expected)!={a['effect_id'] for a in row['abilities']}:raise ValueError('Fighter ability set differs from the pinned item')
    for saved in row['abilities']:
        ability=expected[saved['effect_id']]
        if saved['active'] and not ability.effect.isImplemented:raise ValueError('Unimplemented fighter ability cannot be activated')
        ability.active=saved['active']

def capture(fighter,include_states=False):
    from eos.saveddata.fighter import Fighter
    row=dict(name=fighter.item.name,amount=fighter.amount,active=fighter.active)
    current=states(fighter)
    # Retain unchanged legacy representation, but never lose nondefault abilities.
    if include_states or current!=states(Fighter(fighter.item)):row['abilities']=current
    return row
