"""Run one C03.1 phase and retain hash-verified raw results and screenshots."""
import argparse
import hashlib
import json
import re
import subprocess
from evidence_paths import evidence_dir

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase',choices=('prepare','restored'),required=True)
phase=parser.parse_args().phase
evidence=evidence_dir();package='io.github.sussic.pyfa.dev'


def adb(*args,timeout=30):
    result=subprocess.run(['adb',*map(str,args)],capture_output=True,timeout=timeout)
    result.check_returncode();return result.stdout


def pull(remote,target):
    adb('shell','sync')
    before=adb('shell','sha256sum',remote).split()[0].decode('ascii')
    size=int(adb('shell','stat','-c','%s',remote).strip())
    result=subprocess.run(['adb','pull',remote,str(target)],capture_output=True,timeout=120)
    (evidence/(target.name+'.pull.log')).write_bytes(result.stdout+result.stderr);result.check_returncode()
    raw=target.read_bytes()
    assert size>0 and len(raw)==size and hashlib.sha256(raw).hexdigest()==before
    assert adb('shell','sha256sum',remote).split()[0].decode('ascii')==before
    return raw


assert adb('shell','getprop','ro.kernel.qemu').strip()==b'1'
assert adb('shell','settings','get','global','airplane_mode_on').strip()==b'1'
adb('shell','am','force-stop',package)
from pathlib import Path
fixture=json.loads((Path(__file__).resolve().parents[2]/'tools/android_reference/fixtures/targeting.json').read_text(encoding='utf-8'))
names={'prepare':['prepare-targeting','prepare-sensor','prepare-drone_range','prepare-align','prepare-signature','prepare-warp_speed','prepare-cargo','prepare-history',*[f'prepare-hold-{attribute}' for attribute in fixture['available_holds']],'prepare-absent'],'restored':['restored']}[phase]
path=f'/sdcard/Download/pyfa-c031-{phase}.json'
adb('shell','rm','-f',path,*(f'/sdcard/Download/pyfa-c031-{name}.png' for name in names))
command=['adb','shell','am','instrument','-w','-r','-e','class','io.github.sussic.pyfa.TargetingTest',
    '-e','c031_phase',phase,f'{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner']
log=evidence/f'targeting-{phase}-instrumentation.txt'
try:
    result=subprocess.run(command,capture_output=True,timeout=900)
except subprocess.TimeoutExpired as error:
    log.write_bytes((error.stdout or b'')+(error.stderr or b''));raise
log.write_bytes(result.stdout+result.stderr)
output=log.read_text(encoding='utf-8')
for name in names:
    remote=f'/sdcard/Download/pyfa-c031-{name}.png'
    if subprocess.run(['adb','shell','test','-f',remote],timeout=30).returncode==0:
        raw=pull(remote,evidence/f'targeting-{name}.png');assert raw.startswith(b'\x89PNG\r\n\x1a\n')
result.check_returncode()
assert re.search(r'^OK \(1 test\)\s*$',output,re.M),output[-6000:]
assert 'INSTRUMENTATION_CODE: -1' in output and not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=',output)
raw=pull(path,evidence/f'targeting-{phase}-native.json')
report=json.loads(raw);assert report['phase']==phase and report['task']=='C03.1'
assert all((evidence/f'targeting-{name}.png').is_file() for name in names)
