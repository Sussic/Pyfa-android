"""Atomic incoming script scope, preview and durable history integration."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_projected_module_bulk import ProjectedModuleBulkTests
from android_bridge.offline.profile_store import StoreWriteRejected


class ProjectedModuleChargeTests(ProjectedModuleBulkTests):
    def preview(self, indices=(2, 0), main=0, scope='SELECTED', name='Targeting Range Script'):
        request = dict(main=self.selection([main])[0], selection=self.selection(indices), scope=scope,
                       charge_id=None if name is None else self.engine._item(name).ID)
        return request, self.session.projected_module_charge_preview(self.key, request)

    def apply(self, request, preview):
        pair = lambda r:dict(position=r['index'], object_key=r['object_key'])
        return self.edit('set_projected_module_charges', dict(fit_id=self.key, **request,
            expected_targets=[pair(r) for r in preview['targets']],
            expected_changes=[pair(r) for r in preview['targets'] if r['status']=='change']))

    def state(self):
        return (deepcopy(self.session._records), deepcopy(self.session.history_details(self.key)), self.path.read_bytes())

    def test_selected_container_order_real_scripts_one_history_undo_redo_reopen(self):
        self.seed(drone=True);request, preview=self.preview()
        self.assertEqual([r['index'] for r in preview['selection']],[2,0])
        self.assertEqual([r['index'] for r in preview['targets']],[0,2])
        self.assertEqual([r['status'] for r in preview['targets']],['change','change'])
        self.assertTrue(preview['available']);self.assertEqual(preview['excluded'],[])
        self.assertIn('Scan Resolution Script',{r['name'] for r in preview['choices']})
        before=deepcopy(self.session._records);recent=self.session.recent_items();count=self.session.history_details(self.key)['undo_count']
        self.apply(request,preview);after=deepcopy(self.session._records)
        for i in (0,2):self.assertEqual(after[self.key]['spec']['projected_modules'][i]['charge'],'Targeting Range Script')
        for i in (1,3):self.assertEqual(after[self.key]['spec']['projected_modules'][i],before[self.key]['spec']['projected_modules'][i])
        self.assertEqual(after[self.key]['inspection_ids'],before[self.key]['inspection_ids'])
        self.assertEqual(self.session.history_details(self.key)['undo_count'],count+1)
        self.assertEqual(self.session.recent_items(),recent)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.session._records,before)
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.session._records,after)
        self.reopen();self.assertEqual(self.session._records,after)

    def test_similar_includes_unselected_and_clear_noop_history(self):
        self.seed();request,preview=self.preview(indices=(0,),scope='SIMILAR')
        self.assertEqual([r['index'] for r in preview['targets']],[0,1,2])
        self.apply(request,preview)
        request,preview=self.preview(indices=(0,),scope='SIMILAR')
        self.assertEqual({r['status'] for r in preview['targets']},{'unchanged'})
        count=self.session.history_details(self.key)['undo_count'];self.apply(request,preview)
        self.assertEqual(self.session.history_details(self.key)['undo_count'],count)
        request,preview=self.preview(indices=(0,),scope='SIMILAR',name=None);self.apply(request,preview)
        self.assertTrue(all(row['charge'] is None for row in self.session._records[self.key]['spec']['projected_modules']))

    def test_empty_compatible_subset_resolves_then_source_calc_skips(self):
        self.seed();request,preview=self.preview(indices=(3,0))
        self.assertEqual([r['index'] for r in preview['targets']],[0,3])
        self.assertEqual([r['status'] for r in preview['targets']],['change','incompatible'])
        before=deepcopy(self.session._records[self.key]['spec']['projected_modules'][3]);self.apply(request,preview)
        self.assertEqual(self.session._records[self.key]['spec']['projected_modules'][3],before)
        request,preview=self.preview(indices=(3,0),scope='SIMILAR')
        self.assertEqual([r['index'] for r in preview['excluded']],[3])

    def test_bad_main_stale_selection_charge_and_preview_are_atomic(self):
        self.seed(environment=True);request,preview=self.preview(indices=(3,1),main=1)
        before=self.state()
        bad=[]
        for key,value in [('scope','all'),('charge_id',True),('charge_id',self.engine._item('Antimatter Charge S').ID),('main',self.selection([2])[0]),('selection',[])]:
            row=deepcopy(request);row[key]=value;bad.append(row)
        row=deepcopy(request);row['selection'][0]['object_key']='stale';bad.append(row)
        row=deepcopy(request);row['main']['position']=True;bad.append(row)
        for row in bad:
            with self.assertRaises((ValueError,TypeError)):self.session.projected_module_charge_preview(self.key,row)
            self.assertEqual(self.state(),before)
        stale=deepcopy(preview);stale['targets'].reverse()
        with self.assertRaises(AssertionError):self.apply(request,stale)
        self.assertEqual(self.state(),before)
        self.edit('set_projected_module_range',dict(fit_id=self.key,**request['main'],range_m=4321))
        wire=self.request('set_projected_module_charges',dict(fit_id=self.key,**request,expected_targets=[],expected_changes=[]))
        wire['expected_revisions'][self.key]=preview['revision']
        saved=self.state();result=json.loads(self.session.dispatch(json.dumps(wire)))
        self.assertEqual(result['status'],'error');self.assertEqual(self.state(),saved)

    def test_write_rejection_rolls_back_joint_charges_and_preserves_availability(self):
        self.seed(drone=True);request,preview=self.preview(scope='SIMILAR');before=self.state()
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic charge write refusal')):
            with self.assertRaises(AssertionError):self.apply(request,preview)
        self.assertEqual(self.state(),before);self.assertTrue(self.session.graph._bridge._available)
        self.apply(request,preview)

    def test_query_prepares_local_without_write_or_history(self):
        self.seed();request,_=self.preview();before=self.state();engine=self.engine
        with patch.object(engine,'prepare_read',wraps=engine.prepare_read) as prepare, patch.object(self.session._store,'write',side_effect=AssertionError('preview must not write')):
            preview=self.session.projected_module_charge_preview(self.key,request)
            self.assertEqual(prepare.call_count,1)
        self.assertEqual(self.state(),before);self.assertEqual(preview['revision'],self.session._revisions[self.key])

    def test_refreshes_copy_profile_and_restart_preserve_charges_and_ids(self):
        self.seed();request,preview=self.preview(scope='SIMILAR');self.apply(request,preview)
        source=self.key;expected=deepcopy(self.session._records[source]['spec']['projected_modules']);ids=deepcopy(self.session._records[source]['inspection_ids'])
        from test_native_session import spec
        other=self.edit('create_fit',dict(spec=dict(spec(),name='Charge recipient')))['fits'][0]['id']
        for operation,args in [
            ('add_projection',dict(source_id=source,target_id=other,range_m=0,active=True,amount=1)),
            ('remove_projection',dict(source_id=source,target_id=other)),
            ('add_command',dict(source_id=source,target_id=other,active=True)),
            ('remove_command',dict(source_id=source,target_id=other)),
            ('add_command_fit',dict(source_id=source,target_id=other)),
            ('remove_command_fit',dict(source_id=source,target_id=other))]:
            self.edit(operation,args);self.assertEqual(self.session._records[source]['spec']['projected_modules'],expected)
            self.assertEqual(self.session._records[source]['inspection_ids'],ids)
        self.feature('assign_profile',dict(fit_id=source,profile_id='builtin:all0'))
        old=set(self.session._fits);self.edit('duplicate_fit',dict(fit_id=source,name='Charge copy'))
        copied=next(k for k in self.session._fits if k not in old)
        self.assertEqual(self.session._records[copied]['spec']['projected_modules'],expected)
        self.assertNotEqual(self.session._records[copied]['inspection_ids'],ids)
        self.reopen();self.assertEqual(self.session._records[source]['spec']['projected_modules'],expected)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(ProjectedModuleChargeTests(name) for name in ProjectedModuleChargeTests.__dict__ if name.startswith('test_'))
