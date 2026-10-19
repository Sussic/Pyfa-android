"""Finite D02.1 inputs shared by independent original and public candidate runners.

No calculation, bridge import, expected numerical value or candidate capture lives
here. projection.json and its committed eleven-stage oracle remain untouched.
"""
from copy import deepcopy
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'projection.json'
LABELS = ('source_a', 'source_b', 'target_a', 'target_b')
DAMP = 'Remote Sensor Dampener II'
RANGE_SCRIPT = 'Targeting Range Dampening Script'
SCAN_SCRIPT = 'Scan Resolution Dampening Script'
WARRIOR = 'Warrior SW-300'
DROMI = 'Dromi I'
SKILL = 'Signal Suppression'


def fixtures(suite):
    base = json.loads(BASE.read_text())
    values = {key:deepcopy(base['source' if key.startswith('source') else 'target']) for key in LABELS}
    filled=json.loads(Path(__file__).with_name('filled_modules.json').read_text())
    for key, value in values.items():
        value['modules']=deepcopy(filled['source' if key.startswith('source') else 'target'])
        value['name'] = 'D02.1 ' + key
        value['ignore_restrictions'] = False
    if suite == 'outgoing':
        values['source_a']['drones'] = [dict(name=WARRIOR, amount=1, active=1)]
        values['source_a']['modules'][1]['state'] = 'OFFLINE'
    return values


def step(name, op, **args):
    return dict(name=name, op=op, args=args)


def links(reverse=False):
    sources = ['source_b', 'source_a'] if reverse else ['source_a', 'source_b']
    return [step('add_' + key, 'add_link', source=key, target='target_a') for key in sources]


def scenario(suite, reverse=False):
    a, b, t, u = LABELS
    prefix = links(reverse)
    if suite == 'composition':
        return prefix + [
            step('a_amount_two', 'link_amount', source=a, target=t, amount=2),
            step('b_disabled', 'link_active', source=b, target=t, active=False),
            step('a_amount_one', 'link_amount', source=a, target=t, amount=1),
            step('b_restored', 'link_active', source=b, target=t, active=True),
            *[step('a_range_' + str(value), 'link_range', source=a, target=t, range_m=value)
              for value in (0.0, 100000.0, 300000.0, None)],
            step('a_scan_script', 'local_charge', fit=a, charge=SCAN_SCRIPT),
            step('a_range_script', 'local_charge', fit=a, charge=RANGE_SCRIPT),
            step('incoming_damp_0', 'add_module', fit=t, item=DAMP),
            step('incoming_damp_1', 'add_module', fit=t, item=DAMP),
            step('incoming_support', 'add_module', fit=t, item='Remote Sensor Booster II'),
            step('selected_range', 'selected_charges', fit=t, main=0, selection=[1, 0], scope='SELECTED', charge=RANGE_SCRIPT, history=True),
            step('similar_scan', 'selected_charges', fit=t, main=0, selection=[0], scope='SIMILAR', charge=SCAN_SCRIPT, history=True),
            step('similar_clear', 'selected_charges', fit=t, main=0, selection=[0], scope='SIMILAR', charge=None, history=True),
            *[step('remove_target_module_'+str(i),'remove_projector',fit=t,family='module',index=i) for i in (2,1,0)],
            step('remove_a','remove_link',source=a,target=t),
            step('clean_baseline','remove_link',source=b,target=t),
        ]
    if suite == 'incoming':
        return prefix + [
            step('source_drone_added', 'add_drone', fit=a, item=WARRIOR),
            step('source_drone_range_zero', 'projector_range', fit=a, family='drone', index=0, range_m=0.0),
            step('source_drone_off', 'projector_active', fit=a, family='drone', index=0, active=False),
            step('source_fighter_added', 'add_fighter', fit=a, item=DROMI),
            step('source_fighter_one', 'fighter_amount', fit=a, index=0, amount=1),
            step('source_fighter_range_zero', 'projector_range', fit=a, family='fighter', index=0, range_m=0.0),
            step('source_fighter_ability_off', 'fighter_ability', fit=a, index=0, history=True),
            step('source_incoming_module', 'add_module', fit=a, item=DAMP),
            step('target_drone_added', 'add_drone', fit=t, item=WARRIOR),
            step('target_drone_range_distant', 'projector_range', fit=t, family='drone', index=0, range_m=300000.0),
            step('target_drone_range_zero', 'projector_range', fit=t, family='drone', index=0, range_m=0.0),
            step('target_drone_off', 'projector_active', fit=t, family='drone', index=0, active=False),
            step('target_fighter_added', 'add_fighter', fit=t, item=DROMI),
            step('target_fighter_one', 'fighter_amount', fit=t, index=0, amount=1),
            step('target_fighter_range_falloff', 'projector_range', fit=t, family='fighter', index=0, range_m=100000.0),
            step('target_fighter_range_zero', 'projector_range', fit=t, family='fighter', index=0, range_m=0.0),
            step('target_fighter_off', 'projector_active', fit=t, family='fighter', index=0, active=False),
            step('target_fighter_restored', 'projector_active', fit=t, family='fighter', index=0, active=True),
            *[step('remove_'+fit+'_'+family,'remove_projector',fit=fit,family=family,index=0) for fit,family in ((a,'module'),(a,'drone'),(a,'fighter'),(t,'drone'),(t,'fighter'))],
            step('remove_a','remove_link',source=a,target=t),
            step('clean_baseline','remove_link',source=b,target=t),
        ]
    if suite == 'outgoing':
        return prefix + [
            step('outgoing_near', 'link_range', source=a, target=t, range_m=0.0),
            step('outgoing_far', 'link_range', source=a, target=t, range_m=300000.0),
            step('outgoing_disabled', 'link_active', source=a, target=t, active=False),
            step('outgoing_restored', 'link_active', source=a, target=t, active=True),
            step('remove_a','remove_link',source=a,target=t),
            step('clean_baseline','remove_link',source=b,target=t),
        ]
    if suite == 'publication':
        return prefix + [
            step('second_recipient_a', 'add_link', source=a, target=u),
            step('second_recipient_b', 'add_link', source=b, target=u),
            step('publication_source_drone','add_drone',fit=a,item=WARRIOR),
            step('publication_target_fighter','add_fighter',fit=t,item=DROMI),
            step('publication_target_fighter_one','fighter_amount',fit=t,index=0,amount=1),
            step('shared_profile', 'share_profile'),
            step('shared_skill_zero', 'shared_skill', level=0, history=True),
            step('source_scan_shared', 'local_charge', fit=a, charge=SCAN_SCRIPT, history=True),
            step('source_inactive_shared', 'local_active', fit=a, active=False, history=True),
            step('source_active_shared', 'local_active', fit=a, active=True, history=True),
            step('source_range_shared', 'local_charge', fit=a, charge=RANGE_SCRIPT, history=True),
            step('shared_skill_restored', 'shared_skill', level=5, history=True),
            step('second_a_disabled', 'link_active', source=a, target=u, active=False, history=True),
            step('second_a_removed', 'remove_link', source=a, target=u, history=True),
            step('second_a_reapplied', 'add_link', source=a, target=u, history=True),
            step('publication_remove_source_drone','remove_projector',fit=a,family='drone',index=0),
            step('publication_remove_target_fighter','remove_projector',fit=t,family='fighter',index=0),
            step('source_a_deleted', 'delete_source', fit=a),
        ]
    raise ValueError(suite)


def assert_witnesses(suite, states, compare):
    """Required causal witnesses; values themselves come only from original EOS."""
    if suite != 'publication':
        compare(states['initial'],states['clean_baseline'],'complete_cleanup_baseline')
    stat = lambda stage, fit, field: states[stage]['stats'][fit][field]['value']
    if suite == 'composition':
        assert stat('b_restored', 'target_a', 'max_target_range') < stat('initial', 'target_a', 'max_target_range')
        values = [stat('a_range_' + str(v), 'target_a', 'max_target_range') for v in (0.0, 100000.0, 300000.0)]
        assert values[0] < values[1] < values[2], values
        assert stat('similar_scan','target_a','scan_resolution') < stat('similar_clear','target_a','scan_resolution')
    if suite == 'incoming':
        for left, right, owner in (
            ('source_drone_range_zero','source_drone_off','source_a'),
            ('source_fighter_range_zero','source_fighter_ability_off','source_a'),
            ('target_drone_range_zero','target_drone_off','target_a'),
            ('target_fighter_range_zero','target_fighter_off','target_a')):
            assert stat(left,owner,'max_velocity') < stat(right,owner,'max_velocity'), (left,right)
        assert stat('source_incoming_module','source_a','max_target_range') < stat('source_fighter_ability_off','source_a','max_target_range')
        # Incoming individual projectors are local-only, even on an outgoing fit.
        anchor = next(name for name in ('add_source_a','add_source_b') if len(states[name]['raw']['target_a']['projections'])==2)
        for stage in ('source_drone_added','source_drone_off','source_fighter_added','source_fighter_ability_off','source_incoming_module'):
            compare(states[anchor]['stats']['target_a'],states[stage]['stats']['target_a'],'local_only.'+stage)
    if suite == 'outgoing':
        compare(states['outgoing_near']['stats']['target_a'],states['outgoing_far']['stats']['target_a'],'forced_zero_range')
        assert stat('outgoing_far','target_a','max_velocity') < stat('outgoing_disabled','target_a','max_velocity')
    if suite == 'publication':
        for target in ('target_a','target_b'):
            assert stat('shared_skill_zero',target,'max_target_range') > stat('shared_profile',target,'max_target_range'), target
        for stage in states.values():
            assert len(stage['stats']) in (3,4)
