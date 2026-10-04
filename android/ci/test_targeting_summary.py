"""C03.1 every scalar/member, fixture provenance and full-summary regressions."""
from copy import deepcopy
import hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from targeting_summary import targeting,summarize,REJECTIONS,metadata_groups
from resource_summary import fixture_bytes
FIXTURE=Path(__file__).resolve().parents[2]/'tools/android_reference/fixtures/targeting.json'


class TargetingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=json.loads(FIXTURE.read_text(encoding='utf-8'));self.expected=self.fixture['cases'][0]['expected']['targeting'];self.actual=deepcopy(self.expected)
    def reject(self,change):
        change(self.actual)
        with self.assertRaises((AssertionError,KeyError)):targeting(self.expected,self.actual)
    def test_complete_matrix_and_families(self):
        self.assertEqual(53,len(self.fixture['cases']));self.assertEqual(437,len(self.fixture['hull_inventory']))
        available={key for key in self.fixture['hold_attributes'] if any((hull['holds'][key] or 0)>0 for hull in self.fixture['hull_inventory'])}
        self.assertEqual(set(self.fixture['available_holds']),available);self.assertEqual(14,len(available))
        self.assertEqual(set(self.fixture['hold_attributes'])-available,set(self.fixture['absent_holds']))
        self.assertEqual(21,len(self.fixture['hold_attributes']));self.assertEqual(8,len(self.fixture['reference_targets']))
        covered=set()
        for case in self.fixture['cases']:
            row=case['expected']['targeting'];targeting(row,deepcopy(row));self.assertEqual(self.fixture['hold_attributes'],[h['attribute'] for h in row['holds']])
            self.assertEqual(self.fixture['reference_targets'],[[h['name'],h['radius']] for h in row['lock_times']])
            covered|={h['attribute'] for h in row['holds'] if (h['capacity']['value'] or 0)>0}
        self.assertEqual(available,covered)
    def test_wrong_value(self):self.reject(lambda r:r['main']['range'].update(value=99999999))
    def test_boolean(self):self.reject(lambda r:r['main']['range'].update(value=True))
    def test_wrong_kind(self):self.reject(lambda r:r['main']['targets'].update(value_type='decimal'))
    def test_wrong_unit(self):self.reject(lambda r:r['main']['range'].update(unit='km'))
    def test_wrong_display(self):self.reject(lambda r:r['main']['range'].update(display='wrong'))
    def test_wrong_detail(self):self.reject(lambda r:r['main']['align'].update(detail='wrong'))
    def test_missing_hold(self):self.reject(lambda r:r['holds'].pop())
    def test_absent_as_present(self):
        absent=next(i for i,h in enumerate(self.actual['holds']) if not h['present'])
        self.reject(lambda r:r['holds'][absent].update(present=True))
    def test_hold_order(self):self.reject(lambda r:r['holds'].reverse())
    def test_lock_size(self):self.reject(lambda r:r['lock_times'][0].update(radius=26))
    def test_missing_lock(self):self.reject(lambda r:r['lock_times'].pop())
    def test_sensor_type(self):self.reject(lambda r:r.update(sensor_type='wrong'))
    def test_warp_signed_and_explicit_unavailable(self):
        disrupted=next(c for c in self.fixture['cases'] if c['spec']['name']=='Projected Warp disruption')['expected']['targeting']
        self.assertLess(disrupted['warp_core']['value'],0);targeting(disrupted,deepcopy(disrupted))
        absent=dict(value=None,value_type='unavailable',unit='x',display=None,detail=None)
        targeting(absent,deepcopy(absent))
        with self.assertRaises(AssertionError):targeting(absent,dict(value=0,value_type='integer',unit='x',display='0',detail='0'))
    def test_exact_fixture_bytes(self):
        reference=FIXTURE.read_bytes().replace(b'\r\n',b'\n')
        with tempfile.TemporaryDirectory() as directory:
            apk=Path(directory)/'test.apk'
            for data,accepted in ((reference,True),(reference.replace(b'\n',b'\r\n'),True),(reference.replace(b'Targeting Vexor',b'Changed Vexor',1),False),(reference.replace(b'  ',b'   ',1),False)):
                with ZipFile(apk,'w') as archive:archive.writestr('assets/targeting-expected.json',data)
                if accepted:fixture_bytes(apk,reference,hashlib.sha256(data).hexdigest(),'targeting-expected.json')
                else:
                    with self.assertRaises(AssertionError):fixture_bytes(apk,reference,hashlib.sha256(data).hexdigest(),'targeting-expected.json')
                with self.assertRaises(AssertionError):fixture_bytes(apk,reference,'0'*64,'targeting-expected.json')
            with ZipFile(apk,'w') as archive:archive.writestr('assets/other.json',reference)
            with self.assertRaises(KeyError):fixture_bytes(apk,reference,hashlib.sha256(reference).hexdigest(),'targeting-expected.json')


class SummaryTests(unittest.TestCase):
    @staticmethod
    def typed(data):
        metadata={}
        def walk(value,path):
            if type(value) is dict:
                for key,entry in value.items():walk(entry,path+'.'+key)
            elif type(value) is list:
                for i,entry in enumerate(value):walk(entry,f'{path}[{i}]')
            elif type(value) in (int,float):metadata[path]='integer' if type(value) is int else 'decimal'
        walk(data,'root');return dict(data=data,numeric_types=metadata)
    def inputs(self):
        fixture=json.loads(FIXTURE.read_text(encoding='utf-8'))
        witness=json.loads(FIXTURE.with_name('targeting-skill-inputs.json').read_text(encoding='utf-8'))
        engine=dict(desktop_source_commit=fixture['source_commit'],database_logical_sha256=witness['database_logical_sha256'],engine_source_sha256='engine',source_data_sha256='data',eos_settings=fixture['eos_settings'])
        graph=dict(sample_id='prior-0',fit_order=[],records={},revisions={},modified={},recent=[],dataset_identity=engine['database_logical_sha256'],eos_settings=fixture['eos_settings']);snapshots=[]
        def add(key,spec,revision=1,skills=None,projections=None):
            spec=deepcopy(spec);spec['name']='C03 '+spec['name'];skills=skills or {};projections=projections or []
            graph['fit_order'].append(key);graph['records'][key]=dict(spec=spec,skills=skills,implants=[],projections=projections,commands=[]);graph['revisions'][key]=revision;graph['modified'][key]=0
            snapshots.append(dict(id=key,name=spec['name'],ship=spec['ship'],revision=revision,skills=skills,implants=[],projections=projections,commands=[],modules=[dict(index=i,**m) for i,m in enumerate(spec['modules'])]))
        for i in range(268):add('prior-'+str(i),fixture['cases'][0]['spec'])
        before=deepcopy(graph);inherited=deepcopy(snapshots);ids=[];values=[];edits=[]
        ui_index=next(i for i,c in enumerate(fixture['cases']) if c['spec']['name']=='Drone range' and c['edits'])
        for i,case in enumerate(fixture['cases']):
            key='target-'+str(i);ids.append(key);spec=deepcopy(case['spec']);skills=deepcopy(witness['cases'][i]['skills']);projections=[];mutated=bool(case['edits'] or 'source_spec' in case)
            for step in case['edits']:
                args=step['args']
                if step['operation']=='set_module_states':
                    for pos in args['module_indices']:spec['modules'][pos]['state']=args['state']
                elif step['operation']=='set_skill_level':skills[args['skill']]=args['level']
                elif step['operation']=='add_cargo':spec['cargo']=[dict(name='Antimatter Charge M',amount=args['quantity'])];graph['recent']=[args['item_id']]
            if 'source_spec' in case:projections=[dict(source_id='source-'+str(i),range_m=None,active=True,amount=1)]
            revision=6 if i==ui_index else 4 if mutated else 1
            add(key,spec,revision,skills,projections)
            if 'source_spec' in case:add('source-'+str(i),case['source_spec'],2)
            values.append(dict(fit_id=key,revision=revision,**deepcopy(case['expected'])))
            if mutated:edits.append(dict(case=i,applied=dict(fit_id=key,revision=2,**deepcopy(case['expected'])),undone=dict(fit_id=key,revision=3,**deepcopy(case['initial'])),redone=dict(fit_id=key,revision=4,**deepcopy(case['expected']))))
        owner=next(i for i,c in enumerate(fixture['cases']) if c['spec']['name']=='Targeting Vexor')
        add('copy',fixture['cases'][owner]['spec'],3);graph['records']['copy']['spec']['name']='C03 copy';snapshots[-1]['name']='C03 copy'
        copied=dict(fit_id='copy',revision=3,**deepcopy(fixture['cases'][owner]['expected']))
        ui=dict(case=ui_index,before=dict(fit_id=ids[ui_index],revision=4,**deepcopy(fixture['cases'][ui_index]['expected'])),undone=dict(fit_id=ids[ui_index],revision=5,**deepcopy(fixture['cases'][ui_index]['initial'])),redone=deepcopy(values[ui_index]))
        saved=dict(pid=102,ids=ids,inherited=self.typed(inherited),inherited_graph=self.typed(before),graph=self.typed(graph),all_fits=self.typed(snapshots),edits=edits,ui_history=ui,copy_id='copy',copy_targeting=copied,outputs=values)
        start=dict(manifest={k:v for k,v in engine.items() if k!='eos_settings'},eos_settings=fixture['eos_settings'],persistence=dict(enabled=True,opened_existing=True))
        common=dict(task='C03.1',runtime_start=start,ids=ids,saved=saved,copy_observation=copied,fixture_sha256=hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),observations=[dict(case=i,actual=deepcopy(v)) for i,v in enumerate(values)])
        stages=[];previous=dict(graph=self.typed(before),all_fits=self.typed(inherited))
        for group,count in enumerate((33,45,53)):
            row=deepcopy(common);row.update(phase='prepare'+str(group),pid=100+group,protocol_rejections=REJECTIONS if group==2 else [],stage_start=deepcopy(previous))
            stage=row['saved'];stage['pid']=100+group
            if group<2:
                stage['ids']=stage['ids'][:count];stage['outputs']=stage['outputs'][:count];stage['edits']=[e for e in stage['edits'] if e['case']<count]
                stage['copy_id']=stage['copy_targeting']=row['copy_observation']=None
                partial=deepcopy(graph);partial['fit_order']=partial['fit_order'][:268+count];partial['recent']=deepcopy(before['recent'])
                for field in ('records','revisions','modified'):partial[field]={key:partial[field][key] for key in partial['fit_order']}
                stage['graph']=self.typed(partial);stage['all_fits']=self.typed([s for s in snapshots if s['id'] in partial['fit_order']])
            row['ids']=deepcopy(stage['ids']);row['observations']=row['observations'][:count]
            stages.append(row);previous={field:deepcopy(stage[field]) for field in ('graph','all_fits')}
        restored=dict(**deepcopy(common),phase='restored',pid=103,protocol_rejections=[],stage_start=deepcopy(previous))
        return [*stages,restored],engine
    def test_complete_summary_and_corruptions(self):
        reports,engine=self.inputs()
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory);(run/'native').mkdir();(run/'apks').mkdir()
            with ZipFile(run/'apks/app-debug-androidTest.apk','w') as archive:archive.writestr('assets/targeting-expected.json',FIXTURE.read_bytes())
            with patch('targeting_summary.evidence_dir',return_value=run/'native'):
                self.assertTrue(summarize(reports,engine,{99})['complete'])
                changes={
                  'hash':lambda r:r[0].update(fixture_sha256='0'*64),'pid':lambda r:r[1].update(pid=100),
                  'manifest':lambda r:r[0]['runtime_start']['manifest'].update(engine_source_sha256='wrong'),
                  'settings':lambda r:r[0]['runtime_start']['eos_settings'].update(globalDefaultSpoolupPercentage=.5),
                  'restart':lambda r:r[1]['runtime_start']['persistence'].update(opened_existing=False),
                  'missing_case':lambda r:r[0]['observations'].pop(),'order':lambda r:r[0]['observations'][0].update(case=1),
                  'revision':lambda r:r[0]['observations'][0]['actual'].update(revision=2),'restored_revision':lambda r:r[3]['observations'][0]['actual'].update(revision=2),
                  'recent':lambda r:r[2]['saved']['graph']['data'].update(recent=[]),
                  'inherited':lambda r:r[0]['saved']['all_fits']['data'][0].update(name='changed'),
                  'inherited_kind':lambda r:r[0]['saved']['graph']['numeric_types'].update({'root.revisions.prior-0':'decimal'}),
                  'graph_order':lambda r:r[0]['saved']['graph']['data']['fit_order'].reverse(),
                  'copy':lambda r:r[2]['copy_observation'].update(fit_id='wrong'),
                  'guards':lambda r:r[2].update(protocol_rejections=[]),
                  'edit_revision':lambda r:r[0]['saved']['edits'][0]['undone'].update(revision=2),
                  'ui_revision':lambda r:r[0]['saved']['ui_history']['undone'].update(revision=4),
                  'missing_metadata':lambda r:r[0]['saved']['graph']['numeric_types'].pop('root.revisions.target-0'),
                  'skills':lambda r:r[1]['saved']['graph']['data']['records']['target-41']['skills'].clear(),
                  'missing_dependent':lambda r:r[1]['saved']['graph']['data']['records']['target-43']['skills'].pop('Electronic Attack Ships'),
                  'dependent_none_as_zero':lambda r:r[1]['saved']['graph']['data']['records']['target-43']['skills'].update({'Electronic Attack Ships':0}),
                  'additional_dependent':lambda r:r[1]['saved']['graph']['data']['records']['target-43']['skills'].update({'Synthetic extra skill':None}),
                  'stage_pid':lambda r:r[2].update(pid=r[1]['pid']),
                  'stage_input':lambda r:r[1]['stage_start']['all_fits']['data'][0].update(name='changed'),
                  'stage_outputs':lambda r:r[1]['saved']['outputs'].pop(),
                  'stage_graph':lambda r:r[1]['saved']['graph']['data']['records']['target-0']['spec'].update(name='changed'),
                  'stage_inherited':lambda r:r[1]['saved']['inherited']['data'][0].update(name='changed'),
                  'hold':lambda r:r[0]['observations'][0]['actual']['targeting']['holds'].pop(),
                  'lock':lambda r:r[0]['observations'][0]['actual']['targeting']['lock_times'][0].update(radius=26),
                }
                for name,change in changes.items():
                    with self.subTest(name=name):
                        bad=deepcopy(reports);change(bad)
                        with self.assertRaises((AssertionError,KeyError)):summarize(bad,engine,{99})


class MetadataIndexTests(unittest.TestCase):
    def test_exact_prefix_memberships(self):
        ids=('a','ab','a.b','a[0]','a.b[0]','a.','a[','')
        prefixes=[f'root.{field}.{key}' for field in ('records','revisions','modified') for key in ids]
        names={prefix+suffix for prefix in prefixes for suffix in ('','.value','[0]','.nested[1].x','z','[broken')}
        names|={'root.other.a.value','root.records.other.value','unrelated'}
        for changed in (False,True):
            wrapper=dict(numeric_types={name:('decimal' if changed and index%2 else 'integer') for index,name in enumerate(sorted(names))})
            expected={prefix:{k:v for k,v in wrapper['numeric_types'].items() if k==prefix or k.startswith(prefix+'.') or k.startswith(prefix+'[')} for prefix in prefixes}
            self.assertEqual(expected,metadata_groups(wrapper,prefixes))
        self.assertEqual({},metadata_groups(dict(numeric_types={'root.records.a.x':'integer'}),[]))


if __name__=='__main__':unittest.main()
