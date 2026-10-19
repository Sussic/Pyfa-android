"""Pure G09 resource and authoritative-input guards, with fake metadata only."""
from copy import deepcopy
import json
import math
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

from android_bridge import projected_drone_budget as legacy
from android_bridge.projected_drone_admission import AdmissionRejected
from android_bridge.offline.ewar_resource import (MAX_COUNTER, DEFAULT_ALLOWANCE, PRICES,
    EwarReservation, add, mul, reserve_graph, admit_preparation, CONTRIBUTORS, MAX_WIRE_CHARS)
from android_bridge.offline.ewar_samples import sample_ewar
from test_ewar_samples import request, CONTEXT, fit as graph_fit


def effect(name, identity=6687, *, kind='projected', grouped=False):
    return NS(name=name,ID=identity,activeByDefault=True,runTime='normal',isImplemented=True,
        isType=lambda value:value==kind,getattr=lambda value:grouped if value=='grouped' else None)


def item(name, identity, effects=(), *, category='Drone', maximum=3):
    return NS(name=name,ID=identity,category=NS(name=category),effects={e.name:e for e in effects},
        isDrone=category=='Drone',isAbyssal=False,isType=lambda value:value=='projected',
        getAttribute=lambda name:maximum if name=='fighterSquadronMaxSize' else None)


def record():
    return dict(spec=dict(modules=[],drones=[],fighters=[],cargo=[],environments=[],
        projected_modules=[],projected_drones=[],projected_fighters=[]),
        implants=[],boosters=[],commands=[],projections=[])


def live(identity=1):
    f=graph_fit()
    for name in ('modules','drones','fighters','cargo','projectedModules','projectedDrones','projectedFighters','implants','boosters'):
        setattr(f,name,[])
    f.character=NS(implants=[]);f.implantLocation=0;f.appliedImplants=f.implants
    f.projectedFitDict={};f.commandFitDict={};f.ID=identity
    f.activeModulesIter=lambda:iter(f.modules)
    f.activeDronesIter=lambda:(d for d in f.drones if d.amountActive>0)
    f.activeFighterAbilityIter=lambda:((x,a) for x in f.fighters if x.active for a in x.abilities if a.active)
    return f


class LedgerTests(unittest.TestCase):
    def test_exact_allowance_then_one_refuses_without_refund(self):
        r=EwarReservation(128);r('container',1)
        self.assertEqual(r.used,128)
        with self.assertRaises(AdmissionRejected):r('serialization_unit',1)
        self.assertEqual(r.used,128);self.assertEqual(r.count,1)
    def test_checked_counter_boundaries(self):
        self.assertEqual(add(MAX_COUNTER,0),MAX_COUNTER);self.assertEqual(mul(MAX_COUNTER,1),MAX_COUNTER)
        for a,b in [(MAX_COUNTER,1),(-1,0),(True,0),(0,1.0)]:
            with self.assertRaises(AdmissionRejected):add(a,b)
        for a,b in [(MAX_COUNTER,2),(-1,1),(1,True)]:
            with self.assertRaises(AdmissionRejected):mul(a,b)
        for invalid in (-1,True,1.0,MAX_COUNTER+1):
            with self.assertRaises(AdmissionRejected):EwarReservation(invalid)
    def test_unknown_kind_and_invalid_reservation_counts(self):
        for kind,amount in [('unknown',0),('container',True),('scan',-1),('scan',MAX_COUNTER+1)]:
            with self.assertRaises(AdmissionRejected):EwarReservation()(kind,amount)
        r=EwarReservation();r('scan',MAX_COUNTER)
        with self.assertRaises(AdmissionRejected):r('scan',1)
    def test_all_mode_exact_common_point_and_sort_formulas(self):
        for mode,(*_,lists) in CONTRIBUTORS.items():
            r=EwarReservation();reserve_graph(r,mode,[(3,2)],201)
            self.assertEqual(r.counts['tuple_value'],3+201*lists*3)
            self.assertEqual(r.counts['list_slot'],6+201*lists*9)
            self.assertEqual(r.counts['sort_slot'],201*lists*12)
            self.assertEqual(r.counts['mapping_slot'],201*lists)
            self.assertEqual(r.counts['sort_work'],2*lists*201*3*2)
            self.assertEqual(r.counts['repair_parameter_call'],2 if mode=='neutStr' else 0)
    def test_guidance_reserves_both_lists_even_unity(self):
        a=EwarReservation();b=EwarReservation()
        reserve_graph(a,'webStr',[(8,0)],201);reserve_graph(b,'gdStrRange',[(8,0)],201)
        self.assertEqual(b.counts['sort_slot'],2*a.counts['sort_slot'])
        self.assertEqual(b.counts['tuple_value']-8,2*(a.counts['tuple_value']-8))
    def test_explicit_one_point_bound_and_invalid_bool(self):
        a=EwarReservation();reserve_graph(a,'webStr',[(3,0)],1)
        self.assertEqual(a.counts['output_point'],1);self.assertEqual(a.counts['sort_slot'],12)
        for invalid in (True,0,2,200,202):
            with self.assertRaises(AdmissionRejected):reserve_graph(EwarReservation(),'webStr',[(0,0)],invalid)
    def test_eight_fit_cumulative_refusal_not_individual_reset(self):
        individual=EwarReservation();reserve_graph(individual,'webStr',[(200,0)],201)
        self.assertLess(individual.used,DEFAULT_ALLOWANCE)
        with self.assertRaises(AdmissionRejected):reserve_graph(EwarReservation(),'webStr',[(200,0)]*8,201)
    def test_output_ceilings_and_counter_overflow(self):
        r=EwarReservation();reserve_graph(r,'neutStr',[(0,0)]*8,201)
        self.assertEqual(r.counts['output_point'],1608)
        for bounds in ([],[(0,0)]*9,[(MAX_COUNTER,0)],[(True,0)]):
            with self.assertRaises(AdmissionRejected):reserve_graph(EwarReservation(),'webStr',bounds,201)


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.catalog={}
        fake=ModuleType('eos');db=ModuleType('eos.db');db.getItem=self.catalog.get;fake.db=db
        ctx=patch.dict(sys.modules,{'eos':fake,'eos.db':db});ctx.start();self.addCleanup(ctx.stop)
        self.records={'fit':record()};self.fits={'fit':live()};self.revisions={'fit':1}
    def add_drone(self, amount=3, active=2, *, key='fit', incoming=False):
        e=effect('remoteWebifierEntity',6690);i=item('Web',1,[e]);self.catalog['Web']=i
        row=dict(name='Web',amount=amount,active=active)
        obj=NS(item=i,amount=amount,amountActive=active,projectionRange=None,
               getModifiedItemAttr=lambda name:-20 if name=='speedFactor' else 0)
        if incoming:row['range_m']=None
        self.records[key]['spec']['projected_drones' if incoming else 'drones'].append(row)
        getattr(self.fits[key],'projectedDrones' if incoming else 'drones').append(obj)
        return obj
    def add_fighter(self, amount=3, *, raw=None, abilities=True, grouped=True):
        e=effect('fighterAbilityStasisWebifier',6435,grouped=grouped)
        i=item('Fighter',2,[e],category='Fighter');self.catalog['Fighter']=i
        row=dict(name='Fighter',amount=amount,active=True)
        if abilities:row['abilities']=[dict(effect_id=e.ID,active=True)]
        class Fighter:
            @property
            def amount(self):raise AssertionError('derived fighter quantity before admission')
            def getModifiedItemAttr(self,*args):raise AssertionError('derived attribute before admission')
        obj=Fighter();obj.item=i;obj._amount=amount if raw is None else raw
        obj.active=True;obj.abilities=[NS(effectID=e.ID,effect=e,active=True)]
        self.records['fit']['spec']['fighters'].append(row);self.fits['fit'].fighters.append(obj)
        return obj
    def admit(self, mode='webStr', *, rows=None,reserve=None):
        rows=rows or [dict(fit_id='fit',revision=1)]
        return admit_preparation(self.records,self.fits,self.revisions,list(self.fits.values()),rows,
            [self.fits[row['fit_id']] for row in rows],mode,EwarReservation() if reserve is None else reserve,
            lambda:None,lookup=self.catalog.get)
    def sample(self,r=None,**kwargs):
        def prep(rows,handles,mode,reserve,check):
            return admit_preparation(self.records,self.fits,self.revisions,list(self.fits.values()),rows,
                handles,mode,reserve,check,lookup=self.catalog.get)
        return sample_ewar(request() if r is None else r,resolve_fit=lambda k:(self.fits[k],self.revisions[k]),
            current_context=lambda:CONTEXT,clock=lambda:0,prep_admit=prep,**kwargs)
    def test_legacy_zero_incoming_exemption_unchanged(self):
        with patch.object(sys.modules['eos.db'],'getItem',side_effect=AssertionError('catalogue lookup')):
            self.assertEqual(legacy.admit(self.records),dict(enabled=False,cold_units=0,request_units=0))
    def test_opt_in_admits_local_only_without_changing_prices(self):
        self.add_drone();out=legacy.admit(self.records,include_local_only=True,extra_module=False,extra_edge=False)
        self.assertTrue(out['enabled']);self.assertEqual(out['request_phases'],8)
        self.assertEqual(legacy.MAX_COLD_UNITS,16384);self.assertEqual(legacy.MAX_REQUEST_UNITS,134217728)
        for bad in (1,None,'true'):
            with self.assertRaises(AdmissionRejected):legacy.admit(self.records,include_local_only=bad)
    def test_partial_active_drone_count_not_total_quantity(self):
        self.add_drone(amount=99,active=2);self.assertEqual(self.admit(),[(2,0)])
    def test_six_drone_mode_metadata_counts(self):
        for mode,(_,drone,_,_) in CONTRIBUTORS.items():
            if drone is None:continue
            self.records={'fit':record()};self.fits={'fit':live()}
            obj=self.add_drone(amount=7,active=4);e=effect(drone,6690)
            obj.item.effects={drone:e}
            self.assertEqual(self.admit(mode),[(4,0)])
    def test_huge_local_drone_refuses_before_local_or_common_data(self):
        obj=self.add_drone(amount=2**31-1,active=2**31-1);calls=[]
        obj.getModifiedItemAttr=lambda *a:(_ for _ in ()).throw(AssertionError('unsafe derived access'))
        out=self.sample(prepare_fit=lambda f:calls.append(f))
        self.assertEqual(out['error']['code'],'resource_exhausted');self.assertEqual(calls,[])
        self.records['fit']['spec']['drones'][0].update(amount=1,active=1);obj.amount=obj.amountActive=1
        obj.getModifiedItemAttr=lambda n:-20
        self.assertTrue(self.sample()['ok'])
    def test_huge_local_fighter_refuses_before_derived_quantity_or_local(self):
        self.add_fighter(amount=2**31-1,grouped=False);calls=[]
        out=self.sample(prepare_fit=lambda f:calls.append(f))
        self.assertEqual(out['error']['code'],'resource_exhausted');self.assertEqual(calls,[])
    def test_maximum_fighter_sentinel_matches_normalized_record(self):
        self.add_fighter(raw=-1);self.assertEqual(self.admit(),[(1,0)])
    def test_invalid_fighter_maximum_metadata_fails_before_int(self):
        self.add_fighter(raw=-1)
        for bad in (True,None,math.inf,math.nan,-1,3.5,2**31):
            self.catalog['Fighter'].getAttribute=lambda key,v=bad:v
            with self.assertRaises(AdmissionRejected):self.admit()
    def test_fighter_raw_mismatch_and_ability_mismatch(self):
        f=self.add_fighter();f._amount=2
        with self.assertRaises(AdmissionRejected):self.admit()
        f._amount=3;f.abilities[0].active=False
        with self.assertRaises(AdmissionRejected):self.admit()
    def test_legacy_omitted_ability_membership_still_checked(self):
        f=self.add_fighter(abilities=False);self.assertEqual(self.admit(),[(1,0)])
        f.abilities*=2
        with self.assertRaises(AdmissionRejected):self.admit()
        f.abilities=f.abilities[:1];f.abilities[0].effectID=123
        with self.assertRaises(AdmissionRejected):self.admit()
    def test_unknown_edges_and_engine_identity_fail_closed(self):
        self.records['fit']['commands']=[dict(source_id='missing',active=True)]
        self.fits['fit'].commandFitDict[2]=live(2)
        with self.assertRaises(AdmissionRejected):self.admit()
        self.records['fit']['commands']=[];self.fits['fit'].commandFitDict={}
        with self.assertRaises(AdmissionRejected):
            admit_preparation(self.records,self.fits,self.revisions,[live()],request()['fits'],
                              [self.fits['fit']],'webStr',EwarReservation(),lambda:None,lookup=self.catalog.get)
    def test_drone_and_container_authority_mismatch(self):
        obj=self.add_drone();obj.amountActive=3
        with self.assertRaises(AdmissionRejected):self.admit()
        obj.amountActive=2;self.fits['fit'].drones.append(obj)
        with self.assertRaises(AdmissionRejected):self.admit()
    def test_environment_and_projector_prefix_stream_without_copy(self):
        for name in ('Environment','Projector'):
            i=item(name,len(self.catalog)+1,[],category='Module');self.catalog[name]=i
            self.fits['fit'].projectedModules.append(NS(item=i))
        self.records['fit']['spec']['environments']=[dict(name='Environment')]
        self.records['fit']['spec']['projected_modules']=[dict(name='Projector')]
        self.assertEqual(self.admit(),[(0,0)])
        self.fits['fit'].projectedModules.reverse()
        with self.assertRaises(AdmissionRejected):self.admit()
    def test_module_branch_overlap_pre_reserves_all_neut_durations(self):
        es=[effect(name,index+100) for index,name in enumerate(CONTRIBUTORS['neutStr'][0])]
        i=item('Overlapping',8,es,category='Module');self.catalog[i.name]=i
        self.records['fit']['spec']['modules']=[dict(name=i.name)]
        self.fits['fit'].modules=[NS(item=i)]
        self.assertEqual(self.admit('neutStr'),[(4,4)])
    def test_admission_does_not_mutate_records(self):
        self.add_drone();before=deepcopy(self.records);self.admit();self.assertEqual(before,self.records)
    def test_snapshot_scratch_is_charged_before_helper(self):
        self.add_drone()
        with patch.object(legacy,'admit',side_effect=AssertionError('helper before reserve')):
            with self.assertRaises(AdmissionRejected):self.admit(reserve=EwarReservation(2048))
    def test_incoming_cap_reset_reservation_covers_full_cold_not_clamped(self):
        self.add_drone(incoming=True);r=EwarReservation()
        out=legacy.admit(self.records,include_local_only=True,extra_module=False,extra_edge=False)
        self.admit(reserve=r);cold=out['cold_units']
        self.assertGreater(cold,0);self.assertEqual(r.counts['tuple_value'],4*cold)
        self.assertGreaterEqual(r.counts['mapping_slot'],2*cold)
    def test_projected_self_multiplicity_and_command_closure(self):
        self.add_drone();f=self.fits['fit']
        info=NS(amount=2**31-1,active=True,projectionRange=None)
        f.projectedFitDict={f.ID:f};f.getProjectionInfo=lambda k:info
        self.records['fit']['projections']=[dict(source_id='fit',amount=info.amount,active=True,range_m=None)]
        with self.assertRaises(AdmissionRejected):self.admit()
        info.amount=1;self.records['fit']['projections'][0]['amount']=1
        self.assertEqual(self.admit(),[(2,0)])
    def test_projected_source_commands_are_in_whole_library_admission(self):
        self.records['source']=record();self.records['command']=record()
        self.fits['source']=live(2);self.fits['command']=live(3)
        self.revisions.update(source=1,command=1)
        self.add_drone(key='command',amount=3,active=1)
        target,source,command=(self.fits[k] for k in ('fit','source','command'))
        target.projectedFitDict[source.ID]=source
        source.getProjectionInfo=lambda key:NS(active=True,amount=1,projectionRange=None)
        self.records['fit']['projections']=[dict(source_id='source',active=True,amount=1,range_m=None)]
        source.commandFitDict[command.ID]=command
        command.getCommandInfo=lambda key:NS(active=True)
        self.records['source']['commands']=[dict(source_id='command',active=True)]
        baseline=legacy.admit(self.records,include_local_only=True,extra_module=False,extra_edge=False)
        self.assertEqual(self.admit(),[(0,0)])
        # Source command closure contributes its LOCAL quantity cost before any
        # selected target preparation, in either durable library insertion order.
        for records in (self.records,dict(reversed(list(self.records.items())))):
            with patch.object(legacy,'admit',wraps=legacy.admit) as admitted:
                original=self.records;self.records=records
                self.assertEqual(self.admit(),[(0,0)])
                self.assertIs(admitted.call_args.args[0],records);self.records=original
        source.commandFitDict={};self.records['source']['commands']=[]
        without=legacy.admit(self.records,include_local_only=True,extra_module=False,extra_edge=False)
        self.assertGreater(baseline['cold_units'],without['cold_units'])
    def test_all_mode_module_predicates_are_independently_counted(self):
        for mode,(names,_,_,_) in CONTRIBUTORS.items():
            self.records={'fit':record()};self.fits={'fit':live()}
            i=item('Overlap',10,[effect(name,index+100) for index,name in enumerate(names)],category='Module')
            self.catalog['Overlap']=i;self.records['fit']['spec']['modules']=[dict(name='Overlap')]
            self.fits['fit'].modules=[NS(item=i)]
            self.assertEqual(self.admit(mode),[(len(names),len(names) if mode=='neutStr' else 0)])
    def test_record_order_does_not_reorder_requested_fits(self):
        self.records['other']=record();self.fits['other']=live(2);self.revisions['other']=1
        self.add_drone(key='other',amount=4,active=4)
        rows=[dict(fit_id='other',revision=1),dict(fit_id='fit',revision=1)]
        self.assertEqual(self.admit(rows=rows),[(4,0),(0,0)])
        self.records=dict(reversed(list(self.records.items())))
        self.assertEqual(self.admit(rows=rows),[(4,0),(0,0)])
    def test_native_facade_uses_authoritative_records_before_prepare(self):
        from android_bridge.offline.native_session import NativeSession
        calls=[];owned=self.records
        bridge=NS(_records=owned,_fits=self.fits,_revisions=self.revisions,
                  _capture=lambda *a:(_ for _ in ()).throw(AssertionError('capture')))
        facade=NS(graph=NS(_ready=lambda:None,_verify_durable=lambda:calls.append('durable'),_bridge=bridge),
            _fits=self.fits,_revisions=self.revisions,context=lambda:CONTEXT,
            engine=NS(_fits=list(self.fits.values()),prepare_read=lambda f:calls.append('prepare')))
        original=legacy.admit
        def admit(records,**kwargs):
            self.assertIs(records,owned);self.assertNotIn('prepare',calls);calls.append('admit')
            return original(records,**kwargs)
        with patch.object(legacy,'admit',side_effect=admit),patch.object(legacy,'live_records',side_effect=AssertionError('snapshot')):
            out=json.loads(NativeSession.ewar_samples(facade,json.dumps(request())))
        self.assertTrue(out['ok'],out);self.assertEqual(calls,['durable','admit','prepare','durable'])
    def test_native_unavailable_and_durable_mismatch_are_reopen_errors(self):
        from android_bridge.offline.native_session import NativeSession
        from android_bridge.offline.profiles import ProfileError
        from android_bridge.offline.profile_store import StoreUncertain
        def unavailable():raise ProfileError('reopen_required','internal detail')
        out=json.loads(NativeSession.ewar_samples(NS(graph=NS(_ready=unavailable)),json.dumps(request())))
        self.assertEqual(out['error']['code'],'reopen_required');self.assertNotIn('internal detail',str(out))
        disabled=[]
        def uncertain():raise StoreUncertain('private detail')
        facade=NS(graph=NS(_ready=lambda:None,_verify_durable=uncertain),_disable=lambda:disabled.append(True))
        out=json.loads(NativeSession.ewar_samples(facade,json.dumps(request())))
        self.assertEqual(out['error']['code'],'reopen_required');self.assertEqual(disabled,[True])
    def test_native_malformed_raw_request_never_prepares(self):
        from android_bridge.offline.native_session import NativeSession
        facade=NS(graph=NS(_ready=lambda:None))
        for value in (None,' '*16385,'{"version":1,"version":1}','[NaN]','{'):
            out=json.loads(NativeSession.ewar_samples(facade,value))
            self.assertEqual(out['error']['code'],'invalid_request');self.assertNotIn('series',out)


if __name__=='__main__':unittest.main()
