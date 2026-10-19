#!/usr/bin/env python3
"""JSON-only causal/cross-construction checks of the original preflight receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
from tools.android_reference.reference import compare
from tools.android_reference.remote_support.preflight import exact


def verify(directory):
    names=('repair','repair-reverse','capacitor','nosferatu','reciprocal','reciprocal-reverse')
    runs={name:json.loads((directory/(name+'-measure-v4.json')).read_text()) for name in names}
    witnesses=[]
    def witness(name,condition):
        assert condition,name
        witnesses.append(name)
    for name,run in runs.items():
        capture_path=directory/(name+'-capture-v4.json')
        capture=json.loads(capture_path.read_text())
        witness(name+'.distinct_capture_measure_process',capture['process_nonce']!=run['process_nonce'])
        witness(name+'.exact_capture_receipt',hashlib.sha256(capture_path.read_bytes()).hexdigest()==run['measurement_input_sha256'])
        for field in ('source_files','original_imports','harness_files','fixture_files','dataset_sha256','inputs','steps','ranges','settings'):
            exact(capture[field],run[field],name+'.'+field)
        witness(name+'.zero_forbidden_network',not run['forbidden_attempts'] and not run['network_attempts'])
        witness(name+'.process_bounds',run['elapsed_seconds']<180 and run['peak_rss_kib']<1024*1024 and 0<run['limits']['address_space_bytes']<=1024**3)
        last='remove_b_a' if run['suite']=='reciprocal' else 'clean_baseline'
        if run['suite']=='reciprocal':
            # The shared profile remains shared. Original setLevel materializes
            # inactive dependent skill rows; preserve them, never pretend that
            # raw initial profile identity was restored by removing graph edges.
            for key in run['states']['initial']['raw']:
                first,final=run['states']['initial']['raw'][key],run['states'][last]['raw'][key]
                exact({k:v for k,v in first.items() if k!='skills'},{k:v for k,v in final.items() if k!='skills'},name+'.baseline_nonprofile_raw.'+key)
                exact(run['states']['shared_skill_five']['raw'][key]['skills'],final['skills'],name+'.retained_source_profile_rows.'+key)
            witnesses.append(dict(check=name+'.original_profile_rows_retained',
                initial={k:v['skills'] for k,v in run['states']['initial']['raw'].items()},
                final={k:v['skills'] for k,v in run['states'][last]['raw'].items()}))
        else:
            exact(run['states']['initial']['raw'],run['states'][last]['raw'],name+'.filled_baseline_raw')
        compare(run['states']['initial']['values'],run['states'][last]['values'],name+'.filled_baseline_values')
        witnesses.append(name+('.filled_equipment_edges_numerics_restored' if run['suite']=='reciprocal' else '.complete_filled_baseline_restored'))
    for family in ('repair','reciprocal'):
        forward,reverse=runs[family],runs[family+'-reverse'];matched=[]
        for stage in forward['states'].keys() & reverse['states'].keys():
            left,right=forward['states'][stage],reverse['states'][stage]
            if json.dumps(left['raw'],sort_keys=True)==json.dumps(right['raw'],sort_keys=True):
                exact(left['capture'],right['capture'],family+'.cross_construction_capture.'+stage)
                compare(left['values'],right['values'],family+'.cross_construction_values.'+stage)
                matched.append(stage)
        witness(family+'.cross_construction_count',len(matched)>=len(forward['states'])-3)
        witnesses.append(dict(check=family+'.cross_construction',stages=sorted(matched)))
    repair=runs['repair']['states']
    armor=lambda stage:repair[stage]['values']['target_c']['tank']['tank']['armorRepair']
    base,one,two=(armor(s) for s in ('initial','add_source_a_to_target_c','add_source_b_to_target_c'))
    witness('repair.diminishing_returns',0<one-base<two-base<2*(one-base))
    witness('repair.sustained_cap_transition',repair['initial']['values']['target_c']['capacitor']['stable'] is False and repair['add_source_b_to_target_c']['values']['target_c']['capacitor']['stable'] is True)
    for layer,item in (('shield','Medium Remote Shield Booster II'),('armor','Medium Remote Armor Repairer II'),('hull','Medium Remote Hull Repairer II')):
        off=repair[item+'_online']['values']['target_c']['tank']['tank'][layer+'Repair']
        on=repair[item+'_active']['values']['target_c']['tank']['tank'][layer+'Repair']
        witness('repair.'+layer+'_module_causal',off<on)
    witness('repair.range_falloff',armor('repair_range_zero')>armor('repair_range_armor_falloff')>armor('repair_range_beyond_support'))
    witness('repair.direct_armour_causal',armor('direct_armor')>armor('direct_armor_off') and armor('direct_armor')==armor('direct_armor_on'))
    witness('repair.depleting_donor_still_outgoing',repair['add_source_b_to_target_c']['values']['source_a']['capacitor']['stable'] is False and repair['add_source_b_to_target_c']['values']['source_a']['outgoing']['armor']>0)
    cap=runs['capacitor']['states']
    cv=lambda stage:cap[stage]['values']['target_c']['capacitor']
    witness('capacitor.transfer_boundary',cv('transfer_exact_max')['recharge']>cv('transfer_one_beyond')['recharge'])
    witness('capacitor.neut_multiplicity',cv('neut_amount_two')['used']>cv('add_source_b_to_target_c')['used']>cv('add_source_a_to_target_c')['used'])
    witness('capacitor.neut_falloff',cv('neut_range_zero')['used']>cv('neut_range_falloff')['used']>cv('neut_range_beyond')['used'])
    signs=[row[1] for row in cap['add_source_b_to_target_c']['capture']['target_c']['raw_extra_drains']]
    witness('capacitor.transfer_negative_neut_positive',any(v<0 for v in signs) and any(v>0 for v in signs))
    for item,anchor in (('Medium Remote Capacitor Transmitter II','neut_range_restored'),('Medium Energy Neutralizer II','remove_direct_Medium Remote Capacitor Transmitter II')):
        for source in ('source_a','source_b'):
            compare(cap[anchor]['values'][source],cap['direct_'+item]['values'][source],'direct projector has no invented donor.'+item+source)
        compare(cap[anchor]['values'],cap['remove_direct_'+item]['values'],'direct projector cleanup.'+item)
        witnesses.append('capacitor.direct_no_donor_and_restoration.'+item)
    nos=runs['nosferatu']['states']
    witness('nosferatu.local_gain',nos['nos_active']['values']['source_b']['capacitor']['recharge']>nos['nos_online']['values']['source_b']['capacitor']['recharge'])
    witness('nosferatu.projected_drain',nos['nos_active']['values']['target_c']['capacitor']['used']>nos['nos_online']['values']['target_c']['capacitor']['used'])
    compare(nos['add_local_nos']['values'],nos['nos_active']['values'],'nosferatu.active_restoration')
    reciprocal=runs['reciprocal']['states']
    for source in ('source_a','source_b'):
        witness('reciprocal.skill_donor_cost.'+source,reciprocal['shared_skill_four']['values'][source]['capacitor']['used']>reciprocal['shared_skill_five']['values'][source]['capacitor']['used'])
        compare(reciprocal['shared_skill_four']['values'][source]['outgoing'],reciprocal['shared_skill_five']['values'][source]['outgoing'],'skill unchanged outgoing.'+source)
    compare(reciprocal['shared_skill_four']['values']['target_c'],reciprocal['shared_skill_five']['values']['target_c'],'skill unchanged recipient')
    before,after=(reciprocal[s]['values'] for s in ('shared_skill_five','direct_neut_a'))
    witness('reciprocal.direct_neut_local_cost',after['source_a']['capacitor']['used']>before['source_a']['capacitor']['used'])
    for source in ('source_a','source_b','target_c'):
        compare(before[source]['outgoing'],after[source]['outgoing'],'direct incoming unchanged outgoing.'+source)
    compare(before,reciprocal['remove_direct_neut_a']['values'],'reciprocal direct cleanup')
    summary=dict(status='PASS original-only preflight and finite numerical measurements',
        stages=sum(len(v['states']) for v in runs.values()),saved_complete_fit_observations=sum(len(v['states'])*3 for v in runs.values()),
        actual_fit_observations_both_orders=sum(len(v['states'])*6 for v in runs.values()),
        simulations=sum(len(v['simulations']) for v in runs.values()),
        max_measured_events=max(s['iterations'] for v in runs.values() for s in v['simulations']),
        max_saved_events=max(s['saved_events'] for v in runs.values() for s in v['simulations']),
        max_bound_events=max(s['estimate']['events'] for v in runs.values() for s in v['simulations']),
        max_bound_event_list_work=max(s['estimate']['event_list_work'] for v in runs.values() for s in v['simulations']),
        max_elapsed_seconds=max(v['elapsed_seconds'] for v in runs.values()),max_peak_rss_kib=max(v['peak_rss_kib'] for v in runs.values()),
        witnesses=witnesses,receipt_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.glob('*-v4.json')},
        checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        excluded_claims=['candidate parity','graph/interleaving parity','desktop presentation','transactions/restart','native compilation/execution','clean semantic-pin dataset qualification'])
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();summary=verify(args.directory)
    with args.output.open('x') as stream:json.dump(summary,stream,indent=2,sort_keys=True,allow_nan=False);stream.write('\n')
    print(summary['status']);print(json.dumps({k:v for k,v in summary.items() if k not in ('witnesses','receipt_sha256','excluded_claims')},indent=2))
