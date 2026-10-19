"""Finite D02.2 inputs only; no expected values or bridge dependencies."""
from copy import deepcopy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ('source_a', 'source_b', 'target_c')
TRANSFER = 'Medium Remote Capacitor Transmitter II'
SHIELD = 'Medium Remote Shield Booster II'
ARMOR = 'Medium Remote Armor Repairer II'
HULL = 'Medium Remote Hull Repairer II'
NEUT = 'Medium Energy Neutralizer II'
NOS = 'Medium Energy Nosferatu II'
SKILL = 'Shield Emission Systems'
SUITES = ('repair', 'capacitor', 'nosferatu', 'reciprocal')


def fixture(filename, name):
    cases = json.loads((ROOT / 'fixtures' / filename).read_text())['cases']
    return deepcopy(next(c['spec'] for c in cases if c['spec']['name'] == name))


def fixtures(suite):
    assert suite in SUITES
    outgoing = fixture('output.json', 'All outgoing')
    demanding = fixture('tank.json', 'Cap limited repairs')
    values = dict(source_a=deepcopy(outgoing), source_b=deepcopy(outgoing), target_c=demanding)
    if suite in ('capacitor', 'nosferatu'):
        values['source_a']['modules'] = [dict(name=TRANSFER, state='ACTIVE', charge=None)]
        # Nosferatu variant starts with neutralizer and uses original remove/add commands.
        values['source_b']['modules'] = [dict(name=NEUT, state='ACTIVE', charge=None)]
    for key, spec in values.items():
        spec['name'] = 'D02.2 ' + key
        assert not spec['drones'] and not spec['factor_reload']
    return values


def step(name, op, **args):
    return dict(name=name, op=op, args=args)


def scenario(suite, ranges, reverse=False):
    a, b, c = LABELS
    add = lambda source,target: step('add_'+source+'_to_'+target, 'add_link', source=source, target=target)
    remove = lambda name,source,target: step(name, 'remove_link', source=source, target=target)
    state = lambda name,fit,item,value: step(name,'local_state',fit=fit,item=item,state=value)
    direct = lambda item: [step('direct_'+item,'add_module',fit=c,item=item),step('remove_direct_'+item,'remove_projector',fit=c,family='module',index=0)]
    if suite == 'repair':
        sources = (b,a) if reverse else (a,b)
        steps = [add(source,c) for source in sources] + [
            step('a_amount_two','link_amount',source=a,target=c,amount=2),
            step('b_disabled','link_active',source=b,target=c,active=False),
            step('a_amount_one','link_amount',source=a,target=c,amount=1),
            step('b_restored','link_active',source=b,target=c,active=True)]
        for item in (SHIELD,ARMOR,HULL):
            steps += [state(item+'_online',a,item,'ONLINE'), state(item+'_active',a,item,'ACTIVE')]
        # Isolate range witnesses to A; preserve B and restore it afterward.
        steps += [step('b_disabled_for_range','link_active',source=b,target=c,active=False)]
        for name, value in [('null',None),('zero',0.0),('armor_falloff',ranges['armor_falloff']),('beyond_support',ranges['beyond_support']),('restored',None)]:
            steps += [step('repair_range_'+name,'link_range',source=a,target=c,range_m=value)]
        steps += [step('b_restored_after_range','link_active',source=b,target=c,active=True),
                  step('direct_armor','add_module',fit=c,item=ARMOR),
                  step('direct_armor_off','projector_active',fit=c,family='module',index=0,active=False),
                  step('direct_armor_on','projector_active',fit=c,family='module',index=0,active=True),
                  step('remove_direct_armor','remove_projector',fit=c,family='module',index=0),
                  remove('remove_a',a,c),remove('clean_baseline',b,c)]
        return steps
    if suite == 'capacitor':
        steps = [add(a,c),add(b,c),step('neut_amount_two','link_amount',source=b,target=c,amount=2),
                 step('neut_disabled','link_active',source=b,target=c,active=False),
                 step('neut_one','link_amount',source=b,target=c,amount=1),
                 step('neut_restored','link_active',source=b,target=c,active=True)]
        for source,item in ((a,TRANSFER),(b,NEUT)):
            steps += [state(item+'_online',source,item,'ONLINE'),state(item+'_active',source,item,'ACTIVE'),
                      remove('remove_'+source,source,c),step('restore_'+source,'add_link',source=source,target=c)]
        for name,value in [('exact_max',ranges['transfer_max']),('one_beyond',ranges['transfer_max']+1),('restored',None)]:
            steps += [step('transfer_'+name,'link_range',source=a,target=c,range_m=value)]
        for name,value in [('null',None),('zero',0.0),('falloff',ranges['neut_falloff']),('beyond',ranges['neut_beyond']),('restored',None)]:
            steps += [step('neut_range_'+name,'link_range',source=b,target=c,range_m=value)]
        steps += direct(TRANSFER) + direct(NEUT) + [remove('remove_a_final',a,c),remove('clean_baseline',b,c)]
        return steps
    if suite == 'nosferatu':
        return [add(a,c),add(b,c),step('remove_local_neut','local_remove',fit=b,item=NEUT),
                step('add_local_nos','local_add',fit=b,item=NOS),state('nos_online',b,NOS,'ONLINE'),
                state('nos_active',b,NOS,'ACTIVE'),step('remove_local_nos','local_remove',fit=b,item=NOS),
                step('restore_local_neut','local_add',fit=b,item=NEUT),remove('remove_a',a,c),remove('clean_baseline',b,c)]
    if suite == 'reciprocal':
        edges = [(a,b),(b,a),(a,c)]
        if reverse: edges.reverse()
        steps = [add(*edge) for edge in edges]
        steps += [state('a_armor_online',a,ARMOR,'ONLINE'),state('a_armor_active',a,ARMOR,'ACTIVE'),
                  state('a_transfer_online',a,TRANSFER,'ONLINE'),state('a_transfer_active',a,TRANSFER,'ACTIVE'),
                  step('a_to_b_two','link_amount',source=a,target=b,amount=2),
                  step('a_to_b_one','link_amount',source=a,target=b,amount=1),
                  step('a_to_b_range_zero','link_range',source=a,target=b,range_m=0.0),
                  step('a_to_b_range_falloff','link_range',source=a,target=b,range_m=ranges['armor_falloff']),
                  step('a_to_b_range_null','link_range',source=a,target=b,range_m=None),
                  step('b_to_a_disabled','link_active',source=b,target=a,active=False),
                  step('b_to_a_restored','link_active',source=b,target=a,active=True),
                  remove('b_to_a_removed',b,a),step('b_to_a_reapplied','add_link',source=b,target=a),
                  step('share_profile','share_profile'),step('shared_skill_four','shared_skill',level=4),
                  step('shared_skill_five','shared_skill',level=5),
                  step('direct_neut_a','add_module',fit=a,item=NEUT),
                  step('remove_direct_neut_a','remove_projector',fit=a,family='module',index=0),
                  remove('remove_a_c',a,c),remove('remove_a_b',a,b),remove('remove_b_a',b,a)]
        return steps
    raise ValueError(suite)
