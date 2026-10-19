#!/usr/bin/env python3
"""Finite C07.2 candidate/wire exporter; parent admission required, never self-launches.

Use --output-dir NEW_DIRECTORY --schedule REVIEWED_SCHEDULE_JSON --items FROZEN_INPUTS_JSON.
The pinned environment/PYFA_* inputs and resource process guard belong to parent.
Fresh-process reopen is a separate invocation with --reopen NAME against retained stores.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
from unittest.mock import patch

sys.dont_write_bytecode=True
REPO=Path(os.environ['PYFA_CURRENT_REPO']).resolve()
sys.path[:0]=[str(REPO),os.environ['PYFA_REFERENCE_SOURCE']]
from android_bridge.engine import HeadlessEngine
from android_bridge.contract import _json
from android_bridge.offline.native_session import NativeSession
from android_bridge.character_implants import catalog_response


def scalar(value):
    assert type(value) in (int,float) and math.isfinite(value)
    return dict(kind='integer' if type(value) is int else 'decimal',value=value,float_hex=value.hex() if type(value) is float else None)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):digest.update(part)
    return digest.hexdigest()


def write(path,data):
    with path.open('x',encoding='utf-8') as stream:stream.write(data if type(data) is str else _json(data));stream.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--schedule',type=Path,required=True)
    parser.add_argument('--items',type=Path,required=True)
    parser.add_argument('--reopen',choices=('N4','N7','N13'))
    args=parser.parse_args()
    assert os.environ.get('C072_PARENT_HEAVY_LANE')=='granted','Parent exclusive admission required'
    schedule=json.loads(args.schedule.read_text());frozen=json.loads(args.items.read_text());items=frozen['items']
    database=Path(os.environ['PYFA_DATABASE']);dataset=os.environ['PYFA_DATASET_SHA']
    assert sha(database)=='68fb9ea965cb046e426f7c068c7508b55a4e82d2a3dceeed3cb948585d6e7203'
    engine=HeadlessEngine(database)
    assert dict(engine.settings)==schedule['eos_settings']
    output=args.output_dir.resolve()
    if args.reopen:
        mapping=json.loads((output/'identities.json').read_text())
        session=NativeSession(engine,output/(args.reopen+'.sqlite'),dataset,None)
        assert session.history.rows=={}
        observation=observe(session,engine,mapping['fits'],mapping['profiles'],mapping['rows'],schedule['read_order'])
        expected=json.loads((output/'observations.json').read_text())[args.reopen]
        assert observation==expected,(args.reopen,'fresh process inputs/raw values differ')
        assert session.graph._state['version']==5 and session.graph._state['profiles']['format']==2
        write(output/(args.reopen+'-reopen.json'),dict(ok=True,state=observation,history_empty=True,database_sha256=sha(database)))
        session.graph._bridge._reset_storage();return
    output.mkdir(parents=True,exist_ok=False);wire=output/'wire';wire.mkdir()
    session=NativeSession(engine,output/'working.sqlite',dataset,None)
    counter=[0];events=[]
    def retain(kind,request,response):
        counter[0]+=1;label='%03d-%s'%(counter[0],kind)
        if request is not None:write(wire/(label+'.request.json'),request)
        write(wire/(label+'.response.json'),response)
        parsed=json.loads(response)
        events.append(dict(label=label,kind=kind,request=None if request is None else label+'.request.json',response=label+'.response.json'))
        return parsed
    def edit(operation,arguments):
        ids={arguments[k] for k in ('fit_id','source_id','target_id') if k in arguments}
        request=_json(dict(version=1,request_id='candidate-'+str(counter[0]),session_id=session.session_id,operation=operation,
                           expected_revisions={key:session._revisions[key] for key in ids},arguments=arguments))
        result=retain('bridge',request,session.dispatch(request));assert result['status']=='ok',result;return result
    def feature(operation,arguments,anchor=None,ok=True):
        before_state=_json(session.feature_state(anchor));before_bridge=session.bootstrap()
        request=_json(dict(version=2,request_id='candidate-'+str(counter[0]),context=session.context(),operation=operation,arguments=arguments,anchor_fit_id=anchor))
        result=retain('feature',request,session.feature_dispatch(request));assert result['ok'] is ok,result
        label=events[-1]['label'];write(wire/(label+'.before-state.json'),before_state);write(wire/(label+'.before-bridge.json'),before_bridge)
        events[-1].update(before_state=label+'.before-state.json',before_bridge=label+'.before-bridge.json')
        return result
    fits={};profiles={};tokens={};observations={};graphs={};stale=None
    catalogue=retain('catalogue',None,_json(catalog_response(engine,dataset)));assert catalogue['ok'],catalogue
    write(output/'catalogue.json',catalogue)
    write(output/'initial-feature-state.json',session.feature_state(None));write(output/'initial-bridge.json',session.bootstrap())
    for key,fixture in schedule['fixtures'].items():
        spec=dict(name='C07.2 candidate '+key,ship=items[fixture['ship']]['name'],skill_level=5,factor_reload=False,
                  damage_pattern=dict(emAmount=25,thermalAmount=25,kineticAmount=25,explosiveAmount=25),target_profile=None,
                  security=dict(system='HISEC',pilot=0.0),implants=[],boosters=[],projections=[],commands=[],environments=[],
                  modules=[dict(name=items[row['item']]['name'],state=row['state'],charge=items[row['charge']]['name'] if row['charge'] else None) for row in fixture['modules']],drones=[],cargo=[],ignore_restrictions=False)
        previous=set(session._fits);edit('create_fit',dict(spec=spec));created=set(session._fits)-previous;assert len(created)==1;fits[key]=created.pop()
        if fixture['profile']!='P':profiles[key]=session.graph._state['profiles']['bindings'][fits[key]]['profile_id']
        for row in fixture['local_implants']:
            edit('fit_implant',dict(fit_id=fits[key],item_id=items[row['item']]['id']))
            if not row['active']:edit('toggle_implants',dict(fit_id=fits[key],main_position=len(session._records[fits[key]]['implants'])-1,positions=[]))
            ids=session._records[fits[key]]['inspection_ids']['implants'];tokens[ids[-1]]=row['identity']
    created=feature('create_profile',dict(name='C07.2 shared P',source='builtin:all5'))
    profiles['P']=next(row['profile_id'] for row in created['state']['profiles'] if row['name']=='C07.2 shared P');profiles['All5']='builtin:all5'
    assert len({profiles['P'],profiles['T1'],profiles['T2']})==3
    assert all(profiles[key].startswith('profile:') for key in ('P','T1','T2'))
    for key in ('A','B','C','S'):feature('assign_profile',dict(fit_id=fits[key],profile_id=profiles['P']),fits[key])
    for target in ('T1','T2'):
        edit('add_projection',dict(source_id=fits['A'],target_id=fits[target],range_m=0.0,active=True,amount=1))
        edit('add_command',dict(source_id=fits['S'],target_id=fits[target],active=True))
    def profile():return session.graph._state['profiles']['profiles'][profiles['P']]
    def graph_request(t):
        return dict(version=1,request_id='speed-'+str(counter[0]),context=session.context(),fits=[dict(fit_id=fits['A'],revision=session._revisions[fits['A']])],
                    x=dict(quantity='time',unit='s',range=[t,t]),y=dict(quantity='speed',unit='m/s'),resolution=1,budget_ms=10000,target_mass_mkg=None,target_inertia=None)
    for state in schedule['states']:
        name=state['name']
        for operation in state['operations']:
            kind=operation['operation']
            if kind=='add_profile_implant':
                item=items[operation['item']];occupant=next((row for row in profile()['implants'] if row['slot']==item['slot']),None)
                feature(kind,dict(profile_id=profiles['P'],revision=profile()['revision'],item_id=item['id'],replace_implant_id=occupant['implant_id'] if occupant else None),fits['A'])
                row=next(row for row in profile()['implants'] if row['item_id']==item['id']);tokens[row['implant_id']]=operation['identity']
            elif kind=='set_implant_source':
                key=fits[operation['fit']];feature(kind,dict(fit_id=key,fit_revision=session._revisions[key],source=operation['source']),key)
            elif kind=='equipment_source_only':edit('fit_implant',dict(fit_id=fits['A'],item_id=items['NAV5']['id']))
            elif kind=='undo_equipment_source_only':edit('undo',dict(fit_id=fits['A']))
            elif kind=='remove_profile_implant':
                row=next(row for row in profile()['implants'] if row['item_id']==items[operation['item']]['id'])
                feature(kind,dict(profile_id=profiles['P'],revision=profile()['revision'],implant_id=row['implant_id']),fits['A'])
            elif kind=='restore_profile_implant_inputs':feature('undo',{},fits['A'])
            elif kind=='assign_profile':feature(kind,dict(fit_id=fits[operation['fit']],profile_id=profiles[operation['profile']]),fits[operation['fit']])
            elif kind=='delete_profile_with_replacement':feature('delete_profile',dict(profile_id=profiles['P'],replacement=profiles['All5']),fits['A'])
            else:raise AssertionError(kind)
        observation=observe(session,engine,fits,profiles,tokens,schedule['read_order']);observations[name]=observation
        if name in schedule['graph_states']:
            graphs[name]=[]
            for t in schedule['graph_times_s']:
                request=graph_request(t);response=retain('g07',_json(request),session.mobility_samples(_json(request)));assert response['ok'],response
                graphs[name].append(dict(time_s=t,raw=scalar(response['series'][0]['y'][0])))
            if name=='N3':stale=graph_request(1.0)
        if name=='N4':
            for fit in session._fits.values():fit.clear()
            reverse=observe(session,engine,fits,profiles,tokens,list(reversed(schedule['read_order'])))
            assert reverse==observations['N4'],'N4 recipient-first/reverse reads differ'
            write(output/'read-order-crosscheck.json',dict(state='N4',forward=schedule['read_order'],reverse=list(reversed(schedule['read_order'])),exact_equal=True))
            response=retain('g07-stale',_json(stale),session.mobility_samples(_json(stale)));assert not response['ok'] and response['error']['code']=='stale_context'
        if name in ('N4','N7','N13'):shutil.copyfile(output/'working.sqlite',output/(name+'.sqlite'))
    # Actual no-op and complete definite errors for native codec/model consumption.
    generation=session._store.current.generation
    same=feature('set_implant_source',dict(fit_id=fits['A'],fit_revision=session._revisions[fits['A']],source='CHARACTER'),fits['A'])
    assert not same['committed'] and session._store.current.generation==generation
    feature('add_profile_implant',dict(profile_id='builtin:all5',revision=0,item_id=items['NAV1']['id'],replace_implant_id=None),fits['A'],ok=False)
    request=dict(version=1,request_id='unsupported-feature-v1',context=session.context(),operation='undo',arguments={},anchor_fit_id=fits['A'])
    error=retain('feature-error',_json(request),session.feature_dispatch(_json(request)));assert not error['ok'] and error['committed'] is False
    # A separate post-observation wire-only import proves outer v1/embedded v2.
    preview_request=_json(dict(version=1,request_id='candidate-import',profile_id='builtin:all5',documents=[dict(label='Synthetic wire-only EFT',text='[Rifter, C07.2 wire-only import]\n')]))
    preview=retain('import-preview',preview_request,session.import_preview(preview_request));assert preview['ok'],preview
    imported=retain('import',_json(preview['request']),session.import_execute(_json(preview['request'])))
    assert imported['ok'] and imported['version']==1 and imported['state']['version']==2
    with patch.object(session._store,'confirm',side_effect=RuntimeError('deliberate uncertain acknowledgement')):
        uncertain=feature('create_profile',dict(name='Deliberate uncertain wire evidence',source='builtin:all5'),None,ok=False)
    assert uncertain['committed'] is None and uncertain['reopen_required'] and not session._available
    write(output/'identities.json',dict(fits=fits,profiles=profiles,rows=tokens))
    write(output/'observations.json',observations);write(output/'graphs.json',graphs);write(output/'wire-index.json',events)
    write(output/'result.json',dict(ok=True,states=list(observations),fits_per_state=6,wire_events=len(events),database_sha256=sha(database),
                                  qualifications=['Candidate observations only; independent original comparison remains required.','Fresh-process N4/N7/N13 reopening is a separate guarded invocation.','Wire-only import and deliberate uncertain write occur only after N13 observation and all three retained stores.']))
    session.graph._bridge._reset_storage()


def observe(session,engine,fits,profiles,tokens,order):
    from eos.const import ImplantLocation
    result={};profile_names={value:key for key,value in profiles.items()}
    for key in order:
        fit=engine.prepare_read(session._fits[fits[key]]);record=session._records[fits[key]]
        local=[]
        for index,obj in enumerate(fit.implants):
            identity=record['inspection_ids']['implants'][index]
            local.append(dict(identity=tokens[identity],item_id=obj.itemID,slot=obj.slot,active=obj.active))
        character=[dict(identity=tokens[row['implant_id']],item_id=row['item_id'],slot=row['slot'],active=row['active']) for row in record['character_implants']]
        source=ImplantLocation(fit.implantSource).name
        result[key]=dict(identity=key,profile=profile_names[session.graph._state['profiles']['bindings'][fits[key]]['profile_id']],source=source,
                        local_implants=local,character_implants=character,applied_implants=local if source=='FIT' else character,
                        maxVelocity=scalar(fit.ship.getModifiedItemAttr('maxVelocity')),scanResolution=scalar(fit.ship.getModifiedItemAttr('scanResolution')),
                        shieldHP=scalar(fit.hp['shield']),projection_count=len(fit.projectedFits),command_count=len(fit.commandFits))
    return result


if __name__=='__main__':main()
