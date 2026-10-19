"""Pure host checker tests. Synthetic reports are not Android evidence."""
import ast
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import drone_delivery as d
import local_verification as launcher


class DroneDeliveryTests(unittest.TestCase):
    def test_preserves_exact_inherited_plan_and_adds_required_gates(self):
        source=subprocess.check_output(['git','show','cbda3ade:android/ci/local_verification.py'],cwd=d.ROOT,text=True)
        nodes=[n for n in ast.parse(source).body if
               isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in
                 ('FAMILIES','HEADLESS','BUILD','INSPECTOR') for t in n.targets) or
               isinstance(n,ast.FunctionDef) and n.name=='plan']
        ns=dict(NATIVE_STEPS=launcher.NATIVE_STEPS,INSPECTION_PHASES=launcher.INSPECTION_PHASES)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<previous-plan>','exec'),ns)
        prior=ns['plan']('full',None); current=launcher.plan('full',None)
        self.assertEqual(175,len(prior)); self.assertEqual(prior,current[:175])
        self.assertEqual(list(d.HOST_GATES)+[d.NATIVE_GATE,d.DECISION_GATE],current[175:])
        self.assertEqual(190,len(current)); self.assertEqual(190,len(set(current)))
        self.assertEqual(ns['plan']('desktop',None)+list(d.HOST_GATES),launcher.plan('desktop',None))

    def test_every_focused_host_gate_has_existing_entrypoint(self):
        for gate in d.HOST_GATES:
            name=gate.split(':')[1]
            self.assertIn(gate,launcher.plan('desktop',name))
            args=d.host_command(gate,Path('out'),Path('database'),sys.executable,Path('source'))
            self.assertEqual(['-I','-B'],args[1:3])
            if name!='drone_harness': self.assertTrue(Path(args[3]).is_file())
            with self.assertRaises(AssertionError): launcher.plan('full',name)
        with self.assertRaises(AssertionError): launcher.plan('desktop','drone_missing')

    def test_approved_decision_requires_the_exact_selected_policy(self):
        self.assertEqual('F08.03-conserve-v1',d.require_decision()['id'])

    def test_reporter_rejects_missing_gates_and_missing_conservation_evidence(self):
        import report_local
        with self.assertRaisesRegex(AssertionError,'Missing C04'):
            report_local.validate_c04_delivery(Path('absent'),{'plan':[]},{})
        with self.assertRaisesRegex(AssertionError,'Missing completed conservation gate'):
            report_local.validate_c04_delivery(Path('absent'),{'plan':launcher.plan('full',None)},{})

    def test_native_methods_fixtures_and_initial_exclusion_are_complete(self):
        from native_suite import EXCLUDED
        self.assertEqual(11,sum(len(methods) for _,methods in d.PHASES.values()))
        self.assertEqual(5,len(d.SCREENSHOTS))
        for cls,methods in d.PHASES.values():
            self.assertIn(cls,EXCLUDED)
            text=(d.ROOT/'android/app/src/androidTest/java/io/github/sussic/pyfa'/f'{cls}.kt').read_text(encoding='utf-8')
            for method in methods:self.assertIn('fun '+method+'(',text)
        prepare=(d.ROOT/'android/prepare-engine.py').read_text(encoding='utf-8')
        loop=next(n for n in ast.walk(ast.parse(prepare)) if isinstance(n,ast.For) and
                  isinstance(n.iter,ast.Tuple) and any(isinstance(v,ast.Constant) and v.value=='drone-details' for v in n.iter.elts))
        self.assertEqual({Path(n).stem for n in d.REFERENCE_FILES.values()},set(ast.literal_eval(loop.iter)))
        self.assertIn('fixtures/{family}.json',ast.unparse(loop))
        self.assertIn('{family}-expected.json',ast.unparse(loop))

    def observations(self):
        original=json.loads((d.FIXTURES/'drone-core-edits.json').read_text(encoding='utf-8'))
        acceptance=json.loads((d.FIXTURES/'drone-acceptance.json').read_text(encoding='utf-8'))
        core=[]
        for c in original['cases']+acceptance['core_extra']:
            row=dict(name=c['spec']['name'],operation=c['operation'],accepted=c.get('accepted',True),
                     before=c['before'],after=c['after'],restored=c['restored'])
            if row['accepted']: row['redone']=c['after']
            core.append(deepcopy(row))
        linked=dict(linked=[dict(name=c['spec']['name'],operation=c['operation'],link=c['link'],
            after=c['after'],restored=c['restored'],redone=c['after']) for c in acceptance['linked']],
            variations=[dict(name=c['spec']['name'],step=i,after=s['after']) for c in acceptance['variations'] for i,s in enumerate(c['steps'])])
        return core,deepcopy(linked),original,acceptance

    def test_complete_synthetic_reports_validate(self):d.validate_observations(*self.observations())

    def test_missing_extra_duplicate_changed_and_reordered_reports_reject(self):
        def remove_case(c,l):c.pop()
        def duplicate(c,l):c[1]=deepcopy(c[0])
        def missing(c,l):c[0].pop('after')
        def extra(c,l):c[0]['unexpected']=True
        def changed(c,l):c[0]['after']['active']+=1
        def bool_number(c,l):c[0]['after']['active']=True
        def nonfinite(c,l):c[0]['after']['active']=float('nan')
        def link(c,l):l['linked'][0]['link']='wrong'
        def missing_recipient(c,l):l['linked'][0]['after'].pop()
        def missing_step(c,l):l['variations'].pop()
        def reorder(c,l):l['variations'].reverse()
        for change in (remove_case,duplicate,missing,extra,changed,bool_number,nonfinite,link,missing_recipient,missing_step,reorder):
            c,l,o,a=self.observations(); change(c,l)
            with self.subTest(change=change.__name__),self.assertRaises(AssertionError):d.validate_observations(c,l,o,a)

    def test_wire_shape_units_bool_and_nonfinite_fail_closed(self):
        expected={'value':1.0,'unit':'m','rows':[1,2]}
        d.compare_wire(expected,{'value':1,'unit':'m','rows':[1.0,2.0]})
        for actual in ({'value':True,'unit':'m','rows':[1,2]}, {'value':1,'unit':'km','rows':[1,2]},
                       {'value':float('inf'),'unit':'m','rows':[1,2]}, {'value':1,'rows':[1,2]},
                       {'value':1,'unit':'m','rows':[2,1]}):
            with self.subTest(actual=actual),self.assertRaises(AssertionError):d.compare_wire(expected,actual)

    def test_retry_uses_new_owned_avd_without_overwriting_previous_data(self):
        folder=Path('evidence/run.123')
        first=d.avd_identity(folder,0); retry=d.avd_identity(folder,1)
        self.assertEqual((folder/'avd-c04-r0','pyfa-local-run-123-r0-c04'),first)
        self.assertNotEqual(first[0],retry[0]);self.assertNotEqual(first[1],retry[1])
        self.assertEqual(folder,retry[0].parent)
        for bad in (-1,True,1.5):
            with self.assertRaises(AssertionError):d.avd_identity(folder,bad)


    def test_conservation_reports_and_corruptions(self):
        expected=json.loads((d.FIXTURES/'drone-conservation.json').read_text(encoding='utf-8'))
        rows=[]
        for c in expected['cases']:
            row=dict(name=c['spec']['name'],operation=c['operation'],accepted=c['accepted'],
                     before=c['before'],after=c['after'],restored=c['before'])
            if c['accepted']:row['redone']=c['after']
            rows.append(deepcopy(row))
            self.assertEqual(sum(r['active'] for r in c['spec']['drones']),sum(r['active'] for r in c['after_rows']))
            self.assertEqual(sum(r['amount'] for r in c['spec']['drones']),sum(r['amount'] for r in c['after_rows']))
        d.validate_conservation_rows(rows,expected)
        def missing(x):x.pop()
        def duplicate(x):x[1]=deepcopy(x[0])
        def active(x):x[1]['after']['core']['active']+=1
        def boolean(x):x[1]['after']['core']['active']=True
        def metric(x):x[5]['after']['metrics'][0]['hp_shield']+=1
        def restore(x):x[1]['restored']=deepcopy(x[1]['after'])
        def approval(x):x[-1]['accepted']=True
        for corrupt in (missing,duplicate,active,boolean,metric,restore,approval):
            value=deepcopy(rows);corrupt(value)
            with self.subTest(corrupt=corrupt.__name__),self.assertRaises(AssertionError):d.validate_conservation_rows(value,expected)

    def test_only_owned_emulator_data_is_excluded_from_artifact_manifest(self):
        root=Path('run')
        for relative,wanted in (('avd/guest/data.img',True),('avd-c04-r0/guest/data.img',True),
          ('avd-c04-r12/guest/data.img',True),('native/c04/result.json',False),
          ('c04-seed-r0/graph.sqlite3',False),('avd-c04-r0-evidence/proof.json',False)):
            self.assertEqual(wanted,d.is_emulator_data(root,root/relative))


if __name__=='__main__': unittest.main(verbosity=2)
