"""Run in a fresh process: actual mobile runtime, no desktop imports or JNI claims."""
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
sys.path[:0]=[os.environ['PYFA_CURRENT_REPO'],os.environ['PYFA_REFERENCE_SOURCE'],
              str(Path(os.environ['PYFA_CURRENT_REPO'])/'android/app/src/main/python')]
import mobile_runtime as runtime

def run(path,reopen=False):
    database=os.environ['PYFA_DATABASE']
    with sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True) as db:
        metadata=dict(db.execute('SELECT field_name,field_value FROM metadata'))
    case=dict(name='Runtime smoke',ship='Rifter',skill_level=5,factor_reload=False,
              damage_pattern=dict(emAmount=25,thermalAmount=25,kineticAmount=25,explosiveAmount=25),
              target_profile=None,security=dict(system='HISEC',pilot=0.0),implants=[],boosters=[],
              projections=[],commands=[],environments=[],modules=[],drones=[],cargo=[],ignore_restrictions=False,edit={})
    runtime.boot(database,json.dumps(dict(dataset_metadata=metadata,database_logical_sha256=os.environ['PYFA_DATASET_SHA'])),json.dumps(case),path)
    boot=json.loads(runtime.bridge_bootstrap());assert boot['status']=='ok'
    key=runtime.bridge_sample_id();state=json.loads(runtime.offline_feature_state(key))
    assert len(state['skills'])>400
    export_request=dict(version=1,request_id='runtime-export',context=state['context'],fit_id=key,
                        revision=runtime._bridge._revisions[key],options=dict.fromkeys(
                        ('loaded_charges','cargo','implants','boosters','mutations'),True))
    before=Path(path).read_bytes()
    exported=json.loads(runtime.offline_export_preview(json.dumps(export_request)))
    assert exported['ok'] and exported['text'].startswith('[Rifter,'),exported
    assert Path(path).read_bytes()==before
    lock=dict(version=1,request_id='runtime-lock',context=state['context'],
              fits=[dict(fit_id=key,revision=runtime._bridge._revisions[key])],
              x=dict(quantity='signature_radius',unit='m',range=[1,4.3]),
              y=dict(quantity='lock_time',unit='s'),resolution=200,budget_ms=10000)
    locked=json.loads(runtime.offline_locktime_samples(json.dumps(lock)))
    assert locked['ok'] and locked['total_points']==201,locked
    class LockFlag:
        def get(self):return True
    stopped=json.loads(runtime.offline_locktime_samples(json.dumps(lock),LockFlag()))
    assert stopped['error']['code']=='cancelled',stopped
    assert Path(path).read_bytes()==before
    print('Runtime lock-time samples/cancellation/read-only persistence passed')
    mobility=dict(version=1,request_id='runtime-mobility',context=state['context'],
                  fits=[dict(fit_id=key,revision=runtime._bridge._revisions[key])],
                  x=dict(quantity='time',unit='s',range=[0,30]),y=dict(quantity='bumpDistance',unit='km'),
                  target_mass_mkg=1300,target_inertia=.015,resolution=200,budget_ms=10000)
    moved=json.loads(runtime.offline_mobility_samples(json.dumps(mobility)))
    assert moved['ok'] and moved['total_points']==201,moved
    stopped=json.loads(runtime.offline_mobility_samples(json.dumps(mobility),LockFlag()))
    assert stopped['error']['code']=='cancelled',stopped
    assert Path(path).read_bytes()==before
    print('Runtime mobility samples/cancellation/read-only persistence passed')
    if reopen:
        assert len(boot['fits'])==7
        assert runtime._bridge._records==json.loads(Path(path+'.linked-records.json').read_text())
        carrier=next(k for k,v in runtime._bridge._records.items() if v['spec']['ship']=='Thanatos')
        actual=json.loads(runtime.fighter_details(carrier))['squadrons']
        assert actual==json.loads(Path(path+'.fighters.json').read_text())
        assert json.loads(runtime.fighter_similar_selection(carrier,0))['matches']==json.loads(Path(path+'.similar.json').read_text())
        assert json.loads(runtime.booster_details(carrier))['boosters']==json.loads(Path(path+'.boosters.json').read_text())
        spool=next(k for k,v in runtime._bridge._records.items() if v['spec']['ship']=='Vedmak')
        assert json.loads(runtime.module_spool_details(spool))['modules']==json.loads(Path(path+'.spool.json').read_text())
        rah=next(k for k,v in runtime._bridge._records.items() if v['spec']['ship']=='Vexor')
        assert json.loads(runtime.module_rah_details(rah))['module_page']['entries']==json.loads(Path(path+'.rah.json').read_text())
        assert json.loads(runtime.implant_details(carrier))['implants']==json.loads(Path(path+'.implants.json').read_text())
        structure=next(k for k,v in runtime._bridge._records.items() if v['spec']['ship']=='Fortizar')
        assert json.loads(runtime.system_security_details(structure))['system']=='WSPACE'
        assert abs(json.loads(runtime.targeting_details(structure))['targeting']['main']['range']['value']-425600)<1e-6
        assert json.loads(runtime.recent_items())['item_ids']==json.loads(Path(path+'.recent.json').read_text())
        for fit_id,hp in json.loads(Path(path+'.command-shields.json').read_text()).items():
            assert json.loads(runtime.defense_details(fit_id))['defenses']['layers']['shield']['hp']['value']==hp
        for fit_id,rows in json.loads(Path(path+'.projected-modules.json').read_text()).items():
            assert json.loads(runtime.projected_module_details(fit_id))['modules']==rows
        for fit_id,value in json.loads(Path(path+'.projected-scan.json').read_text()).items():
            runtime._bridge.engine.prepare_read(runtime._bridge._fits[fit_id])
            assert runtime._bridge._fits[fit_id].ship.getModifiedItemAttr('scanResolution')==value
        assert state['history']['undo_count']==0
        assert not runtime._forbidden
        print('Fresh runtime restart restored 7 fits and exact command/projection links, fighter, booster, spool, reactive armor, implant and structure security states; session-local history cleared; no desktop imports')
        return
    pid=state['bindings'][key]['profile_id']
    request=dict(version=1,request_id='runtime-preview',profile_id=pid,documents=[dict(label='runtime',text='[Rifter, Runtime imported]\n')])
    preview=json.loads(runtime.offline_import_preview(json.dumps(request)));assert preview['ok'],preview
    response=json.loads(runtime.offline_import_execute(json.dumps(preview['request'])));assert response['ok'],response
    assert len(response['bridge']['fits'])==2
    state=response['state'];key=state['selected_fit_id']
    cap=dict(version=1,request_id='runtime-cap',context=state['context'],fits=[dict(fit_id=key,revision=runtime._bridge._revisions[key])],
             x=dict(quantity='time',unit='s',range=[0,300]),y=dict(quantity='cap_amount',unit='GJ'),
             starting_cap_percent=100,use_simulation=True,resolution=32,budget_ms=10000)
    class Flag:
        def get(self):return True
    cancelled=json.loads(runtime.offline_capacitor_samples(json.dumps(cap),Flag()))
    assert cancelled['error']['code']=='cancelled',cancelled
    result=json.loads(runtime.offline_capacitor_samples(json.dumps(cap)));assert result['ok'],result
    assert not runtime._forbidden
    def edit(operation,arguments,fit_id=None):
        request=dict(version=1,request_id='runtime-fighter',session_id=runtime._bridge.session_id,
                     operation=operation,arguments=arguments,
                     expected_revisions={args_id:runtime._bridge._revisions[args_id] for args_id in
                         {arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}})
        result=json.loads(runtime.bridge_dispatch(json.dumps(request)));assert result['status']=='ok',result
        return result
    carrier_spec={k:v for k,v in case.items() if k!='edit'}
    carrier_spec.update(ship='Thanatos',name='Runtime carrier')
    created=edit('create_fit',dict(spec=carrier_spec))
    carrier=created['fits'][0]['id']
    import eos.db
    item=eos.db.getItem('Firbolg I')
    edit('add_fighter',dict(fit_id=carrier,item_id=item.ID),carrier)
    details=json.loads(runtime.fighter_details(carrier));effect=next(a['effect_id'] for a in details['squadrons'][0]['abilities'] if a['active'])
    edit('toggle_fighter_ability',dict(fit_id=carrier,main_position=0,positions=[],effect_id=effect),carrier)
    for name in ('Firbolg II','Dromi I'):
        edit('add_fighter',dict(fit_id=carrier,item_id=eos.db.getItem(name).ID),carrier)
    before=Path(path).read_bytes();history=runtime._bridge.history_details(carrier)
    selected=json.loads(runtime.fighter_similar_selection(carrier,0))
    assert [r['index'] for r in selected['matches']]==[0,1]
    assert selected['revision']==runtime._bridge._revisions[carrier]
    assert Path(path).read_bytes()==before and runtime._bridge.history_details(carrier)==history
    edit('toggle_fighters',dict(fit_id=carrier,main_position=0,positions=[r['index'] for r in selected['matches']]),carrier)
    selected_after=json.loads(runtime.fighter_similar_selection(carrier,0))
    assert selected_after['matches']==selected['matches']
    Path(path+'.similar.json').write_text(json.dumps(selected['matches']))
    saved=json.loads(runtime.fighter_details(carrier))['squadrons']
    assert not saved[0]['active'] and not saved[1]['active'] and saved[2]['active']
    assert not next(a['active'] for a in saved[0]['abilities'] if a['effect_id']==effect)
    Path(path+'.fighters.json').write_text(json.dumps(saved))
    assert not runtime._forbidden
    print('Runtime fighter add/ability edit/durable state passed')
    booster=eos.db.getItem('Standard Blue Pill Booster')
    options=json.loads(runtime.booster_add_options(carrier,booster.ID));assert options['is_booster'] and options['occupant'] is None
    edit('fit_booster',dict(fit_id=carrier,item_id=booster.ID),carrier)
    row=json.loads(runtime.booster_details(carrier))['boosters'][0];effect=row['side_effects'][0]['effect_id']
    edit('set_booster_side_effect',dict(fit_id=carrier,position=0,effect_id=effect,active=True),carrier)
    edit('change_booster_variation',dict(fit_id=carrier,position=0,item_id=eos.db.getItem('Improved Blue Pill Booster').ID),carrier)
    saved=json.loads(runtime.booster_details(carrier))['boosters']
    assert next(e['active'] for e in saved[0]['side_effects'] if e['effect_id']==effect)
    Path(path+'.boosters.json').write_text(json.dumps(saved))
    assert not runtime._forbidden
    print('Runtime booster add-options/fit/side-effect/variation/durable state passed')
    spool_spec={k:v for k,v in case.items() if k!='edit'}
    spool_spec.update(ship='Vedmak',name='Runtime spool',modules=[dict(name='Heavy Entropic Disintegrator II',state='ACTIVE',charge='Occult M')])
    spool=edit('create_fit',dict(spec=spool_spec))['fits'][0]['id']
    row=json.loads(runtime.module_spool_details(spool))['modules'][0];assert row['override_cycles'] is None
    edit('set_module_spool',dict(fit_id=spool,position=row['index'],cycles=0),spool)
    saved=json.loads(runtime.module_spool_details(spool))['modules']
    assert saved[0]['override_cycles']==0 and saved[0]['current_cycles']==0
    Path(path+'.spool.json').write_text(json.dumps(saved))
    assert not runtime._forbidden
    print('Runtime spool details/explicit zero/durable state passed')
    rah_spec={k:v for k,v in case.items() if k!='edit'}
    rah_spec.update(ship='Vexor',name='Runtime reactive armor',modules=[dict(name='Reactive Armor Hardener',state='ACTIVE')])
    rah=edit('create_fit',dict(spec=rah_spec))['fits'][0]['id']
    row=json.loads(runtime.module_rah_details(rah))['module_page']['entries'][0];assert row['mode']=='fit'
    edit('set_module_rah',dict(fit_id=rah,position=row['index'],mode='builtin',pattern_id=-2),rah)
    saved=json.loads(runtime.module_rah_details(rah))['module_page']['entries'];assert saved[0]['builtin_id']==-2
    Path(path+'.rah.json').write_text(json.dumps(saved))
    assert not runtime._forbidden
    print('Runtime reactive armor details/built-in/durable state passed')
    implant=eos.db.getItem("Eifyr and Co. 'Rogue' Navigation NN-601")
    options=json.loads(runtime.implant_add_options(carrier,implant.ID));assert options['is_implant'] and options['occupant'] is None
    edit('fit_implant',dict(fit_id=carrier,item_id=implant.ID),carrier)
    row=json.loads(runtime.implant_details(carrier))['implants'][0]
    edit('toggle_implants',dict(fit_id=carrier,main_position=row['index'],positions=[]),carrier)
    saved=json.loads(runtime.implant_details(carrier))['implants'];assert not saved[0]['active']
    Path(path+'.implants.json').write_text(json.dumps(saved))
    assert not runtime._forbidden
    print('Runtime implant add-options/fit/toggle/durable state passed')
    structure_spec={k:v for k,v in case.items() if k!='edit'}
    structure_spec.update(ship='Fortizar',name='Runtime structure',modules=[dict(name='Standup L-Set Target Acquisition Array I',state='ONLINE')])
    structure=edit('create_fit',dict(spec=structure_spec))['fits'][0]['id']
    assert json.loads(runtime.system_security_details(structure))['system']=='HISEC'
    edit('set_system_security',dict(fit_id=structure,system='WSPACE'),structure)
    assert json.loads(runtime.system_security_details(structure))['system']=='WSPACE'
    assert abs(json.loads(runtime.targeting_details(structure))['targeting']['main']['range']['value']-425600)<1e-6
    assert not runtime._forbidden
    print('Runtime structure security and EOS targeting/durable state passed')
    # Source-policy link editor uses the existing six-fit graph and endpoint revisions.
    remote=eos.db.getItem('Remote Sensor Booster II')
    edit('add_module',dict(fit_id=key,item_id=remote.ID),key)
    position=next(i for i,m in enumerate(runtime._bridge._fits[key].modules) if not m.isEmpty and m.itemID==remote.ID)
    edit('set_module_charge',dict(fit_id=key,position=position,charge_id=eos.db.getItem('Scan Resolution Script').ID),key)
    endpoints=dict(source_id=key,target_id=carrier)
    base=runtime._bridge._fits[carrier].ship.getModifiedItemAttr('scanResolution')
    edit('add_projected_fit',endpoints)
    assert runtime._bridge._fits[carrier].ship.getModifiedItemAttr('scanResolution')>base
    edit('add_projected_fit',endpoints)
    edit('set_projected_fit_range',dict(endpoints,range_m=2500.0))
    edit('set_projected_fit_active',dict(endpoints,active=False))
    assert runtime._bridge._fits[carrier].ship.getModifiedItemAttr('scanResolution')==base
    edit('set_projected_fit_active',dict(endpoints,active=True))
    edit('set_projected_fit_range',dict(endpoints,range_m=None))
    before_links=runtime._bridge._records[carrier]['projections']
    assert before_links==[dict(source_id=key,range_m=None,active=True,amount=2)]
    edit('remove_projected_fit',endpoints);assert not runtime._bridge._records[carrier]['projections']
    edit('undo',dict(fit_id=carrier),carrier)
    assert runtime._bridge._records[carrier]['projections']==before_links
    Path(path+'.projection-records.json').write_text(json.dumps(runtime._bridge._records))
    print('Runtime saved-fit projection add/increment/range/state/remove/undo and linked stats passed')
    command_spec={k:v for k,v in case.items() if k!='edit'}
    command_spec.update(ship='Vulture',name='Runtime command source',modules=[
        dict(name='Shield Command Burst II',state='ACTIVE',charge='Shield Extension Charge')])
    command_source=edit('create_fit',dict(spec=command_spec))['fits'][0]['id']
    targets=(carrier,rah)
    def shield(fit_id):return json.loads(runtime.defense_details(fit_id))['defenses']['layers']['shield']['hp']['value']
    base={fit_id:shield(fit_id) for fit_id in targets}
    for fit_id in targets:edit('add_command_fit',dict(source_id=command_source,target_id=fit_id))
    boosted={fit_id:shield(fit_id) for fit_id in targets}
    assert all(boosted[fit_id]>base[fit_id] for fit_id in targets)
    history=runtime._bridge.history_details(carrier)['undo_count']
    command_endpoints=dict(source_id=command_source,target_id=carrier)
    edit('add_command_fit',command_endpoints)
    assert runtime._bridge.history_details(carrier)['undo_count']==history
    edit('set_command_fit_active',dict(command_endpoints,active=False));assert shield(carrier)==base[carrier]
    edit('set_command_fit_active',dict(command_endpoints,active=True));assert shield(carrier)==boosted[carrier]
    edit('remove_command_fit',command_endpoints);assert shield(carrier)==base[carrier]
    edit('undo',dict(fit_id=carrier));assert shield(carrier)==boosted[carrier]
    edit('fit_implant',dict(fit_id=command_source,item_id=eos.db.getItem('Shield Command Mindlink').ID))
    saved_shields={fit_id:shield(fit_id) for fit_id in targets}
    assert all(saved_shields[fit_id]>boosted[fit_id] for fit_id in targets)
    def projected_edit(operation,fit_id,index=0,**values):
        row=json.loads(runtime.projected_module_details(fit_id))['modules'][index]
        return edit(operation,dict(fit_id=fit_id,position=row['index'],object_key=row['object_key'],**values))
    options=json.loads(runtime.projected_module_add_options(carrier,remote.ID));assert options['enabled']
    edit('add_projected_module',dict(fit_id=carrier,item_id=remote.ID))
    options=json.loads(runtime.projected_module_options(carrier,0));assert options['charges'] and options['variations']
    projected_edit('set_projected_module_charge',carrier,charge_id=eos.db.getItem('Scan Resolution Script').ID)
    projected_edit('set_projected_module_range',carrier,range_m=2500.0)
    projected_edit('set_projected_module_state',carrier,state='inactive')
    projected_edit('set_projected_module_state',carrier,state='active')
    variation=next(row['id'] for row in options['variations'] if row['enabled'] and row['id']!=remote.ID)
    projected_edit('change_projected_module_variation',carrier,item_id=variation)
    assert json.loads(runtime.projected_module_details(carrier))['modules'][0]['range_m'] is None
    projected_edit('set_projected_module_range',carrier,range_m=0)
    projected_edit('remove_projected_module',carrier)
    edit('undo',dict(fit_id=carrier))
    repair=eos.db.getItem('Heavy Mutadaptive Remote Armor Repairer II')
    edit('add_projected_module',dict(fit_id=rah,item_id=repair.ID))
    options=json.loads(runtime.projected_module_options(rah,0));assert options['spool']
    projected_edit('set_projected_module_spool',rah,cycles=0)
    projected_saved={fit_id:json.loads(runtime.projected_module_details(fit_id))['modules'] for fit_id in targets}
    Path(path+'.projected-modules.json').write_text(json.dumps(projected_saved))
    projected_scan={}
    for fit_id in targets:
        runtime._bridge.engine.prepare_read(runtime._bridge._fits[fit_id])
        projected_scan[fit_id]=runtime._bridge._fits[fit_id].ship.getModifiedItemAttr('scanResolution')
    Path(path+'.projected-scan.json').write_text(json.dumps(projected_scan))
    print('Runtime individual projected module queries, charge/range/state/variation/remove/undo/spool and durable identities passed')
    cap.update(context=runtime._bridge.context(),fits=[dict(fit_id=k,revision=runtime._bridge._revisions[k]) for k in (command_source,*targets)],resolution=1)
    cap['x']['range']=[0,1]
    sampled=json.loads(runtime.offline_capacitor_samples(json.dumps(cap)));assert sampled['ok'],sampled
    assert {fit_id:shield(fit_id) for fit_id in reversed(targets)}==saved_shields
    Path(path+'.command-shields.json').write_text(json.dumps(saved_shields))
    Path(path+'.linked-records.json').write_text(json.dumps(runtime._bridge._records))
    print('Runtime command-fit links, duplicate/state/removal/undo, real burst/mindlink effects, graph cleanup and two-recipient persistence passed')
    # A rejected valid fighter attempt updates only Recent metadata/context.
    before_records=json.dumps(runtime._bridge._records,sort_keys=True)
    before_revisions=dict(runtime._bridge._revisions)
    before_history=runtime._bridge.history_details(key)
    before_generation=runtime._bridge.context()['generation']
    request=dict(version=1,request_id='runtime-rejected-fighter',session_id=runtime._bridge.session_id,operation='add_fighter',arguments=dict(fit_id=key,item_id=eos.db.getItem('Satyr I').ID),expected_revisions={key:runtime._bridge._revisions[key]})
    rejected=json.loads(runtime.bridge_dispatch(json.dumps(request)))
    assert rejected['status']=='error'
    assert json.dumps(runtime._bridge._records,sort_keys=True)==before_records
    assert runtime._bridge._revisions==before_revisions
    assert runtime._bridge.history_details(key)==before_history
    assert runtime._bridge.context()['generation']>before_generation
    saved=json.loads(runtime.recent_items())['item_ids']
    assert saved[0]==eos.db.getItem('Satyr I').ID
    Path(path+'.recent.json').write_text(json.dumps(saved))
    assert not runtime._forbidden
    print('Runtime rejected valid fighter attempt changed only Recent/context; durable order saved')
    print('Runtime boot/import/full publication/capacitor/cancellation passed; no desktop imports')

if __name__=='__main__':
    run(sys.argv[1],len(sys.argv)>2)
