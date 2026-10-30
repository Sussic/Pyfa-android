"""Explicit, resumable, policy-bound local verification with durable MSI offload."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import nullcontext

sys.path.insert(0, str(Path(__file__).resolve().parent))
from artifact_retention import ArtifactBudget, cleanup_verified_runtime, register_runtime
from execution_policy import (AdmissionDeferred, PressureWindow, admit, detect_host,
                              heavy_lease, load_policy, select)
from policy_host_metrics import host_memory
from native_suite import STEPS as NATIVE_STEPS
from inspection_delivery import PHASES as INSPECTION_PHASES
from drone_delivery import HOST_GATES as DRONE_HOST_GATES, NATIVE_GATE as DRONE_NATIVE_GATE, DECISION_GATE as DRONE_DECISION_GATE

ROOT=Path(__file__).resolve().parents[2]
PIN='8b04f3b271e614b3e103853b44a7851a63d79d0e'
FAMILIES=['projection','command','catalog','equipment','empty_hulls','module_edits',
    'charge_edits','variation_edits','rack_ordering','bulk_charges','bulk_states',
    'clone_fill','bulk_variation_removal','hull_modes','subsystems','structures',
    'cargo_stacks','cargo_actions','cargo_transfers','notes','history','history_mutations','resources','capacitor','defenses','tank','output','targeting']
HEADLESS=['bridge','persistence','library','market','empty_hulls','module_edits',
    'charge_edits','variation_edits','rack_ordering','bulk_charges','bulk_states',
    'clone_fill','bulk_variation_removal','hull_modes','subsystems','structures',
    'cargo_stacks','cargo_actions','cargo_transfers','notes','history','history_mutations','resources','capacitor','defenses','tank','output','targeting']
BUILD=['dependencies','engine-assets','apks-lint','signature','package']
INSPECTOR=['inventory','attributes','metadata','units','affectors','properties',
    'projection','command','equipment_paths','equipment_probes','guard_domains','effect_catalog','identities','sorting','text','contexts','affector_metadata','context_metadata']


def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()

def pending_tank_fixture_fix(root, before, after, completed):
    """Only the reviewed, not-yet-executed single falloff witness may change."""
    assert before == '7a0aaa27b1739d9600e14915d62cb2d35a873db0'
    assert completed == ['desktop:utilities','desktop:reference','desktop:migration',
        'reference:projection','reference:command','reference:catalog','reference:equipment',
        'reference:empty_hulls','reference:module_edits']
    pairs = {
        'tools/android_reference/tank.py': (
            '62cd2fd83c0b74eff761d8b5c57537689e470c615015cd7d822712e3918c8cf2',
            '5d85254c2ecd7e97b548f0d99803e94d0ac45266acf4030d9d3032939142cfdb'),
        'tools/android_reference/fixtures/tank.json': (
            'bb740504554a00c6cfe020d18124409bee2d50308f446aceba31a4e5159fc28d',
            'c0154338bf8f8c6134fd9a188e4a10ee03082cabaf64c0088bb2e433e24a4aca'),
    }
    for path, hashes in pairs.items():
        for commit, expected in zip((before, after), hashes):
            content = subprocess.check_output(['git','show',commit+':'+path],cwd=root)
            assert hashlib.sha256(content.replace(b'\r\n',b'\n')).hexdigest() == expected, path
    changed = subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed = set(pairs) | {'android/ci/local_verification.py','android/ci/report_local.py',
                           'android/ci/test_pending_tank_fixture_fix.py'}
    assert set(pairs) <= set(changed)
    assert all(path in allowed or path.startswith('docs/android/') for path in changed), changed


def pending_mutation_count_fix(root, before, after, completed):
    """Reuse earlier gates only for the exact unexecuted suite-count correction."""
    assert 'headless:history_mutations' not in completed
    path = 'tools/android_headless/check_history_mutations.py'
    def source(commit):
        return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=root, text=True, encoding='utf-8')
    old = source(before); new = source(after)
    assert old.count('(2 if args.matrix_only else 22)') == 1
    assert new == old.replace('(2 if args.matrix_only else 22)', '(2 if args.matrix_only else 23)', 1)

OUTPUT_HISTORY_BEFORE='4b42c02f8af88057f557c3c542dec0dbedb28b28'


def pending_output_history_fix(root, before, after, completed):
    """Reuse only the 54 gates before the failed C02 registration witness."""
    assert before==OUTPUT_HISTORY_BEFORE
    assert completed==plan('full',None)[:54]
    assert plan('full',None)[54]=='headless:history_mutations'
    path='tools/android_headless/check_history_mutations.py'
    for revision,digest in ((before,'0ade08192b8fee95f92168eca3c0a327b1aad8175621537df40c996c5ad23431'),
                            (after,'3ff31dc4ed5b6f0eee41437af0cfb6b00d1e81509bb75a3254f84e0d7316555d')):
        source=subprocess.check_output(['git','show',revision+':'+path],cwd=root)
        assert hashlib.sha256(source.replace(b'\r\n',b'\n')).hexdigest()==digest,path
    changes=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={path,'android/ci/local_verification.py','android/ci/report_local.py',
             'android/ci/test_output_history_retry.py'}
    assert path in changes and all(p in allowed or p.startswith('docs/android/') for p in changes),changes


OUTPUT_RESOURCE_BEFORE='118a4a4aa0af57dae0fdb60b64d4406251b70c95'


def pending_output_resource_fix(root, before, after, completed):
    """Only the reviewed C02 diagnostic fighter boundary may change."""
    assert before==OUTPUT_RESOURCE_BEFORE and completed==plan('full',None)[:55]
    assert plan('full',None)[55]=='headless:resources'
    path='tools/android_headless/check_resources.py'
    for revision,digest in ((before,'d7eb87af482e02d80668bf218502726944f26c90e2b9d7a7594d884927c9c0ba'),
                            (after,'9f2b992ebbc38a8925d8cdde617a301ce5bee674cffb7cad9d465624d60671f1')):
        source=subprocess.check_output(['git','show',revision+':'+path],cwd=root)
        assert hashlib.sha256(source.replace(b'\r\n',b'\n')).hexdigest()==digest,path
    changes=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={path,'android/ci/local_verification.py','android/ci/report_local.py','android/ci/test_output_resource_retry.py'}
    assert path in changes and all(p in allowed or p.startswith('docs/android/') for p in changes),changes
    import ast
    def executed(revision):
        source=subprocess.check_output(['git','show',revision+':android/ci/local_verification.py'],cwd=root,text=True,encoding='utf-8')
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(source))
                if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(before)==executed(after),'Executed host/build behavior changed'


def pending_runner_fix(root, before, after, completed):
    """Only the missing storage flag may change before any B09.2 phase passes."""
    assert 'native:check-history.py' in completed
    assert not any(g.startswith('native:mutation-history-') for g in completed)
    path = 'android/app/src/androidTest/java/io/github/sussic/pyfa/DiagnosticTestRunner.kt'
    def source(commit, name):
        return subprocess.check_output(['git', 'show', commit + ':' + name], cwd=root, text=True, encoding='utf-8')
    old = source(before, path)
    ending = '!arguments.containsKey("b091_phase"))'
    assert old.count(ending) == 1
    assert source(after, path) == old.replace(ending,
        '!arguments.containsKey("b091_phase") &&\n            !arguments.containsKey("b092_phase"))', 1)
    changes = subprocess.check_output(['git', 'diff', '--name-only', before, after], cwd=root, text=True).splitlines()
    allowed = {path, 'android/ci/local_verification.py', 'android/ci/report_local.py', 'android/ci/test_pending_runner_fix.py'}
    assert path in changes and set(changes) <= allowed, changes
    import ast
    def executed(text):
        return {n.name: ast.dump(n, include_attributes=False) for n in ast.walk(ast.parse(text))
            if isinstance(n, ast.FunctionDef) and n.name in ('plan', 'host', 'build', 'execute')}
    assert executed(source(before, 'android/ci/local_verification.py')) == executed(source(after, 'android/ci/local_verification.py'))

def pending_settings_fix(root, before, after):
    """Only the named whole-double settings comparison may change in raw validation."""
    def source(commit, name):
        return subprocess.check_output(['git','show',commit+':'+name],cwd=root,text=True,encoding='utf-8')
    path='android/ci/mutation_history_summary.py'
    addition='''def settings(expected, actual):
    # JSONObject writes the whole-valued double 1.0 as 1. Only this setting's
    # representation may differ; its numeric value must still match exactly.
    exact(set(expected), set(actual))
    for key, value in expected.items():
        other = actual[key]
        if key == 'globalDefaultSpoolupPercentage':
            assert type(value) is float and type(other) in (int, float)
            assert isfinite(value) and isfinite(other) and value == other
        else: exact(value, other)


'''
    old=source(before,path)
    line="    exact(fixture['eos_settings'], engine['eos_settings'])"
    assert old.count(line)==1 and old.count('def _typed_shape(value):')==1
    expected=old.replace('def _typed_shape(value):',addition+'def _typed_shape(value):',1).replace(line,"    settings(fixture['eos_settings'], engine['eos_settings'])",1)
    assert source(after,path)==expected, 'Unrelated raw validator change'
    changes=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={path,'android/ci/test_mutation_history_summary.py','android/ci/local_verification.py',
        'android/ci/report_local.py','android/ci/revalidate-mutation-history.py','android/ci/test_pending_settings_fix.py'}
    assert path in changes and set(changes)<=allowed,changes
    import ast
    def executed(text):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.walk(ast.parse(text))
            if isinstance(n,ast.FunctionDef) and n.name in ('plan','host','build','execute')}
    assert executed(source(before,'android/ci/local_verification.py'))==executed(source(after,'android/ci/local_verification.py'))

def pending_stale_test_fixture_fix(root,before,after):
    path='android/ci/test_stale_history_retry.py'
    def source(commit):return subprocess.check_output(['git','show',commit+':'+path],cwd=root,text=True,encoding='utf-8')
    old=source(before)
    line='self.new={path:(ROOT/path).read_text() for path in self.old}'
    replacement="self.new={path:subprocess.check_output(['git','show','7812de8024259d890e77435f794e69f71e75326b:'+path],cwd=ROOT,text=True,encoding='utf-8') for path in self.old}"
    assert old.count(line)==1 and source(after)==old.replace(line,replacement,1)


def pending_defense_phase_flag_fix(root,before,after,completed):
    """Retain only the58 preceding gates for the exact unexecuted flag expectation."""
    assert before=='9badd3ec58aa3a5bb2e325ec60da5751eea64830'
    assert completed==plan('full',None)[:58] and 'headless:defenses' not in completed
    path='android/ci/test_defense_summary.py'
    def source(commit):return subprocess.check_output(['git','show',commit+':'+path],cwd=root,text=True,encoding='utf-8')
    old=source(before);line="{'c013_phase','c0132_phase','c02_phase'}"
    replacement="{'c013_phase','c0132_phase','c02_phase','c031_phase'}"
    assert old.count(line)==1 and source(after)==old.replace(line,replacement,1), 'Unrelated defense test change'
    changes=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={path,'android/ci/local_verification.py','android/ci/report_local.py','android/ci/test_pending_defense_phase_flag_fix.py'}
    assert path in changes and all(p in allowed or p.startswith('docs/android/') for p in changes),changes


def save(path,value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def plan(mode,gate):
    desktop=['desktop:utilities','desktop:reference','desktop:migration',
        *('reference:'+name for name in FAMILIES),
        'headless:base','headless:projection','headless:command',
        *('headless:'+name for name in HEADLESS),
        *('reference:inspector_'+name for name in INSPECTOR),
        *('headless:inspector_'+name for name in INSPECTOR if name not in ('inventory','sorting','text','contexts')),
        'headless:inspector_presentation','headless:inspector_payloads','headless:inspector_lifecycle']
    if gate:
        if gate=='projected_module_charges':
            if mode!='native': raise ValueError('Supplemental projected-module charges use native mode')
            return ['build:'+name for name in BUILD]+['native:projected_module_charges']
        if gate=='shield_regeneration_graph':
            if mode!='native': raise ValueError('Supplemental shield regeneration uses native mode')
            return ['build:'+name for name in BUILD]+['native:shield_regeneration_graph']
        if gate=='remote_repair_graph':
            if mode!='native': raise ValueError('Supplemental remote repair uses native mode')
            return ['build:'+name for name in BUILD]+['native:remote_repair_graph']
        if gate.startswith('drone_'):
            assert mode=='desktop', 'Focused drone gates use desktop mode'
            matching=[name for name in DRONE_HOST_GATES if name.split(':',1)[1]==gate]
            assert matching, 'Unknown focused drone gate'
            return matching
        if gate=='inspector_lifecycle':
            assert mode=='desktop', 'Focused lifecycle checks use desktop mode'
            return ['headless:inspector_lifecycle']
        if gate.startswith('inspector_'):
            name=gate.removeprefix('inspector_')
            assert mode=='desktop' and name in INSPECTOR, 'Unknown focused inspector gate'
            return ['reference:'+gate] + ([] if name in ('inventory','sorting','text','contexts') else ['headless:'+gate])
        assert mode=='desktop' and gate in FAMILIES, 'Focused gates use desktop --gate <family>'
        return ['reference:'+gate,'headless:'+({'equipment':'market'}.get(gate,gate))] if gate not in ('catalog',) else ['reference:'+gate]
    return (desktop + (list(DRONE_HOST_GATES) if mode=='desktop' else []) if mode in ('full','desktop') else []) + \
        ['build:'+name for name in BUILD if mode in ('full','build','native')] + \
        ['native:'+name for name in NATIVE_STEPS if mode in ('full','native')] + \
        ['native:inspection-'+name for name in (*INSPECTION_PHASES, 'summary') if mode in ('full','native')] + \
        (list(DRONE_HOST_GATES) if mode=='full' else []) + \
        ([DRONE_NATIVE_GATE] if mode in ('full','native') else []) + \
        ([DRONE_DECISION_GATE] if mode=='full' else [])


def pending_inspector_context_metadata_fix(root,before,after,completed):
    """Only the unexecuted metadata fixture's stale context provenance may change."""
    assert before=='e9a2baa24c4eed986673ebf0e2da0ef4e07bfc87'
    assert completed==plan('full',None)[:79] and len(completed)==79
    path='tools/android_reference/fixtures/inspector-context-metadata.json'
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True).splitlines()
    allowed={path,'android/ci/local_verification.py','android/ci/report_local.py',
             'android/ci/test_inspector_plan.py','android/ci/test_report_local.py'}
    assert changed and all(p in allowed or p.startswith('docs/android/') for p in changed)
    old=subprocess.check_output(['git','show',before+':'+path],cwd=root,text=True,encoding='utf-8')
    new=subprocess.check_output(['git','show',after+':'+path],cwd=root,text=True,encoding='utf-8')
    stale='2a0853198524c7d2e37cd3d1857dbdc8be30d2f9ef002e8cc6fd20411b4163a6'
    actual='e2ea5a564e6220b0add14d7089fd65703ef9ed79fad4c818422c2985b0307f97'
    assert old.count(stale)==1 and new==old.replace(stale,actual), 'Metadata values or other provenance changed'


def pending_inspector_booster_history_fix(root,before,after,completed):
    """Retain only55 gates preceding the exact added four-command history witness."""
    assert before=='750e4a7df002a44a9da6f907176e974c0bd2627b'
    assert completed==plan('full',None)[:55] and len(completed)==55
    path='tools/android_headless/check_history_mutations.py'
    def source(revision,name):
        return subprocess.check_output(['git','show',revision+':'+name],cwd=root,text=True,encoding='utf-8')
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True,encoding='utf-8').splitlines()
    allowed={path,'tools/android_headless/booster_history_witness.py','android/ci/local_verification.py',
             'android/ci/test_inspector_plan.py','android/ci/report_local.py','android/ci/test_report_local.py'}
    assert changed and all(p in allowed or p.startswith('docs/android/') for p in changed)
    marker="            compare(set(LABELS) - set(MODULE_LABELS), covered - {'change_variation'})"
    extra='''            # Keep the complete registered-operation assertion. C03 adds four
            # booster commands; execute their independent reference witnesses.
            from tools.android_headless.booster_history_witness import witness
            self.bridge._reset_storage(); self.bridge=BridgeSession(engine)
            booster=witness(self.bridge,self.send,ROOT/'tools/android_reference/fixtures/inspector-contexts.json.gz')
            covered.update(booster['operations'])
            (args.output/'booster-history.json').write_text(json.dumps(booster,indent=2)+'\\n',encoding='utf-8')
'''
    old=source(before,path);assert old.count(marker)==1
    assert source(after,path)==old.replace(marker,extra+marker), 'Existing history verification changed'
    witness=source(after,'tools/android_headless/booster_history_witness.py')
    assert hashlib.sha256(witness.encode('utf-8')).hexdigest()=='bfadc905bb11241ca85f7212bc6ca7ab611d02042f6ea17c926dfe5296a5b6d0', 'Booster witness changed'


def pending_inspector_library_copy_fix(root,before,after,completed):
    """Reuse only gates preceding the exact inherited copy-identity assertion repair."""
    assert before=='fb35ca91c6cd73e3e9ecd71037984d2d3da268a5'
    assert completed==plan('full',None)[:36] and len(completed)==36
    path='tools/android_headless/tests/test_library.py'
    def source(revision):
        return subprocess.check_output(['git','show',revision+':'+path],cwd=root,text=True,encoding='utf-8')
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True,encoding='utf-8').splitlines()
    allowed={path,'android/ci/local_verification.py','android/ci/test_inspector_plan.py'}
    assert changed and all(p in allowed or p.startswith('docs/android/') for p in changed)
    old=source(before)
    marker='        copied = self.send("duplicate_fit", {"fit_id": source, "name": "Source copy"})'
    equal='        self.assertEqual(copy, expected)'
    original='        self.assertEqual(self.bridge._records[source], {**expected, "spec": {**expected["spec"], "name": originals[source]["name"]}})'
    identity='''        from android_bridge.inspection_identity import validate
        original_ids = original_record["inspection_ids"]
        validate(copy["inspection_ids"], {table: len(keys) for table, keys in original_ids.items()})
        self.assertTrue(set(key for keys in original_ids.values() for key in keys).isdisjoint(
            key for keys in copy["inspection_ids"].values() for key in keys))
        expected["inspection_ids"] = deepcopy(copy["inspection_ids"])
'''
    assert old.count(marker)==old.count(equal)==old.count(original)==1
    expected=old.replace(marker,'        original_record = deepcopy(self.bridge._records[source])\n'+marker)
    expected=expected.replace(equal,identity+equal).replace(original,'        self.assertEqual(self.bridge._records[source], original_record)')
    assert source(after)==expected, 'Library test changed beyond the exact copy-identity correction'


def pending_targeting_metadata_index_fix(root,before,after,completed):
    """Retain only the61 inputs completed before this exact unexecuted validator fix."""
    assert before=='bfbbe1570c82b0e884f18461fa379f59b793dfbd'
    assert completed==plan('full',None)[:61] and len(completed)==61 and completed[-1]=='headless:output'
    def source(revision,path):
        return subprocess.check_output(['git','show',revision+':'+path],cwd=root,text=True,encoding='utf-8')
    changed=subprocess.check_output(['git','diff','--name-only',before,after],cwd=root,text=True,encoding='utf-8').splitlines()
    allowed={'android/ci/targeting_summary.py','android/ci/test_targeting_summary.py',
        'android/ci/local_verification.py','android/ci/report_local.py','android/ci/test_pending_targeting_metadata_index_fix.py'}
    assert changed and all(p in allowed or p.startswith('docs/android/') for p in changed)
    index='''def metadata_groups(wrapper,prefixes):
    """Index exactly the old prefix filters, including overlapping opaque IDs."""
    groups={prefix:{} for prefix in prefixes};trie={}
    for prefix in groups:
        node=trie
        for char in prefix:node=node.setdefault(char,{})
        node[None]=prefix
    for name,kind in wrapper['numeric_types'].items():
        node=trie
        for index,char in enumerate(name):
            node=node.get(char)
            if node is None:break
            prefix=node.get(None)
            if prefix is not None and (index+1==len(name) or name[index+1] in '.['):
                groups[prefix][name]=kind
    return groups


'''
    path='android/ci/targeting_summary.py';old=source(before,path)
    marker='def summarize(reports,engine,prior_pids=()):'
    scan="                def metadata(wrapper):return {k:v for k,v in wrapper['numeric_types'].items() if k==prefix or k.startswith(prefix+'.') or k.startswith(prefix+'[')}\n                exact(metadata(saved['inherited_graph']),metadata(saved['graph']))"
    loop='        for row in inherited:'
    indexed="        prefixes=[f'root.{field}.{key}' for key in old for field in ('records','revisions','modified')]\n        before_metadata=metadata_groups(saved['inherited_graph'],prefixes);after_metadata=metadata_groups(saved['graph'],prefixes)\n"+loop
    assert old.count(marker)==old.count(scan)==old.count(loop)==1
    expected=old.replace(marker,index+marker).replace(loop,indexed).replace(scan,'                exact(before_metadata[prefix],after_metadata[prefix])')
    assert source(after,path)==expected, 'Targeting validation changed beyond exact equivalent metadata indexing'
    regression='''class MetadataIndexTests(unittest.TestCase):
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


'''
    path='android/ci/test_targeting_summary.py';old=source(before,path)
    imports='from targeting_summary import targeting,summarize,REJECTIONS'
    main="if __name__=='__main__':unittest.main()"
    assert old.count(imports)==old.count(main)==1
    assert source(after,path)==old.replace(imports,imports+',metadata_groups').replace(main,regression+main), 'Original targeting tests or corruptions changed'


class Run:
    def __init__(self,args):
        self.args=args
        self.policy,self.policy_sha256=load_policy()
        self.host=getattr(args,'execution_host',None) or os.environ.get('CODEX_EXECUTION_HOST') or detect_host()
        if self.host!=detect_host():
            raise RuntimeError('Selected policy host differs from the actual physical executor')
        self.workload=('build' if args.mode=='build' else
                       'focused_test' if args.mode=='desktop' and args.gate else 'full_suite')
        self.settings=select(self.policy,self.host,self.workload)
        if self.host=='initia' and self.settings['preferred_host']=='msi':
            raise AdmissionDeferred('This selection belongs in the durable MSI queue; continue independent implementation on Initia')
        self.execution_root=Path(self.policy['locations']['execution_root'].format(host=self.host,project=self.policy['project']))
        self.execution_started=None
        self.pressure=PressureWindow(self.settings)
        self.directory=Path(args.run).resolve() if args.run else \
            self.execution_root/'results'/(
                datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+git('rev-parse','--short','HEAD')+'-'+uuid.uuid4().hex[:6])
        assert not self.directory.is_relative_to(ROOT), 'Keep large evidence outside the synced checkout'
        self.file=self.directory/'run.json'
        policy_roots=[value.format(repository=str(ROOT),execution_root=str(self.execution_root),host=self.host)
                      for value in self.policy['storage']['accounting_roots']]
        self.artifact_budget=ArtifactBudget([
            *policy_roots,ROOT/'android/build',ROOT/'android/app/build',self.directory,
            *getattr(args,'artifact_root',[])],policy=(self.policy,self.policy_sha256),host=self.host)
        self.artifact_budget.check()
        self.emulator=None
        self.serial=None
        if args.action=='start':
            assert not git('status','--porcelain','--untracked-files=normal'), 'Commit reviewed changes before recording exact-commit evidence'
            self.directory.mkdir(parents=True,exist_ok=False)
            self.state={'version':1,'commit':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),
                'mode':args.mode,'gate':args.gate,'status':'pending','plan':plan(args.mode,args.gate),
                'completed':[],'attempts':[],'platform':platform.platform(),'python':sys.version,
                'started_utc':datetime.now(timezone.utc).isoformat(),'hosted_actions_pass':False}
            save(self.file,self.state)
        else:
            self.original_run_bytes=self.file.read_bytes()
            self.state=json.loads(self.file.read_text(encoding='utf-8'))
            self.artifact_budget.include_previous(self.state.get('artifact_retention'))
            self.artifact_budget.check()
            assert self.state['status'] != 'passed', 'Completed runs are immutable; start a new run'
            assert not git('status','--porcelain','--untracked-files=normal'), 'Resume the same clean tested commit'
            current=git('rev-parse','HEAD')
            if self.state['commit']!=current and args.adopt_launcher_fix and self.state.get('targeting_phase_reuse'):
                from targeting_phase_retry import adopt_preflight_fix
                adopt_preflight_fix(self,current)
            if self.state['commit']!=current and args.adopt_launcher_fix and self.state['commit']=='9736218ec7b212642ce964d76ec3338bf6f91909':
                from targeting_phase_retry import adopt
                adopt(self,current)
            if self.state['commit']!=current and args.adopt_launcher_fix and self.state.get('cargo_search_reuse'):
                from cargo_search_retry import adopt_artifact_flush_retry
                adopt_artifact_flush_retry(self,current)
            if self.state['commit']!=current and args.adopt_launcher_fix:
                from cargo_search_retry import BEFORE as cargo_search_before,exact_source as cargo_search_source
                if self.state['commit']==cargo_search_before:
                    assert self.state['status']=='failed' and self.state['mode']=='full' and self.state['gate'] is None
                    assert self.state['attempts'][-1]['gate']=='native:check-cargo-actions.py' and self.state['attempts'][-1]['exit_code']!=0
                    cargo_search_source(ROOT,self.state['commit'],current,self.state['completed'])
                    retained=[g for g in self.state['completed'] if not g.startswith('build:')]
                    latest={row['gate']:row for row in self.state['attempts']}
                    self.state['cargo_search_reuse']={'from_commit':self.state['commit'],'to_commit':current,
                        'completed_before_adoption':list(self.state['completed']),'retained_gates':retained,
                        'retained_log_hashes':{gate:latest[gate]['log_sha256'] for gate in retained},
                        'prepared':False,'installed':False}
                    self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and getattr(args,'adopt_tank_history_fix',False):
                assert self.state['status']=='failed' and self.state['completed']==plan('full',None)[:-3]
                failure=next(row for row in reversed(self.state['attempts']) if row['gate'].startswith('native:'))
                assert failure['gate']=='native:tank-prepare' and failure['exit_code']!=0
                from tank_history_retry import exact_source
                exact_source(ROOT,self.state['commit'],current)
                before=self.state['commit']
                for row in self.state['attempts']:row.setdefault('tested_commit',before)
                self.state['tank_history_reuse']={'from_commit':before,'to_commit':current,
                    'completed_before_adoption':list(self.state['completed']),
                    'retained_gates':[g for g in self.state['completed'] if g not in ('build:apks-lint','build:package')],
                    'prepared':False,'installed':False}
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_capacitor_runner_fix:
                from capacitor_runner_retry import exact_source
                assert self.state['status']=='failed' and self.state['completed']==plan('full',None)[:-3]
                assert self.state['attempts'][-1]['gate']=='native:capacitor-prepare' and self.state['attempts'][-1]['exit_code']!=0
                exact_source(ROOT,self.state['commit'],current)
                before=self.state['commit']
                for row in self.state['attempts']:row.setdefault('tested_commit',before)
                self.state['capacitor_runner_reuse']={'from_commit':before,'to_commit':current,
                    'retained_gates':list(self.state['completed']),'prepared':False,'installed':False}
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_resource_test_fix:
                assert self.state['status']=='failed' and self.state['completed']==plan('full',None)[:-3]
                failure=next(row for row in reversed(self.state['attempts']) if row['gate'].startswith('native:'))
                assert failure['gate']=='native:resources-prepare' and failure['exit_code']!=0
                from resource_test_retry import exact_source
                exact_source(ROOT,self.state['commit'],current)
                before=self.state['commit']
                for row in self.state['attempts']:row.setdefault('tested_commit',before)
                self.state.setdefault('resource_test_reuse',[]).append({'from_commit':before,'to_commit':current,
                    'completed_before_adoption':list(self.state['completed']),
                    'retained_gates':[gate for gate in self.state['completed'] if gate not in ('build:apks-lint','build:package')],
                    'prepared':False,'installed':False})
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_projection_report_fix:
                assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='native:mutation-history-3-prepare'
                assert self.state['attempts'][-1]['exit_code']!=0 and 'native:mutation-history-3-prepare' not in self.state['completed']
                assert 'native:mutation-history-2-restored' in self.state['completed']
                from projection_history_retry import exact_source
                exact_source(ROOT,self.state['commit'],current)
                self.state.setdefault('projection_report_reuse',[]).append({'from_commit':self.state['commit'],'to_commit':current,
                    'retained_gates':list(self.state['completed']),'validated':False})
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_stale_history_fix:
                assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='native:mutation-history-3-prepare'
                assert self.state['attempts'][-1]['exit_code']!=0
                assert [g for g in self.state['completed'] if g.startswith('native:mutation-history-')]==[f'native:mutation-history-{group}-{phase}' for group in range(3) for phase in ('prepare','restored')]
                from stale_history_retry import exact_source
                exact_source(ROOT,self.state['commit'],current)
                self.state.setdefault('stale_history_reuse',[]).append({'from_commit':self.state['commit'],'to_commit':current,
                    'retained_gates':list(self.state['completed']),'prepared':False})
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_cargo_observer_fix:
                assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='native:mutation-history-1-prepare'
                assert self.state['attempts'][-1]['exit_code']!=0
                assert 'native:check-history.py' in self.state['completed']
                assert [g for g in self.state['completed'] if g.startswith('native:mutation-history-')]==['native:mutation-history-0-prepare','native:mutation-history-0-restored']
                from cargo_history_retry import exact_source
                exact_source(ROOT,self.state['commit'],current)
                retained=[g for g in self.state['completed'] if not g.startswith('native:mutation-history-')]
                self.state.setdefault('cargo_observer_reuse',[]).append({'from_commit':self.state['commit'],'to_commit':current,
                    'completed_before_adoption':list(self.state['completed']),'retained_gates':retained,'prepared':False})
                self.state['completed']=retained
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_pending_settings_fix:
                assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='native:mutation-history-0-restored'
                assert self.state['attempts'][-1]['exit_code']!=0 and 'native:mutation-history-0-prepare' in self.state['completed']
                assert not any(g.startswith('native:mutation-history-1-') for g in self.state['completed'])
                pending_settings_fix(ROOT,self.state['commit'],current)
                self.state.setdefault('settings_fix_reuse',[]).append({'from_commit':self.state['commit'],'to_commit':current,
                    'completed_before_adoption':list(self.state['completed']),'validated':False})
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_pending_runner_fix:
                assert self.state['status']=='failed'
                assert self.state['attempts'][-1]['gate']=='native:mutation-history-0-prepare'
                assert self.state['attempts'][-1]['exit_code']!=0
                pending_runner_fix(ROOT,self.state['commit'],current,self.state['completed'])
                proof={'from_commit':self.state['commit'],'to_commit':current,
                    'completed_before_adoption':list(self.state['completed']),'prepared':False}
                self.state.setdefault('runner_fix_reuse',[]).append(proof)
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_launcher_fix and self.state['commit']==OUTPUT_RESOURCE_BEFORE:
                assert self.state['status']=='failed'
                assert self.state['attempts'][-1]['gate']=='headless:resources' and self.state['attempts'][-1]['exit_code']!=0
                assert self.state['plan']==plan(self.state['mode'],self.state['gate'])
                pending_output_resource_fix(ROOT,self.state['commit'],current,self.state['completed'])
                for row in self.state['attempts']:row.setdefault('tested_commit',self.state['commit'])
                self.state['output_resource_reuse']={'from_commit':self.state['commit'],'to_commit':current,
                    'completed_before_adoption':list(self.state['completed'])}
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.adopt_launcher_fix and self.state.get('charge_keyboard_host_reuse'):
                from charge_keyboard_retry import ALIAS_BEFORE,adopt_alias_fix
                if self.state['commit']==ALIAS_BEFORE:
                    adopt_alias_fix(ROOT,self.directory,self.state,current,self.original_run_bytes)
                    self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.restart_native:
                from charge_keyboard_retry import BEFORE as charge_before,exact_source as charge_source
                if self.state['commit']==charge_before:
                    assert self.state['status']=='failed' and self.state['mode']=='full' and self.state['gate'] is None
                    assert self.state['attempts'][-1]['gate']=='native:check-charge-edits.py' and self.state['attempts'][-1]['exit_code']!=0
                    charge_source(ROOT,self.state['commit'],current,self.state['completed'])
                    for row in self.state['attempts']:row.setdefault('tested_commit',self.state['commit'])
                    retained=[g for g in self.state['completed'] if g.startswith(('desktop:','reference:','headless:'))]
                    latest={row['gate']:row for row in self.state['attempts'] if row['exit_code']==0}
                    self.state['charge_keyboard_host_reuse']={'from_commit':self.state['commit'],'to_commit':current,
                        'completed_before_adoption':list(self.state['completed']),'retained_gates':retained,
                        'retained_log_hashes':{gate:latest[gate]['log_sha256'] for gate in retained}}
                    self.state['completed']=list(retained)
                    self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current and args.restart_native:
                from output_profile_retry import BEFORE,exact_source
                if self.state['commit']==BEFORE:
                    assert self.state['status']=='failed' and self.state['mode']=='full' and self.state['gate'] is None
                    assert self.state['attempts'][-1]['gate']=='native:output-prepare' and self.state['attempts'][-1]['exit_code']!=0
                    exact_source(ROOT,self.state['commit'],current,self.state['completed'])
                    for row in self.state['attempts']:row.setdefault('tested_commit',self.state['commit'])
                    retained=[g for g in self.state['completed'] if g.startswith(('desktop:','reference:','headless:'))]
                    self.state['output_profile_host_reuse']={'from_commit':self.state['commit'],'to_commit':current,
                        'completed_before_adoption':list(self.state['completed']),'retained_gates':retained}
                    self.state['completed']=retained
                    self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            if self.state['commit']!=current:
                assert args.adopt_launcher_fix or args.restart_native, 'Resume the same commit, explicitly adopt a launcher fix, or restart native verification'
                assert args.restart_native or not any(step.startswith('native:') for step in self.state['completed']), 'Native execution has begun; require a fresh native run'
                changed=git('diff','--name-only',self.state['commit'],current).splitlines()
                allowed={'android/ci/local_verification.py','android/ci/native_suite.py','android/verify-local.ps1',
                    'android/ci/report_local.py','android/ci/test_report_local.py'}
                if 'tools/android_reference/fixtures/inspector-context-metadata.json' in changed:
                    assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='reference:inspector_context_metadata' and self.state['attempts'][-1]['exit_code']!=0
                    pending_inspector_context_metadata_fix(ROOT,self.state['commit'],current,self.state['completed'])
                    allowed.update({'tools/android_reference/fixtures/inspector-context-metadata.json','android/ci/test_inspector_plan.py',*[p for p in changed if p.startswith('docs/android/')]})
                if 'tools/android_headless/tests/test_library.py' in changed:
                    assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='headless:library' and self.state['attempts'][-1]['exit_code']!=0
                    pending_inspector_library_copy_fix(ROOT,self.state['commit'],current,self.state['completed'])
                    allowed.update({'tools/android_headless/tests/test_library.py','android/ci/test_inspector_plan.py',*[p for p in changed if p.startswith('docs/android/')]})
                if 'android/ci/test_native_artifact_read.py' in changed:
                    allowed.add('android/ci/test_native_artifact_read.py')
                if 'android/ci/test_stale_history_retry.py' in changed:
                    pending_stale_test_fixture_fix(ROOT,self.state['commit'],current)
                    allowed.add('android/ci/test_stale_history_retry.py')
                if 'android/ci/targeting_summary.py' in changed:
                    assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='headless:targeting' and self.state['attempts'][-1]['exit_code']!=0
                    pending_targeting_metadata_index_fix(ROOT,self.state['commit'],current,self.state['completed'])
                    allowed.update({'android/ci/targeting_summary.py','android/ci/test_targeting_summary.py','android/ci/test_pending_targeting_metadata_index_fix.py',*[p for p in changed if p.startswith('docs/android/')]})
                if 'android/ci/test_defense_summary.py' in changed:
                    assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='headless:defenses' and self.state['attempts'][-1]['exit_code']!=0
                    pending_defense_phase_flag_fix(ROOT,self.state['commit'],current,self.state['completed'])
                    allowed.update({'android/ci/test_defense_summary.py','android/ci/test_pending_defense_phase_flag_fix.py',*[p for p in changed if p.startswith('docs/android/')]})
                if 'tools/android_headless/check_history_mutations.py' in changed:
                    if self.state['commit']=='750e4a7df002a44a9da6f907176e974c0bd2627b':
                        assert self.state['status']=='failed' and self.state['attempts'][-1]['gate']=='headless:history_mutations' and self.state['attempts'][-1]['exit_code']!=0
                        pending_inspector_booster_history_fix(ROOT,self.state['commit'],current,self.state['completed'])
                        allowed.update({'tools/android_headless/booster_history_witness.py','android/ci/test_inspector_plan.py',*[p for p in changed if p.startswith('docs/android/')]})
                    elif self.state['commit']==OUTPUT_HISTORY_BEFORE:
                        assert self.state['status']=='failed'
                        assert self.state['attempts'][-1]['gate']=='headless:history_mutations' and self.state['attempts'][-1]['exit_code']!=0
                        pending_output_history_fix(ROOT,self.state['commit'],current,self.state['completed'])
                        allowed.update({'android/ci/test_output_history_retry.py',*[p for p in changed if p.startswith('docs/android/')]})
                    else:
                        assert not any(row['gate'] == 'headless:history_mutations' for row in self.state['attempts'])
                        pending_mutation_count_fix(ROOT, self.state['commit'], current, self.state['completed'])
                    allowed.add('tools/android_headless/check_history_mutations.py')
                if 'tools/android_reference/tank.py' in changed:
                    pending_tank_fixture_fix(ROOT, self.state['commit'], current, self.state['completed'])
                    allowed.update({'tools/android_reference/tank.py','tools/android_reference/fixtures/tank.json',
                                    'android/ci/test_pending_tank_fixture_fix.py','docs/android/STATUS.md'})
                if args.restart_native:
                    allowed.update({'android/ci/check-history.py','android/ci/history_progress.py',
                        'android/ci/report_local.py','android/ci/test_report_local.py'})
                    changed=[p for p in changed if p!='AGENTS.md' and not p.startswith('docs/android/')]
                    if 'android/ci/check-history.py' in changed:
                        old_history=git('show',self.state['commit']+':android/ci/check-history.py')
                        new_history=(ROOT/'android/ci/check-history.py').read_text(encoding='utf-8').strip()
                        expected_history=old_history.replace('import json\n','import json\nimport os\n',1).replace('timeout=900)',"timeout=2400 if os.name == 'nt' else 900)",1)
                        assert new_history==expected_history, 'Only the approved import and exact Windows history timeout expression may change'
                assert changed and set(changed)<=allowed, 'Completed host/build inputs changed; results cannot be reused'
                import ast
                previous=ast.parse(git('show',self.state['commit']+':android/ci/local_verification.py'))
                present=ast.parse(Path(__file__).read_text(encoding='utf-8'))
                def executed(tree):
                    result={}
                    for node in ast.walk(tree):
                        if isinstance(node,ast.FunctionDef) and node.name in ('plan','host','build','execute'):
                            result[node.name]=ast.dump(node,include_attributes=False)
                    return result
                assert executed(previous)==executed(present), 'Executed host/build behavior changed'
                assert self.state['plan']==plan(self.state['mode'],self.state['gate'])
                for row in self.state['attempts']: row.setdefault('tested_commit',self.state['commit'])
                self.state.setdefault('launcher_fix_reuse',[]).append({'from_commit':self.state['commit'],
                    'to_commit':current,'changed_files':changed,'completed_before_adoption':list(self.state['completed']),
                    'unchanged_completed_host_build_inputs':True})
                self.state['commit']=current;self.state['tree']=git('rev-parse','HEAD^{tree}')
            assert self.state['tree']==git('rev-parse','HEAD^{tree}')
        self.state['artifact_retention']={
            'version':2,'limit_bytes':self.artifact_budget.limit,
            'policy_sha256':self.policy_sha256,
            'historical_policies':self.artifact_budget.historical_policies,
            'roots':self.artifact_budget.roots,'poll_seconds':self.artifact_budget.interval,
            'failed_paused':'preserve until explicitly triaged',
            'budget_response':'stop owned work; never truncate or evict evidence'}
        self.state['execution_policy']={'path':'execution-policy.json','sha256':self.policy_sha256,
            'revision':self.policy['policy_revision'],'host':self.host,'workload':self.workload,
            'workers':self.settings['workers']}
        save(self.file,self.state)
        self.native=self.directory/'native';self.native.mkdir(exist_ok=True)
        os.environ['PYFA_EVIDENCE_DIR']=str(self.native)
        os.environ['PYFA_EXECUTION_KIND']='local_windows'
        os.environ['PYFA_LOCAL_RUN_ID']=self.directory.name
        os.environ['PYTHONUTF8']='1'
        os.environ.pop('GITHUB_RUN_ID',None);os.environ.pop('GITHUB_STEP_SUMMARY',None)
        self.reference=Path(args.reference_python or self.execution_root/'environments/reference/Scripts/python.exe')
        self.source=Path(args.source or self.execution_root/'cache/reference-upstream').resolve()
        assert git('-C',str(self.source),'rev-parse','HEAD')==PIN
        self.db=Path(self.state.get('database',ROOT/'android/build/engine/assets/engine/eve.db'))
        assert sys.version_info[:2]==(3,11), 'Reuse the pinned Python 3.11 environment'
        assert sha(ROOT/'android/gradle/wrapper/gradle-wrapper.jar')=='81a82aaea5abcc8ff68b3dfcb58b3c3c429378efd98e7433460610fecd7ae45f'

    def check_running_resources(self):
        physical,commit=host_memory()
        now=time.monotonic()
        if self.pressure.sample(now,physical,commit):
            raise AdmissionDeferred('Sustained host memory pressure; preserve this run and queue remaining validation')
        if self.execution_started is not None and now-self.execution_started>=self.settings['timeout_seconds']:
            raise AdmissionDeferred('Current workload deadline consumed; checkpoint remaining validation')

    def admit_command(self):
        physical,commit=host_memory()
        self.artifact_budget.check()
        measured=self.artifact_budget.latest
        reasons=admit(self.settings,physical,commit,shutil.disk_usage(self.directory).free,
                      self.settings['estimated_disk_write_bytes'],measured['allocated_bytes'])
        if reasons:
            raise AdmissionDeferred('; '.join(reasons)+'; queue this check and continue independent implementation')

    def execute(self,name,command,cwd=ROOT,timeout=None):
        self.admit_command()
        remaining=self.settings['timeout_seconds']-(time.monotonic()-self.execution_started)
        timeout=min(timeout,remaining) if timeout is not None else remaining
        attempt=self.directory/'logs'/f'{len(self.state["attempts"]):03}-{name.replace(":","-")}.log'
        attempt.parent.mkdir(exist_ok=True)
        row={'gate':name,'command':list(map(str,command)),'log':str(attempt.relative_to(self.directory)),
            'tested_commit':self.state['commit'],
            'started_utc':datetime.now(timezone.utc).isoformat()}
        self.state['attempts'].append(row);save(self.file,self.state)
        print('Running '+name,flush=True)
        started=time.monotonic()
        with attempt.open('wb') as log:
            try:
                result=self.artifact_budget.run(list(map(str,command)),cwd=cwd,stdout=log,stderr=subprocess.STDOUT,timeout=timeout)
                row['exit_code']=result.returncode
            except BaseException:
                row['exit_code']=None;row['interrupted']=True;save(self.file,self.state);raise
        row['seconds']=round(time.monotonic()-started,3);row['log_sha256']=sha(attempt)
        save(self.file,self.state)
        if row['exit_code']!=0:
            print(attempt.read_text(encoding='utf-8',errors='replace')[-6000:],flush=True)
            raise RuntimeError(f'{name} failed; full log: {attempt}')
        print('PASS '+name,flush=True)

    def host(self,step):
        kind,name=step.split(':',1)
        output=self.directory/'host'/f'{len(self.state["attempts"]):03}-{kind}-{name}'
        output.parent.mkdir(exist_ok=True)
        if step in DRONE_HOST_GATES:
            from drone_delivery import host_command
            self.execute(step,host_command(step,output,self.db,self.reference,self.source),timeout=180)
            return
        if step=='desktop:utilities': command=[self.reference,'-m','unittest','discover','-s','tools/android_reference/tests','-v']
        elif step=='desktop:reference': command=[self.reference,'-I','tools/android_reference/reference.py','--source',self.source,'--output',output,'--check','tools/android_reference/fixtures/vexor.json']
        elif step=='desktop:migration': command=[self.reference,'-I','tools/android_headless/check_desktop_migration.py','--database',self.db]
        elif name=='inspector_presentation':
            command=[sys.executable,'-m','unittest','tools.android_headless.test_inspection_presentation','tools.android_headless.test_inspection_properties','android.ci.test_inspection_record_identity','android.ci.test_inspection_instrumentation','android.ci.test_inspection_canonical_summary','android.ci.test_inspection_context_summary','android.ci.test_inspection_delivery','android.ci.test_inspection_summary','android.ci.test_inspection_mutations']
        elif name=='inspector_payloads':
            command=[sys.executable,'-I','tools/android_headless/check_inspector_payloads.py','--database',self.db]
        elif name=='inspector_lifecycle':
            command=[sys.executable,'-I','tools/android_headless/check_bridge.py','--database',self.db,'--output',output,'--lifecycle']
        elif name.startswith('inspector_'):
            command=[self.reference if kind=='reference' else sys.executable,'-I','tools/android_reference/check_inspector.py',
                '--kind',kind,'--family',name.removeprefix('inspector_'),'--database',self.db,'--output',output]
            if kind=='reference':command+=['--source',self.source]
        elif kind=='reference':
            command=[self.reference,'-I',f'tools/android_reference/{name}.py','--source',self.source,'--database',self.db,
                '--output',output,'--check',f'tools/android_reference/fixtures/{name.replace("_","-")}.json']
        else:
            script='check.py' if name in ('base','projection','command') else f'check_{name}.py'
            command=[sys.executable,'-I',f'tools/android_headless/{script}','--database',self.db,'--output',output]
            if name in ('projection','command'): command+=['--scenario',name]
            if '--source' in (ROOT/'tools/android_headless'/script).read_text(encoding='utf-8'):
                command+=['--source',self.source]
        self.execute(step,command)
        if step=='desktop:reference':
            self.db=output/'eve.db';self.state['database']=str(self.db)

    def build(self,name):
        sdk=Path(os.environ['ANDROID_HOME']);android=ROOT/'android'
        commands={
            'dependencies':[sys.executable,'prepare-dependencies.py'],
            'engine-assets':[sys.executable,'-I','prepare-engine.py'],
            'apks-lint':[android/'gradlew.bat','--no-daemon','--console=plain',
                         '--max-workers='+str(self.settings['workers']),
                         ':app:assembleDebug',':app:assembleDebugAndroidTest',':app:lintDebug'],
            'signature':[sdk/'build-tools/35.0.0/apksigner.bat','verify','--verbose','--print-certs','app/build/outputs/apk/debug/app-debug.apk'],
            'package':[sys.executable,'ci/verify-apk.py']}
        self.execute('build:'+name,commands[name],cwd=android)
        if name=='package':
            target=self.directory/'apks';target.mkdir(exist_ok=True)
            for apk in (android/'app/build/outputs/apk').rglob('*.apk'):self.artifact_budget.copy(apk,target/apk.name)
            lint=android/'app/build/reports/lint-results-debug.html'
            self.artifact_budget.copy(lint,self.native/lint.name)

    def start_emulator(self, suffix=''):
        from drone_delivery import admit_native
        admit_native(starting=True)
        sdk=Path(os.environ['ANDROID_HOME']);tools=Path(os.environ['PYFA_SDKMANAGER']).parent
        self.execute('environment:whpx',[sdk/'emulator/emulator.exe','-accel-check'])
        whpx=(self.directory/self.state['attempts'][-1]['log']).read_text(encoding='utf-8')
        assert 'WHPX' in whpx and 'usable' in whpx
        image=sdk/'system-images/android-36/google_apis/x86_64'
        assert image.is_dir(), 'Install system-images;android-36;google_apis;x86_64 first'
        assert suffix in ('','-c04')
        avds=self.directory/'avd'
        name='pyfa-local-'+self.directory.name.replace('.','-')
        restart=len(self.state.get('native_restarts',[]))
        if not suffix and restart:
            avds=self.directory/('avd-r'+str(restart))
            name+='-r'+str(restart)
        if suffix:
            from drone_delivery import avd_identity
            avds,name=avd_identity(self.directory,len(self.state.get('native_restarts',[])))
        self.artifact_budget.check(reserve=0 if avds.exists() else self.policy['android_runtime']['new_avd_disk_forecast_bytes'])
        register_runtime(self.state,self.directory,avds,name)
        save(self.file,self.state)
        avds.mkdir(exist_ok=True)
        os.environ['ANDROID_AVD_HOME']=str(avds)
        self.state['avd_name']=name
        if not (avds/f'{name}.ini').exists():
            with (self.directory/f'avd-create-{len(self.state["attempts"]):03}.log').open('wb') as log:
                self.artifact_budget.run([str(tools/'avdmanager.bat'),'create','avd','--name',name,'--package',
                    'system-images;android-36;google_apis;x86_64','--device','pixel_2'],input=b'no\n',stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        # Bind only this disposable emulator. Other emulators and phones stay untouched.
        devices=subprocess.check_output(['adb','devices'],text=True)
        used={line.split()[0] for line in devices.splitlines()[1:] if line.strip()}
        port=next(p for p in range(5560,5680,2) if f'emulator-{p}' not in used)
        self.serial=f'emulator-{port}';os.environ['ANDROID_SERIAL']=self.serial
        self.state['emulator_serial']=self.serial
        self.state['emulator_version']=(sdk/'emulator/source.properties').read_text(encoding='utf-8')
        self.state['image_version']=(image/'source.properties').read_text(encoding='utf-8')
        save(self.file,self.state)
        self.emulator_log=(self.directory/'emulator.log').open('ab')
        self.emulator=subprocess.Popen([str(sdk/'emulator/emulator.exe'),'-avd',name,'-port',str(port),
            '-accel','on','-no-window','-gpu','swiftshader_indirect','-no-snapshot','-noaudio',
            '-no-boot-anim','-camera-back','none', '-memory',str(self.policy['android_runtime']['emulator_guest_ram_bytes']//(1024**2)),
            '-cores',str(self.settings['workers'])],stdout=self.emulator_log,stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW)
        deadline=time.monotonic()+self.policy['android_runtime']['boot_timeout_seconds']
        checked_at=0
        while time.monotonic()<deadline:
            if time.monotonic()-checked_at>=self.artifact_budget.interval:
                self.artifact_budget.check();checked_at=time.monotonic()
            if self.emulator.poll() is not None: raise RuntimeError('Emulator exited; inspect emulator.log')
            boot=subprocess.run(['adb','-s',self.serial,'shell','getprop','sys.boot_completed'],capture_output=True,text=True,timeout=20)
            if boot.returncode==0 and boot.stdout.strip()=='1':break
            time.sleep(1)
        else:raise RuntimeError('Emulator did not boot within the current policy deadline')
        actual=subprocess.check_output(['adb','-s',self.serial,'emu','avd','name'],text=True)
        assert actual.splitlines()[0]==name

    def stop_emulator(self):
        if self.emulator is None:return
        try:
            # Console kill exits QEMU without a guest OS shutdown. Flush actual
            # artifact bytes first; otherwise recently written files can reopen
            # as zero bytes even after successful native tests and collection.
            subprocess.run(['adb','-s',self.serial,'shell','sync'],capture_output=True,check=True,timeout=60)
            self.state.setdefault('emulator_flushes',[]).append({'serial':self.serial,'exit_code':0,
                'tested_commit':self.state['commit']})
            save(self.file,self.state)
        finally:
            subprocess.run(['adb','-s',self.serial,'emu','kill'],capture_output=True,timeout=30)
            try:self.emulator.wait(timeout=30)
            except subprocess.TimeoutExpired:self.emulator.terminate();self.emulator.wait(timeout=30)
            self.emulator_log.close();self.emulator=None

    def run(self):
        import msvcrt
        lock=(self.directory/'run.lock').open('a+b');lock.seek(0);lock.write(b'0');lock.flush();lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        print('Evidence: '+str(self.directory),flush=True)
        try:
            self.artifact_budget.check()
            if self.state['mode']=='full':
                from drone_delivery import require_decision
                require_decision()
            if self.args.restart_native:
                assert self.state['status']=='failed' and any(s.startswith('native:') for s in self.state['plan']), 'Restart only a failed native chain'
                # Preserve failed evidence and runtime before starting a fresh AVD.
                # Replaying a failed mutation phase against its partially modified store
                # would violate its original-library precondition.
                archive_bytes=sum(p.stat().st_size for folder in (self.native,self.directory/'apks')
                                  for p in folder.rglob('*') if p.is_file())
                self.artifact_budget.check(reserve=archive_bytes)
                archive=self.directory/('failed-native-'+uuid.uuid4().hex[:8])
                archive.mkdir()
                (archive/'run.json').write_bytes(self.original_run_bytes)
                shutil.copytree(self.native,archive/'native')
                reports=ROOT/'android/app/build/outputs/androidTest-results/connected'
                if reports.exists():shutil.copytree(reports,archive/'junit')
                for name in ('screenshots-reviewed-partial.json','screenshots-reviewed.json'):
                    if (self.directory/name).exists():shutil.copyfile(self.directory/name,archive/name)
                retained=list((self.directory/'apks').glob('*.apk'))
                assert len(retained)==2, 'Both previously tested APKs are required'
                charge_fix=self.state.get('charge_keyboard_host_reuse')
                profile_fix=charge_fix or self.state.get('output_profile_host_reuse')
                if profile_fix:
                    # The app or test package changed: preserve old proof, rebuild
                    # every package gate and run every native gate on a fresh store.
                    shutil.copytree(self.directory/'apks',archive/'apks')
                    profile_fix.update(archive=archive.name,
                        archived_apk_hashes={p.name:sha(p) for p in retained},
                        archived_native_hashes={str(p.relative_to(archive/'native')):sha(p) for p in (archive/'native').rglob('*') if p.is_file()})
                    if charge_fix:
                        from charge_keyboard_retry import validate_retained
                    else:
                        from output_profile_retry import validate_retained
                    validate_retained(ROOT,self.directory,profile_fix)
                    assert self.state['completed']==profile_fix['retained_gates']
                    if charge_fix:
                        from charge_keyboard_retry import reuse_build
                        reuse_build(self,charge_fix)
                else:
                    for apk in retained:
                        current=list((ROOT/'android/app/build/outputs/apk').rglob(apk.name))
                        assert len(current)==1 and sha(apk)==sha(current[0]), 'Reused APK differs from the tested copy'
                prior_runtime='avd-r'+str(len(self.state.get('native_restarts',[]))) if self.state.get('native_restarts') else 'avd'
                if (self.directory/prior_runtime).exists():
                    # Explicit restart triages the failure but preserves its runtime.
                    # start_emulator selects a fresh avd-rN for the next attempt.
                    self.state.setdefault('retained_failed_avds',[]).append(prior_runtime)
                from summary_repair import clear_native_results
                clear_native_results(self.native)
                self.state.setdefault('native_restarts',[]).append({'archive':archive.name,'reason':'Failed native chain; fresh disposable store required','commit':self.state['commit']})
                self.state['completed']=[s for s in self.state['completed'] if not s.startswith('native:')]
            self.state['status']='running';save(self.file,self.state)
            targeting_fix=self.state.get('targeting_phase_reuse')
            if targeting_fix and not targeting_fix['prepared']:
                from targeting_phase_retry import prepare
                prepare(self,targeting_fix);save(self.file,self.state)
            cargo_search_fix=self.state.get('cargo_search_reuse')
            if cargo_search_fix and not cargo_search_fix['prepared']:
                from cargo_search_retry import prepare
                prepare(self,cargo_search_fix);save(self.file,self.state)
            tank_fix=self.state.get('tank_history_reuse')
            if tank_fix and not tank_fix['prepared']:
                from tank_history_retry import prepare
                prepare(self,tank_fix);save(self.file,self.state)
            capacitor_fix=self.state.get('capacitor_runner_reuse')
            if capacitor_fix and not capacitor_fix['prepared']:
                from capacitor_runner_retry import prepare
                prepare(self,capacitor_fix);save(self.file,self.state)
            resource_fixes=self.state.get('resource_test_reuse',[])
            if resource_fixes and not resource_fixes[-1]['prepared']:
                from resource_test_retry import prepare
                prepare(self,resource_fixes[-1]);save(self.file,self.state)
            projection_fixes=self.state.get('projection_report_reuse',[])
            if projection_fixes and not projection_fixes[-1]['validated']:
                from projection_history_retry import revalidate
                revalidate(self,projection_fixes[-1]);save(self.file,self.state)
            stale_fixes=self.state.get('stale_history_reuse',[])
            if stale_fixes and not stale_fixes[-1]['prepared']:
                from stale_history_retry import prepare
                prepare(self,stale_fixes[-1]);save(self.file,self.state)
            cargo_fixes=self.state.get('cargo_observer_reuse',[])
            if cargo_fixes and not cargo_fixes[-1]['prepared']:
                from cargo_history_retry import prepare
                prepare(self,cargo_fixes[-1]);save(self.file,self.state)
            settings_fixes=self.state.get('settings_fix_reuse',[])
            if settings_fixes and not settings_fixes[-1]['validated']:
                proof=settings_fixes[-1]
                archive=self.directory/'settings-fix-original';archive.mkdir(exist_ok=False)
                (archive/'run.json').write_bytes(self.original_run_bytes)
                names=[f'mutation-history-0-{phase}-{suffix}' for phase in ('prepare','restored') for suffix in ('native.json','instrumentation.txt')]
                proof['retained_hashes']={name:sha(self.native/name) for name in names}
                proof['apk_hashes']={p.name:sha(p) for p in (self.directory/'apks').glob('*.apk')}
                assert len(proof['apk_hashes'])==2
                for name in names:shutil.copyfile(self.native/name,archive/name)
                self.execute('native:mutation-history-0-restored',[sys.executable,ROOT/'android/ci/revalidate-mutation-history.py'])
                self.state['attempts'][-1]['retained_native_execution_commit']=proof['from_commit']
                assert all(sha(self.native/name)==value for name,value in proof['retained_hashes'].items())
                self.state['completed'].append('native:mutation-history-0-restored')
                proof['archive']=archive.name;proof['validated']=True;save(self.file,self.state)
            fixes=self.state.get('runner_fix_reuse',[])
            if fixes and not fixes[-1]['prepared']:
                proof=fixes[-1]
                archive=self.directory/'pending-runner-fix-original'
                archive.mkdir(exist_ok=False)
                (archive/'run.json').write_bytes(self.original_run_bytes)
                shutil.copytree(self.directory/'apks',archive/'apks')
                shutil.copyfile(self.native/'apk-contents.json',archive/'apk-contents.json')
                proof['archive']=archive.name
                proof['app_sha256']=sha(archive/'apks/app-debug.apk')
                proof['old_test_apk_sha256']=sha(archive/'apks/app-debug-androidTest.apk')
                self.build('apks-lint')
                assert sha(ROOT/'android/app/build/outputs/apk/debug/app-debug.apk')==proof['app_sha256'], 'Target APK changed; earlier native proof is invalid'
                self.build('package')
                from zipfile import ZipFile
                old_test=archive/'apks/app-debug-androidTest.apk'
                new_test=self.directory/'apks/app-debug-androidTest.apk'
                with ZipFile(old_test) as old, ZipFile(new_test) as new:
                    assets={name for name in old.namelist() if name.startswith('assets/')}
                    assert assets=={name for name in new.namelist() if name.startswith('assets/')}
                    assert all(old.read(name)==new.read(name) for name in assets), 'Packaged fixtures changed'
                proof['new_test_apk_sha256']=sha(new_test);proof['prepared']=True
                save(self.file,self.state)
            for step in self.state['plan']:
                if step in self.state['completed']:continue
                if (self.directory/'PAUSE').exists():
                    self.state['status']='paused';save(self.file,self.state);return
                assert self.state['commit']==git('rev-parse','HEAD') and not git('status','--porcelain'), 'Test inputs changed during execution'
                if step.startswith(('desktop:','reference:','headless:')):self.host(step)
                elif step.startswith('build:'):self.build(step.split(':')[1])
                elif step==DRONE_DECISION_GATE:
                    self.execute(step,[sys.executable,'-I','-B',ROOT/'android/ci/drone_delivery.py','--accept-conservation',self.directory],timeout=90)
                elif step==DRONE_NATIVE_GATE:
                    from drone_delivery import run_native
                    run_native(self)
                else:
                    if self.emulator is None:self.start_emulator(suffix='-c04' if step in ('native:projected_module_charges','native:shield_regeneration_graph','native:remote_repair_graph') else '')
                    if targeting_fix and not targeting_fix['installed']:
                        from targeting_phase_retry import install
                        install(self,targeting_fix);save(self.file,self.state)
                    if cargo_search_fix and not cargo_search_fix['installed']:
                        from cargo_search_retry import install
                        install(self,cargo_search_fix);save(self.file,self.state)
                    if cargo_search_fix and cargo_search_fix.get('artifact_flush_retry') and not cargo_search_fix['artifact_flush_retry']['installed']:
                        from cargo_search_retry import install_artifact_flush_retry
                        install_artifact_flush_retry(self,cargo_search_fix);save(self.file,self.state)
                    if tank_fix and not tank_fix['installed']:
                        from tank_history_retry import install
                        install(self,tank_fix);save(self.file,self.state)
                    if capacitor_fix and not capacitor_fix['installed']:
                        from capacitor_runner_retry import install
                        install(self,capacitor_fix);save(self.file,self.state)
                    if resource_fixes and not resource_fixes[-1]['installed']:
                        from resource_test_retry import install
                        install(self,resource_fixes[-1]);save(self.file,self.state)
                    if stale_fixes and not stale_fixes[-1].get('installed'):
                        from stale_history_retry import install
                        install(self,stale_fixes[-1]);save(self.file,self.state)
                    if cargo_fixes and not cargo_fixes[-1].get('installed'):
                        from cargo_history_retry import install
                        install(self,cargo_fixes[-1]);save(self.file,self.state)
                    if fixes and not fixes[-1].get('installed'):
                        proof=fixes[-1]
                        def graph_hash():
                            return subprocess.check_output(['adb','-s',self.serial,'shell','run-as','io.github.sussic.pyfa.dev',
                                'sha256sum','no_backup/fits/graph.sqlite3'],text=True).split()[0]
                        prior_graph=graph_hash()
                        self.execute('environment:pending-test-runner-update',['adb','-s',self.serial,'install','-r','-t',self.directory/'apks/app-debug-androidTest.apk'])
                        assert graph_hash()==prior_graph, 'Test runner installation changed the retained fit store'
                        proof['retained_graph_sha256']=prior_graph;proof['installed']=True;save(self.file,self.state)
                    from history_progress import HistoryProgress
                    diagnostics=HistoryProgress(self.directory/'diagnostics'/f'{step.replace(":", "-")}-{len(self.state["attempts"]):03}',self.serial) if step=='native:check-history.py' or step.startswith('native:mutation-history-') else nullcontext()
                    with diagnostics:
                        if step.startswith('native:inspection-'):
                            phase=step.removeprefix('native:inspection-')
                            script='inspection_summary.py' if phase=='summary' else 'inspection_native.py'
                            arguments=[] if phase=='summary' else ['--phase',phase]
                            self.execute(step,[sys.executable,ROOT/'android/ci'/script,*arguments],cwd=ROOT/'android',timeout=None if phase=='summary' else 900)
                        else:
                            arguments=['--expected-avd',self.state['avd_name']] if step in ('native:projected_module_charges','native:shield_regeneration_graph','native:remote_repair_graph') else []
                            self.execute(step,[sys.executable,ROOT/'android/ci/native_suite.py','--step',step.split(':',1)[1],*arguments],cwd=ROOT/'android',timeout=1200 if arguments else None)
                self.state['completed'].append(step);save(self.file,self.state)
            self.state['status']='passed'
            self.state['completed_utc']=datetime.now(timezone.utc).isoformat()
            reports=ROOT/'android/app/build/outputs/androidTest-results/connected'
            if any(s.startswith('native:') for s in self.state['plan']) and reports.exists():shutil.copytree(reports,self.native/'junit',dirs_exist_ok=True)
            self.stop_emulator()
            for row in self.state['attempts']: row.setdefault('tested_commit',self.state['commit'])
            save(self.file,self.state)
            from drone_delivery import is_emulator_data
            files={str(p.relative_to(self.directory)):{'sha256':sha(p),'bytes':p.stat().st_size}
                for p in self.directory.rglob('*') if p.is_file() and not is_emulator_data(self.directory,p) and p.name not in ('run.lock','files.json')}
            save(self.directory/'files.json',files)
            print('PASS local '+self.state['mode']+'; screenshot review is still a separate required step',flush=True)
        except AdmissionDeferred as error:
            self.state['status']='paused'
            self.state['validation_state']='queued'
            self.state['resource_deferred_reason']=str(error)
            save(self.file,self.state)
            raise
        except BaseException:
            self.state['status']='failed';save(self.file,self.state);raise
        finally:
            if self.state['status']!='passed':
                for row in self.state['attempts']: row.setdefault('tested_commit',self.state['commit'])
                save(self.file,self.state)
            try:
                self.stop_emulator()
                # Keep the run lock through verified cleanup and its receipt.
                if self.state['status']=='passed':
                    cleanup_verified_runtime(self.directory,stopped=self.emulator is None)
            finally:
                lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1);lock.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','resume','pause','plan'])
    parser.add_argument('--mode',choices=['full','desktop','build','native'],default='full')
    parser.add_argument('--gate',choices=FAMILIES+['inspector_'+name for name in INSPECTOR]+['inspector_lifecycle','projected_module_charges','shield_regeneration_graph','remote_repair_graph'])
    parser.add_argument('--run');parser.add_argument('--source');parser.add_argument('--reference-python')
    parser.add_argument('--artifact-root',action='append',default=[],
                        help='Additional artifact directory to count, never an eviction target')
    parser.add_argument('--execution-host',choices=['initia','msi'],
                        help='Verified physical executor; defaults to CODEX_EXECUTION_HOST or machine identity')
    parser.add_argument('--artifact-budget-gib',type=int,
                        help=argparse.SUPPRESS)
    parser.add_argument('--adopt-launcher-fix',action='store_true',help='Reuse unchanged host/build gates before any native gate passed, after a verified launcher-only fix')
    parser.add_argument('--restart-native',action='store_true',help='Archive failed evidence and restart the complete native chain with a fresh disposable AVD; reuse only unchanged host/build gates')
    parser.add_argument('--adopt-pending-runner-fix',action='store_true',help='Adopt only the exact missing B09.2 storage flag after its first phase failed; preserve earlier proof and rebuild the test APK')
    parser.add_argument('--adopt-pending-settings-fix',action='store_true',help='Revalidate retained successful group 0 instrumentation after the exact whole-double settings-report correction')
    parser.add_argument('--adopt-cargo-observer-fix',action='store_true',help='Rebuild the exact cargo-sort observer correction, recover the proven synthetic baseline and rerun all B09.2 phases')
    parser.add_argument('--cargo-recovery',help='Validated partial/restored store and receipt directory for the exact B09.2 failure')
    parser.add_argument('--adopt-stale-history-fix',action='store_true',help='Rebuild the exact final-group enum comparison repair; retain groups 0–2 and retry only group 3')
    parser.add_argument('--stale-recovery',help='Validated partial/restored group 3 store and receipt directory')
    parser.add_argument('--adopt-projection-report-fix',action='store_true',help='Revalidate retained successful group 3 preparation after exact decimal projection-range comparison repair; no instrumentation rerun')
    parser.add_argument('--adopt-resource-test-fix',action='store_true',help='Adopt the exact C01.1 copy-ID test repair and validated two-fit recovery; retain all unchanged proof')
    parser.add_argument('--adopt-capacitor-runner-fix',action='store_true',help='Adopt only the exact missing C01.2 persistent runner flag; retain all prior gates and app APK')
    parser.add_argument('--adopt-tank-history-fix',action='store_true',help='Adopt only the exact C01.3.2 revision wait repair; recover its validated synthetic baseline and rerun affected gates')
    args=parser.parse_args()
    if args.artifact_budget_gib is not None:
        parser.error('--artifact-budget-gib is retired; edit and validate execution-policy.json')
    if args.action=='plan':print('\n'.join(plan(args.mode,args.gate)));return
    assert os.name=='nt', 'This explicit launcher owns Windows WHPX AVDs'
    if args.action=='pause':
        assert args.run
        (Path(args.run)/'PAUSE').write_text('Pause at the next completed gate\n',encoding='utf-8');return
    assert args.action!='resume' or args.run
    try:
        runner=Run(args)
        if args.action=='resume':(runner.directory/'PAUSE').unlink(missing_ok=True)
        with heavy_lease(runner.policy,runner.settings):
            runner.execution_started=time.monotonic()
            runner.artifact_budget.resource_check=runner.check_running_resources
            runner.admit_command()
            os.environ['DOTNET_PROCESSOR_COUNT']=str(runner.settings['workers'])
            os.environ['OMP_NUM_THREADS']=str(runner.settings['workers'])
            runner.run()
    except AdmissionDeferred as error:
        if 'runner' in locals():
            runner.state['validation_state']='queued'
            runner.state['resource_deferred_reason']=str(error)
            save(runner.file,runner.state)
        print('DEFERRED: '+str(error),file=sys.stderr)
        return 75


if __name__=='__main__':sys.exit(main())
