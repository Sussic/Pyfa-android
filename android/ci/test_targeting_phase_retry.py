"""Reject altered retained fits and unrelated synthetic-store recovery inputs."""
import copy
import json
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import targeting_phase_retry as retry
from targeting_phase_retry import recovery_graph

ROOT = Path(__file__).resolve().parents[2]


def typed(value):
    kinds = {}
    def visit(row, path):
        if type(row) is dict: return {key: visit(item, path+'.'+key) for key,item in row.items()}
        if type(row) is list: return [visit(item, f'{path}[{i}]') for i,item in enumerate(row)]
        if type(row) in (int,float):
            kinds[path] = 'decimal' if type(row) is float else 'integer'
            return int(row) if type(row) is float and row.is_integer() else row
        return row
    return dict(data=visit(value,'root'),numeric_types=kinds)


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        directory=ROOT/'tools/android_reference/fixtures'
        self.fixture=json.loads((directory/'targeting.json').read_text(encoding='utf-8'))
        self.skills=json.loads((directory/'targeting-skill-inputs.json').read_text(encoding='utf-8'))
        ids=[f'prior-{i}' for i in range(313)]
        record=dict(spec=dict(ship='Vexor',name='retained',modules=[],drones=[],boosters=[],skill_level=5),
                    skills={},implants=[],projections=[],commands=[])
        baseline=dict(format=1,dataset_identity='synthetic-dataset',eos_settings=dict(spool=100.0),
                      sample_id=ids[0],fit_order=ids,records={key:copy.deepcopy(record) for key in ids},
                      revisions={key:1 for key in ids},modified={key:10 for key in ids},recent=[1,2])
        self.prior=dict(task='C03.1',phase='prepare1',observations=[{} for _ in range(45)],
            saved=dict(graph=typed(baseline),all_fits=dict(data=[dict(id=key) for key in ids]),
                       ids=ids[:45],outputs=[{} for _ in range(45)]))
        self.graph=copy.deepcopy(baseline)
        for index,case in enumerate(self.fixture['cases'][45:],45):
            key=f'new-{index}';spec=copy.deepcopy(case['spec']);spec['name']='C03 '+spec['name']
            for edit in case['edits']:
                if edit['operation']=='add_cargo':spec['cargo']=[dict(name='Antimatter Charge M',amount=edit['args']['quantity'])]
            self.add(key,dict(spec=spec,skills=copy.deepcopy(self.skills['cases'][index]['skills']),
                              implants=[],projections=[],commands=[]),4)
            if 'source_spec' in case:
                source=key+'-source';source_spec=copy.deepcopy(case['source_spec']);source_spec['name']='C03 '+source_spec['name']
                self.add(source,dict(spec=source_spec,skills={},implants=[],projections=[],commands=[]),2)
                self.graph['records'][key]['projections']=[dict(source_id=source,range_m=None,active=True,amount=1)]
        item=self.fixture['cases'][49]['edits'][0]['args']['item_id']
        self.graph['recent']=([item]+[i for i in baseline['recent'] if i!=item])[:20]
    def add(self,key,record,revision):
        self.graph['fit_order'].append(key);self.graph['records'][key]=record
        self.graph['revisions'][key]=revision;self.graph['modified'][key]=11
    def check(self):return recovery_graph(self.graph,self.prior,self.fixture,self.skills)
    def test_valid_recovery_preserves_types_and_does_not_mutate_inputs(self):
        before=copy.deepcopy(self.graph);restored,removed=self.check()
        self.assertEqual(before,self.graph);self.assertEqual(313,len(restored['fit_order']))
        self.assertEqual(11,len(removed));self.assertEqual([1,2],restored['recent'])
        self.assertIs(type(restored['eos_settings']['spool']),float)
    def test_rejects_changed_retained_inputs_and_metadata(self):
        changes={
          'record':lambda g:g['records']['prior-0']['spec'].update(name='changed'),
          'revision':lambda g:g['revisions'].update({'prior-0':2}),
          'modified':lambda g:g['modified'].update({'prior-0':20}),
          'kind':lambda g:g['eos_settings'].update(spool=100),
          'dataset':lambda g:g.update(dataset_identity='wrong'),
          'sample':lambda g:g.update(sample_id='new-45'),
          'order':lambda g:g['fit_order'].reverse(),
        }
        for name,change in changes.items():
            with self.subTest(name=name):
                original=copy.deepcopy(self.graph);change(self.graph)
                with self.assertRaises(AssertionError):self.check()
                self.graph=original
    def test_rejects_unrelated_additions_or_wrong_fixture_inputs(self):
        changes={
          'name':lambda g:g['records']['new-45']['spec'].update(name='personal fit'),
          'skill':lambda g:g['records']['new-45']['skills'].update(Navigation=5),
          'source':lambda g:g['records']['new-50']['projections'][0].update(source_id='prior-0'),
          'source_kind':lambda g:g['records']['new-50']['projections'][0].update(amount=True),
          'quantity':lambda g:g['records']['new-49']['spec']['cargo'][0].update(amount=999),
          'recent':lambda g:g.update(recent=[]),
        }
        for name,change in changes.items():
            with self.subTest(name=name):
                original=copy.deepcopy(self.graph);change(self.graph)
                with self.assertRaises(AssertionError):self.check()
                self.graph=original


class SourceTest(unittest.TestCase):
    def setUp(self):
        from local_verification import plan
        self.completed=plan('full',None)[:147]
        paths=(*retry.PHASE_SOURCES,'android/ci/local_verification.py')
        self.sources={(revision,path):subprocess.check_output(['git','show',revision+':'+path],
            cwd=ROOT,text=True,encoding='utf-8') for revision in (retry.BEFORE,retry.BUILD) for path in paths}
        self.sources.update({('after',path):self.sources[(retry.BUILD,path)] for path in paths})
        self.changed=list(retry.PHASE_SOURCES)+['android/ci/targeting_phase_retry.py','docs/android/STATUS.md']
    def check(self):
        def git(args,**kwargs):
            if args[1]=='diff':return '\n'.join(self.changed)
            if args[1]=='show':return self.sources[tuple(args[2].split(':',1))]
            raise AssertionError(args)
        with patch.object(retry.subprocess,'check_output',side_effect=git):
            return retry.exact_source(ROOT,retry.BEFORE,'after',self.completed)
    def test_reviewed_source_and_full_retained_prefix_pass(self):self.check()
    def test_product_fixture_or_unrelated_native_change_rejected(self):
        for path in ('android_bridge/contract.py','tools/android_reference/fixtures/targeting.json',
                     'android/app/src/androidTest/java/io/github/sussic/pyfa/InspectionTest.kt'):
            with self.subTest(path=path):
                self.changed.append(path)
                with self.assertRaises(AssertionError):self.check()
                self.changed.pop()
    def test_assertion_or_timeout_change_rejected(self):
        for path in retry.PHASE_SOURCES:
            with self.subTest(path=path):
                original=self.sources[('after',path)]
                self.sources[('after',path)]=original+'\n# unreviewed assertion or timeout change\n'
                with self.assertRaises(AssertionError):self.check()
                self.sources[('after',path)]=original
    def test_omitted_retained_gate_rejected(self):
        self.completed.pop()
        with self.assertRaises(AssertionError):self.check()
    def test_host_or_build_command_change_rejected(self):
        path='android/ci/local_verification.py'
        source=self.sources[('after',path)]
        self.sources[('after',path)]=source.replace('def build(self,name):','def build(self,name):\n        raise RuntimeError("changed build")',1)
        self.assertNotEqual(source,self.sources[('after',path)])
        with self.assertRaises(AssertionError):self.check()


class ArtifactTest(unittest.TestCase):
    def setUp(self):
        from local_verification import plan
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.run=Path(self.temp.name)/'run';self.archive=self.run/'archive';self.source=Path(self.temp.name)/'build'
        for directory in (self.run/'native',self.run/'logs',self.run/'apks',self.archive/'native',
                          self.archive/'apks',self.source/'native',self.source/'apks'):directory.mkdir(parents=True,exist_ok=True)
        completed=plan('full',None)[:147];rows=[]
        for index,gate in enumerate(completed):
            path=self.run/'logs'/f'{index}.log';path.write_text('actual passing log '+gate)
            rows.append(dict(gate=gate,exit_code=0,tested_commit=retry.BEFORE,log=str(path.relative_to(self.run)),log_sha256=retry.sha(path)))
        old=dict(commit=retry.BEFORE,status='failed',completed=completed,attempts=rows)
        (self.archive/'run.json').write_text(json.dumps(old))
        latest=copy.deepcopy(rows);build_rows={}
        for row in latest:
            if row['gate'].startswith('build:'):
                row.update(tested_commit='compiled',reused_from_run='build');build_rows[row['gate']]=copy.deepcopy(row)
        (self.run/'run.json').write_text(json.dumps(dict(attempts=latest)))
        for name in ('app-debug.apk','app-debug-androidTest.apk'):
            for folder in (self.run/'apks',self.archive/'apks',self.source/'apks'):(folder/name).write_text(name)
        (self.archive/'native/apk-contents.json').write_text('old package proof')
        for folder in (self.run/'native',self.source/'native'):(folder/'apk-contents.json').write_text('new package proof')
        report=self.run/'native/retained.json';report.write_text('passing native report')
        hashes={'native/retained.json':retry.sha(report)}
        (self.archive/'native-manifest.json').write_text(json.dumps(hashes))
        (self.source/'files.json').write_text(json.dumps({'native/apk-contents.json':dict(sha256=retry.sha(self.source/'native/apk-contents.json'))}))
        self.proof=dict(from_commit=retry.BEFORE,to_commit='after',archive='archive',completed_before_adoption=completed,
            retained_gates=[g for g in completed if not g.startswith('build:')],original_run_sha256=retry.sha(self.archive/'run.json'),
            native_manifest_sha256=retry.sha(self.archive/'native-manifest.json'),native_hashes=hashes,
            old_apk_hashes={p.name:retry.sha(p) for p in (self.archive/'apks').iterdir()},
            old_package_sha256=retry.sha(self.archive/'native/apk-contents.json'),build_commit='compiled',
            build_reuse=dict(apk_hashes={p.name:retry.sha(p) for p in (self.run/'apks').iterdir()}))
        self.build_state=dict(completed=plan('build',None));self.build_rows=build_rows
    def check(self):
        with patch.object(retry,'exact_source'),patch.object(retry,'validate_recovery',return_value=dict(retained_fits=313)), \
             patch('charge_keyboard_retry.validated_build',return_value=(self.source,self.build_state,self.build_rows)), \
             patch('cargo_history_retry.assets_equal'),patch.object(retry.subprocess,'check_output',return_value='compiled\n'):
            return retry.validate_retained(ROOT,self.run,self.proof)
    def test_all_retained_artifacts_and_original_gate_stamps_pass(self):self.check()
    def test_changed_log_report_apk_or_package_rejected(self):
        for path in (self.run/'logs/0.log',self.run/'native/retained.json',self.run/'apks/app-debug-androidTest.apk',
                     self.archive/'native/apk-contents.json',self.run/'native/apk-contents.json'):
            with self.subTest(path=path):
                original=path.read_bytes();path.write_text('changed proof')
                with self.assertRaises(AssertionError):self.check()
                path.write_bytes(original)
    def test_relabelled_retained_gate_rejected(self):
        state=json.loads((self.run/'run.json').read_text(encoding='utf-8'));state['attempts'][0]['tested_commit']='after'
        (self.run/'run.json').write_text(json.dumps(state))
        with self.assertRaises(AssertionError):self.check()


if __name__=='__main__':unittest.main()