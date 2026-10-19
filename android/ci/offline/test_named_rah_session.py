"""D05.4 real-EOS structural transaction/lifecycle cases, not numerical parity.

Execution requires a separately admitted integrated source and resource budget.
No expected EOS result is derived here; original matched numbers belong to the
finite candidate comparison. These assertions check identities, authority and
atomic persistence only.
"""
from copy import deepcopy
import json
from unittest.mock import patch
import unittest

from android_bridge.contract import BridgeSession
from android_bridge.store import StoreError as BridgeStoreError
from android_bridge.offline import damage_patterns as damage
from android_bridge.offline.profiles import ProfileError
from android_bridge.offline.profile_store import StoreWriteRejected
from test_native_session import NativeSessionTests, spec


class NamedRahSessionTests(NativeSessionTests):
    def setUp(self):
        super().setUp()
        self.other=self.key
        result=self.edit('create_fit',dict(spec=dict(spec(),name='Named RAH A',ship='Vexor',
            modules=[dict(name='Reactive Armor Hardener',state='ACTIVE')],ignore_restrictions=True)))
        self.key=result['fits'][0]['id']
    def rows(self,fit=None):
        return self.session.module_rah_details(fit or self.key)['module_page']['entries']
    def request_damage(self,operation='read',arguments=None,fit=None,**view):
        return dict(version=3,request_id='named-rah',context=self.session.context(),fit_id=fit or self.key,
            operation=operation,arguments=arguments or {},
            view=dict(query='',offset=0,limit=50,selected_pattern_id=None,bound_offset=0,module_offset=0)|view)
    def damage(self,operation='read',arguments=None,fit=None,**view):
        response=json.loads(self.session.damage_dispatch(json.dumps(self.request_damage(operation,arguments,fit,**view))))
        self.assertTrue(response['ok'],response);self.assertEqual(response['version'],3)
        return response
    def create_pattern(self,name='Shared',values=None):
        values=dict(emAmount=17.0,thermalAmount=31.0,kineticAmount=5.0,explosiveAmount=9.0) if values is None else values
        return self.damage('create',dict(name=name,values=values))['state']['detail']['pattern_id']
    def row_args(self,fit=None,position=0):
        fit=fit or self.key;row=self.rows(fit)[position]
        return dict(fit_revision=self.session._revisions[fit],object_key=row['object_key'],position=row['index'])
    def select(self,pattern,fit=None,position=0):
        selection=dict(mode='named',pattern_id=pattern,revision=self.session.graph._state['damage_patterns']['patterns'][pattern]['revision'])
        return self.damage('set_module',self.row_args(fit,position)|dict(selection=selection),fit)
    def stable(self):
        return self.path.read_bytes(),deepcopy(self.session.graph._state),self.session.history,self.session.context(),deepcopy(self.session.graph._bridge._recent)
    def reject_damage(self,request,code=None):
        before=self.stable();response=json.loads(self.session.damage_dispatch(json.dumps(request)))
        self.assertFalse(response['ok'],response);self.assertFalse(response['committed']);self.assertFalse(response['reopen_required'])
        if code:self.assertEqual(response['error']['code'],code,response)
        self.assertEqual(self.path.read_bytes(),before[0]);self.assertTrue(damage.exact(self.session.graph._state,before[1]))
        self.assertIs(self.session.history,before[2]);self.assertEqual(self.session.context(),before[3]);self.assertEqual(self.session.graph._bridge._recent,before[4])
        return response
    def duplicate(self):
        before=set(self.session._fits)
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Named RAH B'))
        return (set(self.session._fits)-before).pop()
    def test_named_identity_independent_incoming_reopen_and_equal_value_patterns(self):
        first=self.create_pattern();second=self.create_pattern('Equal values')
        incoming=deepcopy(self.session._records[self.key]['spec']['damage_pattern'])
        self.select(first);old=self.rows()[0]
        self.assertEqual(old['named_id'],first);self.assertIsNone(old['builtin_id']);self.assertEqual(old['pattern_revision'],1)
        self.assertTrue(damage.exact(incoming,self.session._records[self.key]['spec']['damage_pattern']))
        self.assertNotIn(self.key,self.session.graph._state['damage_patterns']['bindings'])
        self.reopen();self.assertEqual(self.rows()[0]['object_key'],old['object_key']);self.assertEqual(self.rows()[0]['named_id'],first)
        self.select(second);self.assertEqual(self.rows()[0]['named_id'],second)
        self.assertNotEqual(first,second)
    def test_reads_and_identical_set_do_not_write_recalculate_or_migrate(self):
        pattern=self.create_pattern();self.select(pattern)
        self.create_pattern('Unavailable zero',dict.fromkeys(damage.DAMAGE_FIELDS,0.0))
        args=self.row_args();before=self.stable()
        with patch.object(self.engine,'_recalculate',side_effect=AssertionError('No read recalculation')), \
             patch.object(self.session.graph,'_restore',side_effect=AssertionError('No read reconstruction')):
            details=self.session.module_rah_details(self.key,0,1)
            options=self.damage('module_options',args,query='Unavailable zero')
            selected=self.select(pattern)
        self.assertEqual(details['module_page']['limit'],1);self.assertEqual(details['module_page']['total'],1)
        self.assertFalse(options['state']['page']['entries'][0]['assignable']);self.assertFalse(selected['committed'])
        self.assertEqual(self.stable(),before)
    def test_all_holder_refresh_inactive_modules_and_linked_dependents(self):
        pattern=self.create_pattern();self.select(pattern);other=self.duplicate()
        self.edit('set_module_states',dict(fit_id=other,module_indices=[self.rows(other)[0]['index']],state='OFFLINE'))
        self.edit('add_command_fit',dict(source_id=self.key,target_id=self.other))
        versions=dict(self.session._revisions)
        self.damage('update_values',dict(pattern_id=pattern,revision=1,values=dict(emAmount=2.0,thermalAmount=7.0,kineticAmount=19.0,explosiveAmount=3.0)))
        for key in (self.key,other,self.other):self.assertGreater(self.session._revisions[key],versions[key])
        a=self.session._fits[self.key].modules[self.rows()[0]['index']].rahPatternOverride
        b=self.session._fits[other].modules[self.rows(other)[0]['index']].rahPatternOverride
        self.assertIs(a,b);self.assertEqual(self.rows(other)[0]['pattern_revision'],2)
        self.assertNotIn(other,self.session.graph._state['damage_patterns']['bindings'])
    def test_delete_dual_fallback_undo_redo_and_revision_floors(self):
        pattern=self.create_pattern();self.select(pattern)
        self.damage('assign',dict(pattern_id=pattern,revision=1,fit_revision=self.session._revisions[self.key]))
        key=self.rows()[0]['object_key']
        detail=self.damage(selected_pattern_id=pattern)['state']['detail']
        self.assertEqual((detail['bound_fit_count'],detail['bound_module_count'],detail['affected_fit_count']),(1,1,1))
        self.damage('delete',dict(pattern_id=pattern,revision=1,bound_fit_count=1,bound_module_count=1,affected_fit_count=1),selected_pattern_id=pattern)
        self.assertEqual(self.rows()[0]['mode'],'fit');self.assertEqual(self.damage()['state']['selection']['pattern_id'],damage.UNIFORM)
        self.damage('undo');self.assertEqual(self.rows()[0]['named_id'],pattern);self.assertEqual(self.rows()[0]['object_key'],key)
        self.assertGreater(self.rows()[0]['pattern_revision'],1)
        self.damage('redo');self.assertEqual(self.rows()[0]['mode'],'fit')
        self.damage('undo');self.reopen();self.assertEqual(self.rows()[0]['named_id'],pattern)
    def test_selected_ammo_refreshes_module_only_holder_without_assigning_its_incoming(self):
        self.damage('apply_item',dict(item_id=210,fit_revision=self.session._revisions[self.key]))
        self.select(damage.SELECTED_AMMO);other=self.duplicate()
        self.damage('reset_uniform',dict(fit_revision=self.session._revisions[self.key]))
        self.damage('reset_uniform',dict(fit_revision=self.session._revisions[other]),other)
        revision=self.session._revisions[self.key]
        self.damage('apply_item',dict(item_id=185,fit_revision=self.session._revisions[other]),other)
        self.assertGreater(self.session._revisions[self.key],revision)
        self.assertEqual(self.damage()['state']['selection']['pattern_id'],damage.UNIFORM)
        self.assertEqual(self.damage(fit=other)['state']['selection']['pattern_id'],damage.SELECTED_AMMO)
        self.assertEqual(self.rows()[0]['named_id'],damage.SELECTED_AMMO)
        self.assertEqual(self.rows()[0]['pattern_revision'],self.rows(other)[0]['pattern_revision'])
    def test_stale_context_key_position_fit_pattern_and_strict_old_bridge_refuse(self):
        pattern=self.create_pattern();self.select(pattern);args=self.row_args()
        selection=dict(mode='named',pattern_id=pattern,revision=1)
        for update,code in ((dict(object_key='f'*32),'stale_module'),(dict(position=999),'stale_module'),(dict(fit_revision=1),'stale_fit'),
                            (dict(selection=selection|dict(revision=2)),'stale_pattern')):
            self.reject_damage(self.request_damage('set_module',args|dict(selection=selection)|update),code)
        stale=self.request_damage('set_module',args|dict(selection=dict(mode='fit')))
        self.edit('rename_fit',dict(fit_id=self.key,name='Changed'))
        self.reject_damage(stale,'stale_context')
        before=self.stable()
        request=self.request('set_module_rah',dict(fit_id=self.key,position=self.rows()[0]['index'],mode='named',pattern_id=pattern))
        self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error')
        self.assertEqual(self.stable(),before)
    def test_atomic_write_serialization_and_revision_exhaustion_preserve_noop(self):
        pattern=self.create_pattern();self.select(pattern)
        request=self.request_damage('set_module',self.row_args()|dict(selection=dict(mode='disabled')))
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('injected')):
            self.reject_damage(request)
        with patch.object(damage,'MAX_STATE_BYTES',1):self.reject_damage(request,'response_size')
        self.session.history.sequence=damage.MAX_INT
        with patch.object(self.session.graph,'_restore',side_effect=AssertionError('History exhaustion must not stage')):
            self.reject_damage(request,'revision')
            self.assertFalse(self.select(pattern)['committed'])
    def test_reorder_clone_fill_copy_replace_remove_and_undo_identity_policy(self):
        pattern=self.create_pattern();self.select(pattern);original=self.rows()[0]
        self.edit('clone_selected_modules',dict(fit_id=self.key,module_indices=[original['index']]))
        rows=self.rows();self.assertEqual(len(rows),2);self.assertEqual({r['named_id'] for r in rows},{pattern})
        self.assertEqual(len({r['object_key'] for r in rows}),2)
        self.edit('swap_modules',dict(fit_id=self.key,from_position=rows[0]['index'],to_position=rows[1]['index']))
        self.assertEqual(self.rows()[1]['object_key'],original['object_key'])
        other=self.duplicate();self.assertEqual({r['named_id'] for r in self.rows(other)},{pattern})
        self.assertFalse({r['object_key'] for r in self.rows()} & {r['object_key'] for r in self.rows(other)})
        self.assertEqual(self.session.history.details(other)['undo_count'],0)
        target=self.rows()[0]
        self.edit('replace_module',dict(fit_id=self.key,position=target['index'],item_id=target['item_id']))
        replaced=next(r for r in self.rows() if r['index']==target['index'])
        self.assertEqual(replaced['mode'],'fit');self.assertNotEqual(replaced['object_key'],target['object_key'])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['named_id'],pattern)
        self.edit('remove_module',dict(fit_id=self.key,position=self.rows()[0]['index']))
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['object_key'],target['object_key'])
        self.edit('fill_modules_clone',dict(fit_id=self.key,position=self.rows()[0]['index']))
        self.assertTrue(any(row['mode']=='fit' for row in self.rows()))
    def test_late_fit_copy_blocks_shared_replay_and_delete_fit_removes_only_its_holders(self):
        pattern=self.create_pattern();self.select(pattern)
        self.damage('rename',dict(pattern_id=pattern,revision=1,name='Renamed'))
        copied=self.duplicate()
        self.reject_damage(self.request_damage('undo'),'history_dependency')
        self.edit('delete_fit',dict(fit_id=copied,resolve_references=True))
        detail=self.damage(selected_pattern_id=pattern)['state']['detail']
        self.assertEqual(detail['bound_module_count'],1);self.assertEqual(detail['affected_fit_count'],1)
        self.assertEqual(self.rows()[0]['named_id'],pattern)
    def test_ordinary_history_missing_pattern_refuses_without_losing_action(self):
        pattern=self.create_pattern();self.select(pattern)
        self.edit('remove_module',dict(fit_id=self.key,position=self.rows()[0]['index']))
        # Library-only delete has no direct holder or fit participant. It must
        # not silently recreate the pattern when ordinary module undo runs.
        request=self.request_damage('delete',dict(pattern_id=pattern,revision=1,bound_fit_count=0,bound_module_count=0,affected_fit_count=0))
        request['fit_id']=None
        response=json.loads(self.session.damage_dispatch(json.dumps(request)));self.assertTrue(response['ok'],response)
        before=self.stable()
        result=json.loads(self.session.dispatch(json.dumps(self.request('undo',dict(fit_id=self.key)))))
        self.assertEqual(result['status'],'error');self.assertEqual(self.stable(),before)
        undo=self.request_damage('undo');undo['fit_id']=None
        self.assertTrue(json.loads(self.session.damage_dispatch(json.dumps(undo)))['ok'])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['named_id'],pattern)
    def test_refresh_cargo_copy_dump_and_named_nonrah_refusal_restore_exact_graph(self):
        pattern=self.create_pattern();self.select(pattern);original=self.rows()[0]
        self.edit('add_command_fit',dict(source_id=self.key,target_id=self.other))
        self.assertEqual(self.rows()[0]['object_key'],original['object_key']);self.assertEqual(self.rows()[0]['named_id'],pattern)
        self.edit('remove_command_fit',dict(source_id=self.key,target_id=self.other))
        self.edit('transfer_cargo',dict(fit_id=self.key,direction='TO_CARGO',positions=[original['index']],item_id=None,copy=True))
        self.assertEqual(self.rows()[0]['object_key'],original['object_key']);self.assertEqual(self.rows()[0]['named_id'],pattern)
        repair=self.engine._item('Small Armor Repairer I').ID
        self.edit('add_cargo',dict(fit_id=self.key,item_id=repair,quantity=1))
        before=self.stable()
        request=self.request('transfer_cargo',dict(fit_id=self.key,direction='TO_CARGO',positions=[self.rows()[0]['index']],item_id=repair,copy=False))
        self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error')
        self.assertEqual(self.stable(),before)
        self.edit('transfer_cargo',dict(fit_id=self.key,direction='TO_CARGO',positions=[self.rows()[0]['index']],item_id=None,copy=False))
        self.assertEqual(self.rows(),[])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['object_key'],original['object_key']);self.assertEqual(self.rows()[0]['named_id'],pattern)
    def test_real_bulk_failed_replacement_helper_restores_original_key_and_tag(self):
        import eos.db
        from eos.saveddata.module import Module
        from android_bridge.bulk_edits import _inputs, _restore
        from android_bridge.inspection_identity import identity
        from android_bridge.module_rah import capture
        pattern=self.create_pattern();self.select(pattern);original=self.rows()[0]
        bridge=self.session.graph._bridge;fit=self.session._fits[self.key]
        old=fit.modules[original['index']];before=_inputs(fit)
        try:
            fit.modules.replace(original['index'],Module(old.item))
            eos.db.saveddata_session.flush()
            _restore(self.engine,fit,original['index'],old,before)
            restored=fit.modules[original['index']]
            self.assertIsNot(restored,old)
            self.assertEqual(identity(fit,restored),original['object_key'])
            self.assertEqual(capture(restored,bridge._rah_resolver),dict(rah_pattern=dict(mode='named',pattern_id=pattern)))
            self.assertEqual(restored.state,old.state)
        finally:bridge._recover()
        self.assertEqual(self.rows()[0]['object_key'],original['object_key'])

    def test_real_cargo_replace_helper_carries_to_new_key_without_public_swap_claim(self):
        # The public route short-circuits same-item swaps. This isolates its
        # actual _replace helper, not a claim of a second RAH item in the data.
        from android_bridge.cargo_transfers import _replace
        pattern=self.create_pattern();self.select(pattern);original=self.rows()[0]
        bridge=self.session.graph._bridge;fit=self.session._fits[self.key]
        old=fit.modules[original['index']]
        try:
            self.assertTrue(_replace(self.engine,fit,original['index'],old.item))
            captured=bridge._capture(bridge._fits,{key:row['spec'] for key,row in bridge._records.items()})
            record=captured[self.key]
            self.assertEqual(record['spec']['modules'][original['index']]['rah_pattern'],dict(mode='named',pattern_id=pattern))
            self.assertNotEqual(record['inspection_ids']['modules'][original['index']],original['object_key'])
            self.assertTrue(all('rah_pattern' not in row for row in record['spec']['cargo']))
        finally:bridge._recover()
        self.assertEqual(self.rows()[0]['object_key'],original['object_key'])

    def test_uncertain_confirmation_and_postcommit_publication_require_reopen(self):
        pattern=self.create_pattern();self.select(pattern)
        request=self.request_damage('set_module',self.row_args()|dict(selection=dict(mode='disabled')))
        with patch.object(self.session._store,'confirm',side_effect=RuntimeError('uncertain')):
            response=json.loads(self.session.damage_dispatch(json.dumps(request)))
        self.assertFalse(response['ok']);self.assertIsNone(response['committed']);self.assertTrue(response['reopen_required'])
        with self.assertRaises(ProfileError):self.session.module_rah_details(self.key)
        self.reopen();self.assertEqual(self.rows()[0]['mode'],'disabled')
        self.select(pattern)
        request=self.request_damage('set_module',self.row_args()|dict(selection=dict(mode='fit')))
        with patch.object(self.session,'_remember_versions',side_effect=RuntimeError('publication')):
            response=json.loads(self.session.damage_dispatch(json.dumps(request)))
        self.assertTrue(response['reopen_required']);self.assertIsNone(response['committed'])
        self.reopen();self.assertEqual(self.rows()[0]['mode'],'fit')

    def test_defensive_zero_preview_does_not_relax_create_or_restore(self):
        zero=dict.fromkeys(damage.DAMAGE_FIELDS,0.0)
        for restore in (False,True):
            with self.assertRaisesRegex(ValueError,'damage pattern'):
                self.engine.create_fit(dict(spec(),damage_pattern=zero),restore=restore)
        # Deliberate read-only corrupt in-memory preview fixture, never saved.
        saved=self.session.graph._state['fit_graph']['records'][self.key]['spec']
        old=deepcopy(saved['damage_pattern']);before=self.path.read_bytes()
        try:
            saved['damage_pattern']=zero
            preview=self.session.module_rah_details(self.key)['fit_pattern']
            self.assertEqual(preview,dict(name='Fit pattern',available=False,unavailable_reason='zero_total',components=None))
        finally:saved['damage_pattern']=old
        self.assertEqual(self.path.read_bytes(),before)

    def test_schema_legacy_bare_external_named_and_missing_target_refuse(self):
        pattern=self.create_pattern();self.select(pattern)
        current=deepcopy(self.session.graph._state)
        for version in range(1,7):
            candidate=deepcopy(current);candidate['version']=version
            with self.assertRaises(ProfileError):self.session.graph._validate(candidate)
        # v7 predates profile security: use its actual profile/record schema.
        legacy=deepcopy(current);legacy['version']=7;legacy['profiles']['format']=2
        for profile in legacy['profiles']['profiles'].values():profile.pop('sec_status')
        for record in legacy['fit_graph']['records'].values():record.pop('character_security')
        untagged=deepcopy(legacy)
        for record in untagged['fit_graph']['records'].values():
            for module in record['spec']['modules']:
                if module.get('rah_pattern',{}).get('mode')=='named':module.pop('rah_pattern')
        # With only the named tags removed, both legacy and bare graphs are valid.
        self.session.graph._validate(untagged)
        BridgeSession._validate_graph(untagged['fit_graph'],self.session.graph.dataset,self.engine.settings)
        with self.assertRaises(BridgeStoreError) as error:self.session.graph._validate(legacy)
        self.assertEqual(str(error.exception.__cause__),'Invalid reactive armor mode')
        with self.assertRaises(BridgeStoreError) as error:
            BridgeSession._validate_graph(legacy['fit_graph'],self.session.graph.dataset,self.engine.settings)
        self.assertEqual(str(error.exception.__cause__),'Invalid reactive armor mode')
        external=deepcopy(current['fit_graph']['records'][self.key]['spec'])
        before=self.stable();result=json.loads(self.session.dispatch(json.dumps(self.request('create_fit',dict(spec=external)))))
        self.assertEqual(result['status'],'error');self.assertEqual(self.stable(),before)
        broken=deepcopy(current);broken['damage_patterns']['patterns'].pop(pattern)
        with self.assertRaises(ProfileError) as error:self.session.graph._validate(broken)
        self.assertEqual(error.exception.code,'missing_pattern')


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(NamedRahSessionTests(name) for name in NamedRahSessionTests.__dict__ if name.startswith('test_'))
