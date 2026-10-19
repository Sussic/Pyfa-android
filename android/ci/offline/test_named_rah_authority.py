"""D05.4 authority and history tests; synthetic inputs, no numerical oracle.

Prepared source only until the parent admits execution. EOS materialization is
covered separately; pure cases never approximate hardener calculations.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from android_bridge.offline import damage_patterns as damage, named_rah
from android_bridge.offline.graph_history import GraphHistory, inputs
from android_bridge.offline.profiles import ProfileError
from test_damage_patterns import F, G, CONTEXT, raw, zero, state, wire

P='damage:'+'1'*32
Q='damage:'+'2'*32
A='3'*32
B='4'*32
C='5'*32


def fixture():
    value=state(8)
    value['damage_patterns']['patterns'][P]=dict(name='Shared',values=raw(),revision=1)
    value['damage_patterns']['patterns'][Q]=dict(name='Equal but distinct',values=raw(),revision=1)
    for fit,key,status in ((F,A,'OFFLINE'),(G,B,'ONLINE')):
        record=value['fit_graph']['records'][fit]
        record['spec']['modules']=[dict(name='Reactive Armor Hardener',state=status,rah_pattern=dict(mode='named',pattern_id=P))]
        record['inspection_ids']=dict(modules=[key])
    return value


class NamedRahAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.value=fixture()
        self.engine=SimpleNamespace(_item=lambda name:SimpleNamespace(ID=4403,name=name,group=SimpleNamespace(name='Armor Resistance Shift Hardener')))
    def test_exact_inventory_counts_inactive_overlapping_and_identity(self):
        damage.mutate(self.value,'assign',dict(pattern_id=P,revision=1,fit_revision=1),F)
        holders=named_rah.inventory(self.value['fit_graph']['records'],self.value['damage_patterns'],P)
        self.assertEqual(holders,dict(incoming=(F,),modules=((F,A),(G,B))))
        self.assertEqual(named_rah.holder_fits(self.value['fit_graph']['records'],self.value['damage_patterns'],P),{F,G})
        self.assertEqual(named_rah.inventory(self.value['fit_graph']['records'],self.value['damage_patterns'],Q),dict(incoming=(),modules=()))
    def test_shared_edit_includes_module_only_without_incoming_assignment(self):
        before=deepcopy(self.value['fit_graph']['records'])
        _,affected=damage.mutate(self.value,'update_values',dict(pattern_id=P,revision=1,values=raw(emAmount=17.0)),None)
        self.assertEqual(affected,{F,G});self.assertEqual(self.value['damage_patterns']['bindings'],{})
        self.assertTrue(damage.exact(before,self.value['fit_graph']['records']))
        _,affected=damage.mutate(self.value,'rename',dict(pattern_id=P,revision=2,name='Renamed'),None)
        self.assertEqual(affected,{F,G})
    def test_assigned_zero_refuses_inactive_and_unrelated_zero_remains_valid(self):
        before=deepcopy(self.value)
        with self.assertRaises(ProfileError) as error:
            damage.mutate(self.value,'update_values',dict(pattern_id=P,revision=1,values=zero()),None)
        self.assertEqual(error.exception.code,'unassignable');self.assertTrue(damage.exact(before,self.value))
        damage.mutate(self.value,'update_values',dict(pattern_id=Q,revision=1,values=zero()),None)
        result=damage.state_view(self.value,CONTEXT,F,wire()['view']|dict(selected_pattern_id=Q),GraphHistory(),engine=self.engine)
        self.assertFalse(result['detail']['assignable']);self.assertEqual(result['detail']['bound_module_count'],0)
    def test_dual_delete_distinct_fallbacks_and_three_impact_counts(self):
        damage.mutate(self.value,'assign',dict(pattern_id=P,revision=1,fit_revision=1),F)
        args=dict(pattern_id=P,revision=1,bound_fit_count=1,bound_module_count=2,affected_fit_count=2)
        for field in ('bound_fit_count','bound_module_count','affected_fit_count'):
            before=deepcopy(self.value)
            with self.assertRaises(ProfileError):damage.mutate(self.value,'delete',args|{field:0},None)
            self.assertTrue(damage.exact(before,self.value))
        _,affected=damage.mutate(self.value,'delete',args,None)
        self.assertEqual(affected,{F,G});self.assertNotIn(P,self.value['damage_patterns']['patterns'])
        self.assertEqual(self.value['damage_patterns']['bindings'][F]['pattern_id'],damage.UNIFORM)
        self.assertNotIn(G,self.value['damage_patterns']['bindings'])
        self.assertTrue(all('rah_pattern' not in record['spec']['modules'][0] for record in self.value['fit_graph']['records'].values()))
    def test_selected_ammo_module_only_refresh_never_binds_other_holders(self):
        ledger=self.value['damage_patterns']
        ledger['patterns'][damage.SELECTED_AMMO]=dict(name='Selected Ammo',values=raw(),revision=1)
        for record in self.value['fit_graph']['records'].values():record['spec']['modules'][0]['rah_pattern']['pattern_id']=damage.SELECTED_AMMO
        item=dict(item_id=185,name='Synthetic base item',eligible=True,available=True,unavailable_reason=None,values=dict(emAmount=9.0,thermalAmount=0,kineticAmount=1.0,explosiveAmount=2.0))
        _,affected=damage.mutate(self.value,'apply_item',dict(item_id=185,fit_revision=1),G,item=item)
        self.assertEqual(affected,{F,G});self.assertEqual(set(ledger['bindings']),{G})
        before=deepcopy(self.value)
        self.assertEqual(damage.mutate(self.value,'apply_item',dict(item_id=185,fit_revision=1),G,item=item)[1],set())
        self.assertTrue(damage.exact(before,self.value))
    def test_strict_wire_old_version_missing_counts_and_selection_fields(self):
        args=dict(fit_revision=1,object_key=A,position=0,selection=dict(mode='named',pattern_id=P,revision=1))
        request=wire('set_module',args)
        damage.request(request,CONTEXT,self.value['fit_graph']['records'],self.value['damage_patterns'])
        for invalid in (request|dict(version=2),request|dict(version=True),request|dict(view=wire()['view']|dict(module_offset=True)),
                        wire('set_module',args|dict(selection=args['selection']|dict(values=raw()))),
                        wire('set_module',args|dict(selection=dict(mode='named',pattern_id=damage.UNIFORM,revision=0))),
                        wire('delete',dict(pattern_id=P,revision=1,bound_fit_count=0))):
            with self.assertRaises(ProfileError):damage.request(invalid,CONTEXT,self.value['fit_graph']['records'],self.value['damage_patterns'])
    def test_target_checks_fit_key_position_group_and_noop(self):
        args=dict(fit_revision=1,object_key=A,position=0,selection=dict(mode='named',pattern_id=P,revision=1))
        before=deepcopy(self.value)
        self.assertEqual(named_rah.set_module(self.value,F,args,self.engine),(None,set()))
        self.assertTrue(damage.exact(before,self.value))
        for change,code in ((dict(fit_revision=2),'stale_fit'),(dict(object_key=C),'stale_module'),(dict(position=1),'stale_module'),
                            (dict(selection=dict(mode='named',pattern_id=P,revision=2)),'stale_pattern')):
            with self.assertRaises(ProfileError) as error:named_rah.set_module(self.value,F,args|change,self.engine)
            self.assertEqual(error.exception.code,code);self.assertTrue(damage.exact(before,self.value))
        self.engine._item=lambda name:SimpleNamespace(group=SimpleNamespace(name='Armor Repair Unit'))
        with self.assertRaises(ProfileError) as error:named_rah.set_module(self.value,F,args,self.engine)
        self.assertEqual(error.exception.code,'stale_module')
    def test_named_tag_alignment_and_nonrah_missing_zero_validation(self):
        named_rah.validate(self.value['fit_graph']['records'],self.value['damage_patterns'],self.engine)
        for change in (lambda s:s['fit_graph']['records'][F]['inspection_ids']['modules'].append(C),
                       lambda s:s['fit_graph']['records'][F]['spec']['modules'][0]['rah_pattern'].update(revision=1),
                       lambda s:s['damage_patterns']['patterns'].pop(P),
                       lambda s:s['damage_patterns']['patterns'][P].update(values=zero())):
            candidate=deepcopy(self.value);change(candidate)
            with self.assertRaises(ProfileError):named_rah.validate(candidate['fit_graph']['records'],candidate['damage_patterns'],self.engine)
    def test_history_keeps_named_tags_and_exact_source_destination_inventories(self):
        before=deepcopy(self.value)
        damage.mutate(self.value,'rename',dict(pattern_id=P,revision=1,name='After'),None)
        history=GraphHistory().record(before,self.value,'Rename shared',{'library',F,G})
        action=history.rows['library'][0][0]
        self.assertEqual(action.damage_holders,((P,dict(incoming=(),modules=((F,A),(G,B))),dict(incoming=(),modules=((F,A),(G,B)))),))
        self.assertEqual(inputs(self.value)['records'][F]['spec']['modules'][0]['rah_pattern'],dict(mode='named',pattern_id=P))
        restored,_,_=history.replay('library',False,self.value)
        self.assertEqual(restored['damage_patterns']['patterns'][P]['name'],'Shared')
    def test_later_same_fit_clone_blocks_shared_replay_before_field_changes(self):
        before=deepcopy(self.value)
        damage.mutate(self.value,'rename',dict(pattern_id=P,revision=1,name='After'),None)
        history=GraphHistory().record(before,self.value,'Rename shared',{'library',F,G})
        record=self.value['fit_graph']['records'][F]
        record['spec']['modules'].append(deepcopy(record['spec']['modules'][0]));record['inspection_ids']['modules'].append(C)
        snapshot=deepcopy(self.value);details=history.details('library')
        with self.assertRaises(ProfileError) as error:history.replay('library',False,self.value)
        self.assertEqual(error.exception.code,'history_dependency');self.assertEqual(history.details('library'),details)
        self.assertTrue(damage.exact(snapshot,self.value))
    def test_same_count_holder_substitution_blocks_history(self):
        before=deepcopy(self.value)
        damage.mutate(self.value,'rename',dict(pattern_id=P,revision=1,name='After'),None)
        history=GraphHistory().record(before,self.value,'Rename shared',{'library',F,G})
        self.value['fit_graph']['records'][F]['inspection_ids']['modules'][0]=C
        with self.assertRaises(ProfileError) as error:history.replay('library',False,self.value)
        self.assertEqual(error.exception.code,'history_dependency')
    def test_bounded_module_holder_pages_and_raw_types(self):
        result=damage.state_view(self.value,CONTEXT,F,wire()['view']|dict(selected_pattern_id=P),GraphHistory(),engine=self.engine)
        detail=result['detail'];self.assertEqual(detail['bound_fit_count'],0);self.assertEqual(detail['bound_module_count'],2)
        self.assertEqual(detail['affected_fit_count'],2)
        self.assertEqual([(r['fit_id'],r['object_key'],r['position']) for r in detail['bound_modules']['entries']],[(F,A,0),(G,B,0)])
        result=damage.state_view(self.value,CONTEXT,F,wire()['view']|dict(selected_pattern_id=P,module_offset=2),GraphHistory(),engine=self.engine)
        self.assertEqual(result['detail']['bound_modules']['entries'],[])
    def test_candidate_resolver_identity_never_matches_names_values_or_orm_ids(self):
        import sys
        from types import ModuleType
        from unittest.mock import patch
        from android_bridge.module_rah import capture, CUSTOM_ERROR
        class Pattern:
            def __init__(self,**values):
                self.__dict__.update(values);self.ID=None
            @classmethod
            def getBuiltinById(cls,key):return None
        module=ModuleType('eos.saveddata.damagePattern');module.DamagePattern=Pattern
        with patch.dict(sys.modules,{'eos.saveddata.damagePattern':module}):
            old=named_rah.Resolver(self.value['damage_patterns'])
            first=old.resolve(P);self.assertIs(old.resolve(P),first)
            self.assertIsNot(old.resolve(Q),first)
            changed=deepcopy(self.value['damage_patterns']);changed['patterns'][P]['values']=raw(emAmount=-0.0)
            fresh=named_rah.Resolver(changed);new=fresh.resolve(P)
            self.assertIsNot(new,first);self.assertIsNone(fresh.identify(first))
            holder=SimpleNamespace(item=SimpleNamespace(group=SimpleNamespace(name='Armor Resistance Shift Hardener')),rahPatternOverride=new)
            self.assertEqual(capture(holder,fresh),dict(rah_pattern=dict(mode='named',pattern_id=P)))
            self.assertTrue(damage.exact(new.emAmount,-0.0))
            with self.assertRaisesRegex(ValueError,CUSTOM_ERROR):capture(holder,old)
            holder.rahPatternOverride=Pattern(**changed['patterns'][P]['values']);holder.rahPatternOverride.rawName='Shared'
            with self.assertRaisesRegex(ValueError,CUSTOM_ERROR):capture(holder,fresh)

    def test_delete_revision_exhaustion_preserves_candidate(self):
        before=deepcopy(self.value)
        with self.assertRaises(ProfileError) as error:
            damage.mutate(self.value,'delete',dict(pattern_id=P,revision=1,bound_fit_count=0,bound_module_count=2,affected_fit_count=2),None,pattern_floor={P:damage.MAX_INT})
        self.assertEqual(error.exception.code,'revision');self.assertTrue(damage.exact(before,self.value))


if __name__=='__main__':unittest.main()
