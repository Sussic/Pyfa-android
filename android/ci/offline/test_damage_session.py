"""Actual damage route/history/commit ownership with deterministic replay doubles.

No EOS numerical, SQL, or Android acceptance is claimed. Only existing engine,
character materialization and ordinary engine-edit boundaries are doubled; graph
candidate, version migration, shared history, response staging and commit hooks
are the production methods.
"""
from copy import deepcopy
import json
import math
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from android_bridge.contract import BridgeSession, _json
from android_bridge.history import EditHistory
from android_bridge.offline.native_session import NativeSession
from android_bridge.offline.profile_graph import ProfileGraph
from android_bridge.offline.graph_history import GraphHistory, inputs
from android_bridge.offline.profiles import ProfileError
from android_bridge.offline import target_profiles as target
from android_bridge.offline import damage_patterns as damage
from test_target_session import ReplayGraph as TargetReplayGraph
from test_damage_patterns import F,G,CONTEXT,raw,zero,state,wire

COPY='e'*32
PID='builtin:all5'


class ProfileDouble:
    def __init__(self,ledger):self.ledger=deepcopy(ledger)
    def snapshot(self):return deepcopy(self.ledger)
    def bind(self,f,p):self.ledger['bindings'][f]=dict(profile_id=p,revision=1)
    def unbind(self,f):self.ledger['bindings'].pop(f,None)


class ReplayGraph(TargetReplayGraph):
    def __init__(self,initial):
        self.restore_calls=0
        super().__init__(initial)
        bridge=self._bridge
        bridge._request=lambda text:BridgeSession._request(bridge,text)
        bridge._error=lambda *args:BridgeSession._error(bridge,*args)
        bridge._serialize_success=lambda *args:BridgeSession._serialize_success(bridge,*args)
        bridge._graph=lambda records,revisions:dict(deepcopy(self._state['fit_graph']),records=records,revisions=revisions,fit_order=list(records))
    def _restore(self,graph,*,damage_ledger=None):
        self.restore_calls+=1
        snapshots=super()._restore(graph,damage_ledger=damage_ledger)
        for key,row in snapshots.items():row['damage_pattern']=deepcopy(graph['records'][key]['spec']['damage_pattern'])
        self._bridge._snapshots=snapshots
        return snapshots
    def _apply_profiles(self,candidate):
        super()._apply_profiles(candidate)
        damage.apply(candidate)
    def _model(self,ledger):return ProfileDouble(ledger)
    def _legacy_edit(self,operation,args):
        """Explicit deterministic fake of the existing ordinary-engine boundary."""
        before=deepcopy(self._bridge._records);records=deepcopy(before)
        key=args.get('fit_id')
        if operation=='set_damage_pattern':
            old=records[key]['spec']['damage_pattern']
            records[key]['spec']['damage_pattern']=deepcopy(old if args['pattern']==old else args['pattern'])
        elif operation=='set_target_profile':records[key]['spec']['target_profile']=deepcopy(args['profile'])
        elif operation=='duplicate_fit':
            records[COPY]=deepcopy(records[key]);records[COPY]['spec']['name']=args['name']
        elif operation=='delete_fit':del records[key]
        elif operation=='set_notes':records[key]['spec']['notes']=args['text']
        elif operation=='create_fit':
            records[COPY]=dict(spec=deepcopy(args['spec']),skills={},projections=[],commands=[])
        else:raise AssertionError('Unsupported deterministic operation: '+operation)
        self._bridge._records=records
        self._bridge._revisions={k:self._bridge._revisions.get(k,1) for k in records}
        self._bridge._history=self._bridge._history.after_edit(operation,args,before,records,())
        return dict(status='ok')


def session(initial=None):
    initial=deepcopy(state() if initial is None else initial)
    initial['profiles']=dict(format=2 if initial['version']>=5 else 1,dataset=CONTEXT['dataset_sha256'],profiles={PID:dict(name='All 5',default_level=5,levels={},revision=0)},
        bindings={f:dict(profile_id=PID,revision=1) for f in initial['fit_graph']['records']})
    if initial['version']>=5:
        for row in initial['profiles']['profiles'].values():row.setdefault('implants',[])
    value=NativeSession.__new__(NativeSession);value.graph=ReplayGraph(initial)
    value.history=GraphHistory();value._profile_floor={};value._binding_floor={}
    value._target_profile_floor={};value._target_binding_floor={}
    value._damage_pattern_floor={};value._damage_binding_floor={};value._implant_set_floor={};value._remember_versions()
    return value


class DamageSessionTests(unittest.TestCase):
    def setUp(self):self.session=session()
    def request(self,op='read',args=None,fit=F,selected=None,**view):
        return wire(op,args,context=self.session.context(),fit_id=fit,view=wire()['view']|dict(selected_pattern_id=selected)|view)
    def call(self,op='read',args=None,**kwargs):
        generation=self.session._store.current.generation
        result=json.loads(self.session.damage_dispatch(_json(self.request(op,args,**kwargs))))
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['state']['context']['generation'],generation+int(result['committed']))
        self.assertEqual(set(result),{'version','request_id','ok','committed','reopen_required','state','bridge','error'})
        if op=='read':self.assertIsNone(result['bridge'])
        else:
            self.assertIsNotNone(result['bridge'])
            fits={v['id']:v for v in result['bridge']['fits']}
            if result['state']['fit_id'] is not None:self.assertEqual(fits[result['state']['fit_id']]['revision'],result['state']['fit_revision'])
            if result['state']['detail']:
                for row in result['state']['detail']['bound_fits']['entries']:
                    self.assertEqual(fits[row['fit_id']]['revision'],row['revision']);self.assertEqual(fits[row['fit_id']]['name'],row['name'])
        return result
    def reject(self,request,code=None):
        before=self.session._store.current;history=self.session.history;authority=deepcopy(self.session.graph._state)
        result=json.loads(self.session.damage_dispatch(_json(request)))
        self.assertFalse(result['ok']);self.assertFalse(result['committed']);self.assertFalse(result['reopen_required'])
        self.assertIsNone(result['state']);self.assertIsNone(result['bridge'])
        if code:self.assertEqual(result['error']['code'],code,result)
        self.assertEqual(self.session._store.current,before);self.assertIs(self.session.history,history)
        self.assertTrue(damage.exact(self.session.graph._state,authority))
        return result
    def create(self,name='Shared',value=None):
        return self.call('create',dict(name=name,values=raw() if value is None else value),fit=None)['state']['detail']['pattern_id']
    def revision(self,key):return damage.resolve(self.session.graph._state.get('damage_patterns',damage.empty()),key)['revision']
    def assign(self,key,fit=F):
        return self.call('assign',dict(pattern_id=key,revision=self.revision(key),fit_revision=self.session._revisions[fit]),fit=fit,selected=key)
    def detach(self,fit=F):
        selected=self.call(fit=fit)['state']['selection']
        return self.call('detach_to_anonymous',dict(pattern_id=selected['pattern_id'],revision=selected['pattern_revision'],binding_revision=selected['binding_revision'],fit_revision=self.session._revisions[fit]),fit=fit)
    def reset(self,fit=F):return self.call('reset_uniform',dict(fit_revision=self.session._revisions[fit]),fit=fit)
    def edit(self,op,args):
        request=dict(version=1,request_id='ordinary',session_id=self.session.session_id,operation=op,
            expected_revisions={args['fit_id']:self.session._revisions[args['fit_id']]},arguments=args)
        result=json.loads(self.session.dispatch(_json(request)));self.assertEqual(result['status'],'ok',result);return result
    def test_v1_v2_v3_reads_rejects_noops_and_first_real_edit_migrate_only_once(self):
        for version in (1,2,3):
            self.session=session(state(version));before=self.session._store.current
            self.assertEqual(self.call()['state']['selection']['kind'],'anonymous')
            self.reject(self.request('create',dict(name='Uniform',values=raw())),'reserved_name')
            self.edit('set_damage_pattern',dict(fit_id=F,pattern=dict.fromkeys(damage.DAMAGE_FIELDS,25.0)))
            self.assertEqual(self.session._store.current,before)
            self.assertTrue(self.session.graph.migration_pending)
            self.create('First real edit')
            self.assertEqual(self.session.graph._state['version'],9);self.assertFalse(self.session.graph.migration_pending)
            self.assertEqual(self.session.graph._state['targets'],target.empty());self.assertEqual(self.session.graph._state['imports'],{})
            self.assertNotIn(F,self.session.graph._state['damage_patterns']['bindings'])
    def test_zero_library_only_create_duplicate_reopen_and_zero_reject_before_replay(self):
        initial=state();initial['fit_graph'].update(records={},revisions={},fit_order=[],sample_id=None,format=2,modified={})
        self.session=session(initial);key=self.create(value=zero());self.assertEqual(self.call(fit=None)['state']['selection']['kind'],'no_fit')
        self.call('duplicate',dict(pattern_id=key,revision=1,name='Zero copy'),fit=None)
        self.session=session(json.loads(self.session._store.current.payload))
        self.assertFalse(self.call(fit=None,selected=key)['state']['detail']['assignable'])
        self.assertEqual(self.session.history.details('library')['undo_count'],0)
        self.session=session();key=self.create(value=zero());calls=self.session.graph.restore_calls
        self.reject(self.request('assign',dict(pattern_id=key,revision=1,fit_revision=1)),'unassignable')
        self.assertEqual(self.session.graph.restore_calls,calls)
        nonzero=self.create('Positive');self.assign(nonzero);calls=self.session.graph.restore_calls
        self.reject(self.request('update_values',dict(pattern_id=nonzero,revision=1,values=zero())),'unassignable')
        self.assertEqual(self.session.graph.restore_calls,calls)
    def test_shared_edit_rename_delete_undo_redo_has_monotonic_all_floors(self):
        key=self.create();self.assign(key);self.assign(key,G)
        self.call('update_values',dict(pattern_id=key,revision=1,values=raw(emAmount=-0.0)),selected=key)
        versions=(self.revision(key),self.session._revisions[F],self.session.graph._state['damage_patterns']['bindings'][F]['revision'])
        self.call('undo',fit=None,selected=key)
        self.assertGreater(self.revision(key),versions[0]);self.assertGreater(self.session._revisions[F],versions[1]);self.assertGreater(self.session.graph._state['damage_patterns']['bindings'][F]['revision'],versions[2])
        self.assertTrue(damage.exact(self.session._records[F]['spec']['damage_pattern'],raw()))
        self.call('redo',fit=None,selected=key)
        self.call('rename',dict(pattern_id=key,revision=self.revision(key),name='Renamed'),selected=key)
        self.call('delete',dict(pattern_id=key,revision=self.revision(key),bound_fit_count=2,bound_module_count=0,affected_fit_count=2),selected=key)
        self.assertNotIn(key,self.session.graph._state['damage_patterns']['patterns'])
        for f in (F,G):self.assertEqual(self.session.graph._state['damage_patterns']['bindings'][f]['pattern_id'],damage.UNIFORM)
        self.call('undo',fit=None);self.assertEqual(self.session.graph._state['damage_patterns']['patterns'][key]['name'],'Renamed')
        self.assertTrue(damage.exact(self.session._records[G]['spec']['damage_pattern'],raw(emAmount=-0.0)))
        self.call('redo',fit=None,selected=key)
        self.assertIsNone(self.call(selected=None)['state']['detail'])
    def test_unchanged_identity_detach_uniform_integer_and_signedzero_raw(self):
        for key in (damage.UNIFORM,damage.builtin_id(-17),self.create(value=raw(emAmount=-0.0))):
            self.assign(key);saved=deepcopy(self.session._records[F]['spec']['damage_pattern'])
            before=self.session.history.details(F)['undo_count'];result=self.detach()
            self.assertTrue(result['committed']);self.assertEqual(result['state']['selection']['kind'],'anonymous')
            self.assertEqual(self.session.history.details(F)['undo_count'],before+1)
            self.assertTrue(damage.exact(saved,self.session._records[F]['spec']['damage_pattern']))
            self.call('undo');self.assertEqual(self.call()['state']['selection']['pattern_id'],key)
            self.call('redo');self.assertTrue(damage.exact(saved,self.session._records[F]['spec']['damage_pattern']))
    def test_stale_detach_identity_binding_fit_and_values_reject(self):
        key=self.create();self.assign(key)
        args=dict(pattern_id=key,revision=1,binding_revision=1,fit_revision=self.session._revisions[F])
        for change,code in (({'pattern_id':damage.UNIFORM,'revision':0},'stale_binding'),({'binding_revision':2},'stale_binding'),({'revision':0},'stale_pattern'),({'fit_revision':1},'stale_fit'),({'values':raw()},'invalid_request')):
            self.reject(self.request('detach_to_anonymous',args|change),code)
        self.detach();self.reject(self.request('detach_to_anonymous',args|dict(fit_revision=self.session._revisions[F])),'stale_binding')
    def test_noops_preserve_all_versions_history_bytes_and_migration(self):
        key=self.create();self.assign(key)
        before=self.session._store.current;history=self.session.history;floors=deepcopy(self.session._damage_pattern_floor)
        self.assertFalse(self.assign(key)['committed'])
        self.assertFalse(self.call('rename',dict(pattern_id=key,revision=1,name=' Shared '))['committed'])
        self.assertFalse(self.call('update_values',dict(pattern_id=key,revision=1,values=raw()))['committed'])
        self.assertEqual(self.session._store.current,before);self.assertIs(self.session.history,history);self.assertEqual(self.session._damage_pattern_floor,floors)
        self.reset();before=self.session._store.current;self.assertFalse(self.reset()['committed']);self.assertEqual(self.session._store.current,before)
        self.detach();self.assertTrue(self.reset()['committed'])
    def test_raw_signedzero_editor_kind_change_is_real_and_reopen_exact(self):
        self.assign(damage.UNIFORM)
        key=self.call('duplicate',dict(pattern_id=damage.UNIFORM,revision=0,name='Integer source'))['state']['detail']['pattern_id'];self.assign(key)
        self.assertTrue(self.call('update_values',dict(pattern_id=key,revision=1,values=dict.fromkeys(damage.DAMAGE_FIELDS,25.0)))['committed'])
        self.call('update_values',dict(pattern_id=key,revision=self.revision(key),values=raw(emAmount=-0.0)))
        self.call('undo');self.call('redo')
        self.session=session(json.loads(self.session._store.current.payload))
        self.assertTrue(damage.exact(self.call(selected=key)['state']['detail']['values'],raw(emAmount=-0.0)))
        self.assertEqual(self.session.history.details(F)['undo_count'],0)
    def test_named_inline_magnitude_equal_uses_submitted_float_kinds_one_shared_token(self):
        self.assign(damage.UNIFORM);old=self.session.history.details(F)['undo_count']
        submitted=dict.fromkeys(damage.DAMAGE_FIELDS,25.0)
        self.edit('set_damage_pattern',dict(fit_id=F,pattern=submitted))
        self.assertEqual(self.call()['state']['selection']['kind'],'anonymous')
        self.assertTrue(damage.exact(self.session._records[F]['spec']['damage_pattern'],submitted))
        self.assertEqual(self.session.history.details(F)['undo_count'],old+1)
        self.assertEqual(self.session.graph._bridge._history.details(F)['undo_count'],0)
        self.call('undo');self.assertEqual(self.call()['state']['selection']['pattern_id'],damage.UNIFORM)
        self.assertTrue(all(type(v) is int for v in self.session._records[F]['spec']['damage_pattern'].values()))
        self.call('redo');self.assertTrue(damage.exact(self.session._records[F]['spec']['damage_pattern'],submitted))
    def test_anonymous_inline_numeric_noop_preserves_kinds_but_actual_edit_shared(self):
        before=self.session._store.current
        self.edit('set_damage_pattern',dict(fit_id=F,pattern=dict.fromkeys(damage.DAMAGE_FIELDS,25.0)))
        self.assertEqual(self.session._store.current,before);self.assertEqual(self.session.history.details(F)['undo_count'],0)
        self.assertTrue(all(type(v) is int for v in self.session._records[F]['spec']['damage_pattern'].values()))
        self.edit('set_damage_pattern',dict(fit_id=F,pattern=raw(emAmount=-0.0)))
        self.assertEqual(self.session.history.details(F)['undo_count'],1)
        self.assertEqual(self.session.graph._bridge._history.details(F)['undo_count'],0)
        self.call('undo');self.call('redo')
        self.assertTrue(damage.exact(self.session._records[F]['spec']['damage_pattern'],raw(emAmount=-0.0)))
    def test_copy_shares_both_bindings_delete_removes_only_copy_and_empty_copy_history(self):
        key=self.create();self.assign(key)
        targs=dict(target_id=target.builtin_id(-149),revision=0,fit_revision=self.session._revisions[F])
        self.session.graph.edit_target('assign',targs,F)
        self.edit('duplicate_fit',dict(fit_id=F,name='Copy'))
        for ledger,field in (('targets','target_id'),('damage_patterns','pattern_id')):
            bindings=self.session.graph._state[ledger]['bindings'];self.assertEqual(bindings[F][field],bindings[COPY][field]);self.assertEqual(bindings[COPY]['revision'],1)
        self.assertEqual(self.session.history.details(COPY)['undo_count'],0)
        self.edit('delete_fit',dict(fit_id=COPY,resolve_references=True))
        for ledger in ('targets','damage_patterns'):
            self.assertNotIn(COPY,self.session.graph._state[ledger]['bindings']);self.assertIn(F,self.session.graph._state[ledger]['bindings'])
    def test_later_copy_blocks_older_shared_edit_before_replay_or_resolution(self):
        key=self.create();self.assign(key)
        self.call('rename',dict(pattern_id=key,revision=1,name='Edited'))
        self.edit('duplicate_fit',dict(fit_id=F,name='Later copy'))
        before=self.session.graph.restore_calls
        self.reject(self.request('undo',fit=None),'history_dependency')
        self.assertEqual(before,self.session.graph.restore_calls)
    def test_undo_create_with_untracked_binding_and_redo_delete_with_later_copy_refuse(self):
        key=self.create()
        # Intentional later outside-timeline binding; this isolates pre-resolution guard.
        self.session.graph.edit_damage('assign',dict(pattern_id=key,revision=1,fit_revision=1),F);self.session._remember_versions()
        self.reject(self.request('undo',fit=None),'history_dependency')
        self.session=session();key=self.create();self.assign(key)
        self.call('delete',dict(pattern_id=key,revision=1,bound_fit_count=1,bound_module_count=0,affected_fit_count=1));self.call('undo',fit=None)
        self.edit('duplicate_fit',dict(fit_id=F,name='Later copy'))
        self.reject(self.request('redo',fit=None),'history_dependency')
    def test_dependency_closure_notes_branching_and_history_limit(self):
        self.session.graph._state['fit_graph']['records'][G]['projections']=[dict(source_id=F)]
        key=self.create();self.assign(key);old=self.session._revisions[G]
        self.call('rename',dict(pattern_id=key,revision=1,name='Renamed'))
        self.assertGreater(self.session._revisions[G],old);self.assertIn(G,self.session.history.rows[F][0][-1].participants)
        self.edit('set_notes',dict(fit_id=F,text='Retain this direct note'))
        self.call('undo');self.assertEqual(self.session._records[F]['spec']['notes'],'Retain this direct note')
        self.call('rename',dict(pattern_id=key,revision=self.revision(key),name='Branch'))
        self.assertEqual(self.session.history.details('library')['redo_count'],0)
        for index in range(102):self.call('rename',dict(pattern_id=key,revision=self.revision(key),name='Name '+str(index)))
        self.assertEqual(self.session.history.details(F)['undo_count'],100)
    def test_target_route_undo_reconstructs_damage_and_preserves_target(self):
        key=self.create();self.assign(key)
        req=dict(version=1,request_id='target',context=self.session.context(),fit_id=F,
            view=dict(query='',offset=0,limit=50,selected_target_id=None,bound_offset=0),operation='assign',
            arguments=dict(target_id=target.builtin_id(-149),revision=0,fit_revision=self.session._revisions[F]))
        result=json.loads(self.session.target_dispatch(_json(req)));self.assertTrue(result['ok'],result)
        self.call('rename',dict(pattern_id=key,revision=1,name='Damage changed'))
        req.update(context=self.session.context(),operation='undo',arguments={})
        result=json.loads(self.session.target_dispatch(_json(req)));self.assertTrue(result['ok'],result)
        self.assertEqual(self.revision(key),3);self.assertEqual(self.session.graph._state['damage_patterns']['bindings'][F]['pattern_id'],key)
        self.assertEqual(self.session.graph._state['targets']['bindings'][F]['target_id'],target.builtin_id(-149))
    def test_import_staging_preserves_v4_ledgers_receipts_and_new_fit_anonymous(self):
        key=self.create();self.assign(key);before=deepcopy(self.session.graph._state)
        model=self.session.graph._model(before['profiles']);spec=deepcopy(before['fit_graph']['records'][G]['spec']);spec['name']='Imported'
        result=self.session.graph._stage_import_specs([spec],'import-case','f'*64,PID,model)
        self.assertFalse(result['replayed']);current=self.session.graph._state
        self.assertEqual(current['version'],9);self.assertEqual(current['damage_patterns'],before['damage_patterns']);self.assertEqual(current['targets'],before['targets'])
        self.assertNotIn(COPY,current['damage_patterns']['bindings']);self.assertIn('import-case',current['imports'])
        self.session=session(json.loads(self.session._store.current.payload));self.assertIn('import-case',self.session.graph._state['imports'])
    def test_full_state_size_and_bootstrap_serialization_refuse_before_write(self):
        key=self.create();self.assign(key)
        request=self.request('rename',dict(pattern_id=key,revision=1,name='Rejected'))
        with patch.object(damage,'MAX_STATE_BYTES',1):self.reject(request,'response_size')
        with patch.object(self.session.graph._bridge,'bootstrap',side_effect=RuntimeError('private error secret')):
            result=self.reject(request);self.assertNotIn('secret',result['error']['message'])
        self.call()
    def test_definite_write_failure_recovers_snapshots_history_and_floors(self):
        key=self.create();self.assign(key);snapshots=deepcopy(self.session.graph._snapshots);floors=deepcopy(self.session._damage_pattern_floor)
        with patch.object(self.session._store,'write',side_effect=OSError('write rejected')):
            self.reject(self.request('rename',dict(pattern_id=key,revision=1,name='Rejected')))
        self.assertEqual(self.session.graph._snapshots,snapshots);self.assertEqual(self.session._damage_pattern_floor,floors)
        self.call('rename',dict(pattern_id=key,revision=1,name='Works after recovery'))
    def test_ambiguous_write_and_postcommit_publication_disable_until_reopen(self):
        for boundary in ('confirm','_remember_versions'):
            self.session=session();request=self.request('create',dict(name='Committed maybe',values=raw()))
            owner=self.session._store if boundary=='confirm' else self.session
            with patch.object(owner,boundary,side_effect=RuntimeError('uncertain')):
                response=json.loads(self.session.damage_dispatch(_json(request)))
            self.assertFalse(response['ok']);self.assertIsNone(response['committed']);self.assertTrue(response['reopen_required']);self.assertFalse(self.session._available)
    def test_failed_recovery_disables_and_external_writer_never_publishes_cache(self):
        key=self.create();request=self.request('rename',dict(pattern_id=key,revision=1,name='Rejected'))
        with patch.object(self.session.graph,'_restore',side_effect=RuntimeError('cannot recover')):
            response=json.loads(self.session.damage_dispatch(_json(request)))
        self.assertIsNone(response['committed']);self.assertTrue(response['reopen_required'])
        self.session=session();self.session._store._durable=self.session._store.current._replace(generation=2)
        response=json.loads(self.session.damage_dispatch(_json(self.request())))
        self.assertIsNone(response['committed']);self.assertTrue(response['reopen_required']);self.assertIsNone(response['state'])
    def test_revision_generation_exhaustion_and_delete_count_reject_without_write(self):
        key=self.create();self.assign(key)
        self.reject(self.request('delete',dict(pattern_id=key,revision=1,bound_fit_count=0,bound_module_count=0,affected_fit_count=0)),'stale_bindings')
        self.session._damage_binding_floor[F]=damage.MAX_INT
        self.reject(self.request('rename',dict(pattern_id=key,revision=1,name='Overflow')),'revision')
        self.session._damage_binding_floor[F]=1;self.session.graph._revision_floor[F]=damage.MAX_INT
        self.reject(self.request('rename',dict(pattern_id=key,revision=1,name='Overflow')),'revision')
        self.session.graph._revision_floor[F]=self.session._revisions[F]
        self.session._store.current=self.session._store.current._replace(generation=damage.MAX_INT);self.session._store._durable=self.session._store.current
        self.reject(self.request('rename',dict(pattern_id=key,revision=1,name='Overflow')),'revision')
    def test_read_rechecks_durable_after_prepare_and_malformed_request_id_echo(self):
        original=damage.state_view
        def mutate_durable(*args,**kwargs):
            result=original(*args,**kwargs);self.session._store._durable=self.session._store.current._replace(generation=2);return result
        with patch.object(damage,'state_view',side_effect=mutate_durable):result=json.loads(self.session.damage_dispatch(_json(self.request())))
        self.assertIsNone(result['state']);self.assertTrue(result['reopen_required'])
        self.session=session()
        for text in ('{','{"request_id":"x","x":1,"x":2}','{"request_id":"bad\\n"}'):
            result=json.loads(self.session.damage_dispatch(text));self.assertFalse(result['ok']);self.assertIsNone(result['request_id'])
        result=json.loads(self.session.damage_dispatch('{"request_id":"valid-id"}'));self.assertEqual(result['request_id'],'valid-id')


class DamageEnvelopeTests(unittest.TestCase):
    """Production cumulative-root/import/damage validator with engine checks doubled."""
    def check(self,graph,candidate):
        graph.engine.settings={}
        with patch.object(BridgeSession,'_validate_graph') as fit_validation:
            ProfileGraph._validate(graph,candidate)
        return fit_validation
    def test_actual_validator_accepts_each_legacy_version_and_current_v8(self):
        for version in (1,2,3,4,5,6,7,8):
            owner=session(state(version));before=owner._store.current
            checked=self.check(owner.graph,deepcopy(owner.graph._state))
            self.assertEqual(checked.call_count,1);self.assertEqual(owner._store.current,before)
    def test_cumulative_import_receipts_are_validated_in_v2_v3_v4(self):
        for version in (2,3,4):
            owner=session(state(version));candidate=deepcopy(owner.graph._state)
            candidate['imports']={'bad':{}}
            with self.assertRaisesRegex(ProfileError,'receipt'):self.check(owner.graph,candidate)
            self.assertEqual(owner._store.writes,0)
    def test_cumulative_target_ledger_is_validated_in_v3_and_v4(self):
        for version in (3,4):
            owner=session(state(version));candidate=deepcopy(owner.graph._state)
            candidate['targets']['bindings'][F]=dict(target_id=target.builtin_id(-1),revision=1)
            with self.assertRaisesRegex(ProfileError,'disagree'):self.check(owner.graph,candidate)
            self.assertEqual(owner._store.writes,0)
    def test_exact_root_fields_and_unknown_versions_refuse_without_write(self):
        for version in (1,2,3,4):
            owner=session(state(version));candidate=deepcopy(owner.graph._state);candidate['unknown']=1
            with self.assertRaises(ProfileError):self.check(owner.graph,candidate)
            if version>=2:
                candidate=deepcopy(owner.graph._state);del candidate['imports']
                with self.assertRaises(ProfileError):self.check(owner.graph,candidate)
        owner=session();candidate=deepcopy(owner.graph._state);candidate['version']=9
        with self.assertRaises(ProfileError):self.check(owner.graph,candidate)
        self.assertEqual(owner._store.writes,0)
    def test_current_damage_projection_raw_types_signs_and_zero_refuse_without_repair(self):
        owner=session(state(4));candidate=deepcopy(owner.graph._state)
        key,_=damage.mutate(candidate,'create',dict(name='Saved',values=raw(emAmount=-0.0)),None)
        damage.mutate(candidate,'assign',dict(pattern_id=key,revision=1,fit_revision=1),F)
        self.check(owner.graph,candidate)
        for value in (0,0.0,1.0):
            corrupt=deepcopy(candidate);corrupt['fit_graph']['records'][F]['spec']['damage_pattern']['emAmount']=value
            before=deepcopy(corrupt)
            with self.assertRaises(ProfileError):self.check(owner.graph,corrupt)
            self.assertTrue(damage.exact(corrupt,before))
        corrupt=deepcopy(candidate);corrupt['damage_patterns']['patterns'][key]['values']=zero()
        corrupt['fit_graph']['records'][F]['spec']['damage_pattern']=zero()
        with self.assertRaisesRegex(ProfileError,'positive total'):self.check(owner.graph,corrupt)
        self.assertEqual(owner._store.writes,0)
    def test_first_real_target_character_and_import_commits_all_retain_damage_v4(self):
        # The actual shared commit owns migration for every route. Character
        # materialization is doubled; its changed input still traverses commit.
        for route in ('target','character','import'):
            owner=session(state(3));g=owner.graph
            if route=='target':g.edit_target('assign',dict(target_id=target.builtin_id(-1),revision=0,fit_revision=1),F)
            elif route=='character':
                candidate=deepcopy(g._state);candidate['profiles']['profiles'][PID]['name']='Changed label'
                g._commit(candidate,{F,G})
            else:
                spec=deepcopy(g._state['fit_graph']['records'][G]['spec'])
                g._stage_import_specs([spec],'new-import','f'*64,PID,g._model(g._state['profiles']))
            self.assertEqual(g._state['version'],9);self.assertEqual(g._state['damage_patterns'],damage.empty())


if __name__=='__main__':unittest.main()
