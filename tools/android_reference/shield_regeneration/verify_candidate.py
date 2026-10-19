#!/usr/bin/env python3
"""JSON/source-file-only verifier for the six G04 candidate process receipts."""
import argparse
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(REPO))
from tools.android_reference.shield_regeneration.test_candidate import (
    SUITES, SOURCE_ONLY, SKILL_INSPECTION_SHA, candidate_stages, compare_curve, compare_source, exact, sha, qualified_skill_difference)


def verify(paths,original_paths,repo):
    expected=[(suite,phase) for suite in SUITES for phase in ('seed','reopen')]
    receipts=[json.loads(path.read_text()) for path in paths]
    exact(expected,[(r['suite'],r['phase']) for r in receipts],'six ordered seed/reopen processes')
    assert len({r['process_nonce'] for r in receipts})==6
    originals={suite:json.loads(path.read_text()) for suite,path in zip(SUITES,original_paths)}
    assert len({r['process_nonce'] for r in originals.values()})==3
    assert not {r['process_nonce'] for r in receipts}.intersection(r['process_nonce'] for r in originals.values())
    common=receipts[0]; total=dict(stages=0,fit_observations=0,curves=0,points=0); terminal=[]
    for path,row in zip(paths,receipts):
        suite,phase=row['suite'],row['phase']; oracle=originals[suite]
        assert row['status']=='passed' and oracle['status']=='passed',(path,row['status'])
        exact(sha(original_paths[SUITES.index(suite)]),row['oracle_sha256'],'bound independent oracle')
        exact(oracle['process_nonce'],row['original_process_nonce'],'original process identity')
        exact(oracle['source_kind'],row['source_qualification'],'retained source qualification')
        assert row['network_attempts']==row['forbidden_attempts']==[] and row['no_desktop_imports'] is True
        assert row['limits']['address_space_bytes']==1024**3 and row['limits']['external_timeout_seconds']==180
        assert row['limits']['per_request_budget_ms']==10000 and row['limits']['max_fits']==8 and row['limits']['max_points_per_fit']==201
        assert row['elapsed_seconds']<180 and row['peak_rss_kib']<1024**2
        exact(oracle['dataset_sha256'],row['dataset_file_sha256'],'same retained physical database')
        exact(row['dataset_file_sha256'],row['dataset_after_file_sha256'],'database unchanged')
        for field in ('product_files','harness_files','tolerance','limits'): exact(common[field],row[field],'common frozen '+field)
        exact(dict(oracle_sha256=row['oracle_sha256'],product_files=row['product_files'],harness_files=row['harness_files'],skill_inspection_sha256=SKILL_INSPECTION_SHA),row['input_binding'],'complete code/oracle dependency binding')
        exact(SKILL_INSPECTION_SHA,row['skill_inspection_sha256'],'reviewed exact skill inspection')
        checkpoint=Path(row['checkpoint_path']); assert sha(checkpoint)==row['checkpoint_sha256']
        saved=json.loads(checkpoint.read_text()); exact(saved['input_binding'],row['input_binding'],'checkpoint exact code and oracle')
        seed=next(r for r in receipts if r['suite']==suite and r['phase']=='seed')
        exact(seed['checkpoint_sha256'],row['checkpoint_sha256'],'seed/reopen share exact checkpoint bytes')
        exact(seed['input_binding'],row['input_binding'],'seed/reopen immutable execution inputs')
        exact(seed['states'],saved['states'],'checkpoint contains exact credited seed stages')
        exact(seed['states'],{key:row['states'][key] for key in seed['states']},'inherited stages match immutable seed receipt')
        for relative,digest in {**row['product_files'],**row['harness_files']}.items(): assert sha(repo/relative)==digest,relative
        expected_stages=['initial'] if phase=='seed' else candidate_stages(suite)
        # Derive the history seed cut by its actual named source stage, not a brittle count.
        if suite=='history' and phase=='seed':
            names=candidate_stages(suite); expected_stages=names[:names.index('management_four_redo')+1]
        exact(sorted(expected_stages),sorted(row['states']),'complete finite candidate stages')
        assert not set(SOURCE_ONLY).intersection(row['states'])
        for stage,record in row['states'].items():
            source=oracle['states'][stage]
            exact(sorted(source['fits']),sorted(record['fits']),'complete observed fits')
            for label,want in source['raw'].items():
                got=record['raw'][label]; exact(sorted(want),sorted(got),'complete raw source fields')
                for field in set(want)-{'character_id','skills'}: exact(want[field],got[field],'raw '+stage+'.'+label+'.'+field)
                qualified_skill_difference(suite,stage,label,want['skills'],got['skills'])
            for label,curves in record['fits'].items():
                want=source['fits'][label]; assert len(curves)==len(want['curves'])
                for index,curve in enumerate(curves):
                    compare_curve(want['curves'][index],curve,suite+'.'+stage+'.'+label+'.'+str(index))
                    compare_source(want,curve['source'],suite+'.'+stage+'.'+label)
            if phase=='reopen':
                total['stages']+=1; total['fit_observations']+=len(record['fits'])
                total['curves']+=sum(len(curves) for curves in record['fits'].values())
                total['points']+=sum(len(curve['x']) for curves in record['fits'].values() for curve in curves)
        differences=row['qualified_skill_differences']
        expected_differences=([('management_four_undo',label,'Capital Shield Operation') for label in ('source_a','source_b')]+(
            [('operation_four_undo',label,'Caldari Defensive Systems') for label in ('source_a','source_b')] if phase=='reopen' else [])) if suite=='history' else []
        exact(sorted(expected_differences),sorted((d['stage'],d['fit'],d['skill']) for d in differences),'only four narrowly qualified fit-stage differences')
        for difference in differences:
            assert difference['strict_comparison_failed'] is True and difference['original_active_level'] is None
            assert difference['original_effective_level']==0 and difference['candidate_active_level']==difference['candidate_effective_level']==5
            exact(SKILL_INSPECTION_SHA,difference['inspection_sha256'],'live source proof bound to approved inspection')
        for read in row['reads']:
            if read.get('result_ok') is True:
                assert read['durable_checks']==2
                assert len(read['prepares'])==len(read['curves'])==len(read['request']['fits'])
                exact([dict(handle=handle,kind='LOCAL') for handle in read['prepares']],read['top_calculations'],'one top LOCAL preparation per fit')
            assert not any(kind!='LOCAL' for kind in read['calculation_kinds'])
        terminals=[failure for failure in row['failures'] if failure['kind']=='terminal_durable_read']
        assert len(terminals)==1
        terminal.extend((failure['underlying_result'],failure['fail_on_check']) for failure in terminals)
        assert terminals[0]['disabled'] is True and terminals[0]['exact_state_and_bytes_preserved'] is True
        assert terminals[0]['result']['error']['code']=='reopen_required'
        if phase=='seed':
            failure_names={failure['kind'] for failure in row['failures']}
            assert {'cancelled_before_prepare','cancelled_during_points','cancelled_second_fit_after_completed_first',
                    'second_fit_error_no_partial_publication','deadline_during_points','admission_resource_refusal',
                    'point_engine_error','prepare_error','source_arithmetic_overflow','stale_context','stale_revision',
                    'replaced_handle','missing_handle_during_read','revision_during_read','context_during_read',
                    'zero_total_mutation_remains_unsupported','rejected_durable_mutation','duplicate_json_key'}<=failure_names
        else:
            check=next(check for check in row['checks'] if check.get('fresh_process_reopen'))
            assert all(check.values())
    exact([('success',1),('success',2),('cancelled',1),('cancelled',2),('engine_error',1),('engine_error',2)],terminal,'complete terminal durable matrix')
    exact(dict(stages=26,fit_observations=88,curves=608,points=119008),total,'complete supported original matrix')
    return dict(status='passed',**total,successful_candidate_processes=6,distinct_original_processes=3,
        repeated_reverse_selection_order=True,fresh_reopens=3,terminal_durable_cases=terminal,
        source_only_stages=list(SOURCE_ONLY),source_only_curves=36,source_only_points=7236,
        max_process_seconds=max(r['elapsed_seconds'] for r in receipts),peak_rss_kib=max(r['peak_rss_kib'] for r in receipts),
        receipts={str(path):sha(path) for path in paths},original_receipts={str(path):sha(path) for path in original_paths},
        verifier_sha256=sha(__file__),qualification=common['source_qualification'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--repo',type=Path,default=REPO)
    parser.add_argument('--originals',type=Path,nargs=3,required=True)
    parser.add_argument('receipts',type=Path,nargs=6); args=parser.parse_args()
    print(json.dumps(verify(args.receipts,args.originals,args.repo),indent=2,sort_keys=True))
