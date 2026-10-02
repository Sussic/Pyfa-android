"""Run only the selected C01.2 native phase; retain every raw result and PNG."""
import argparse
import json
import re
import subprocess
from evidence_paths import evidence_dir

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--phase', choices=('prepare','restored'), required=True)
phase = parser.parse_args().phase
evidence = evidence_dir(); package = 'io.github.sussic.pyfa.dev'


def adb(*args, timeout=30, binary=False):
    result = subprocess.run(['adb',*args],capture_output=True,text=not binary,timeout=timeout)
    result.check_returncode(); return result.stdout


assert adb('shell','getprop','ro.kernel.qemu').strip() == '1'
assert adb('shell','settings','get','global','airplane_mode_on').strip() == '1'
adb('shell','am','force-stop',package)
path = f'/sdcard/Download/pyfa-c012-{phase}.json'
names = {'prepare':['prepare-battery-detail','prepare-0','prepare-4','prepare-10'], 'restored':['restored']}[phase]
adb('shell','rm','-f',path,*(f'/sdcard/Download/pyfa-c012-{name}.png' for name in names))
command = ['shell','am','instrument','-w','-r','-e','class',
           'io.github.sussic.pyfa.CapacitorTest']
command += ['-e','c012_phase',phase]
output = adb(*command,f'{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner',timeout=900)
(evidence/f'capacitor-{phase}-instrumentation.txt').write_text(output,encoding='utf-8')
for name in names:
    remote = f'/sdcard/Download/pyfa-c012-{name}.png'
    if subprocess.run(['adb','shell','test','-f',remote],timeout=30).returncode == 0:
        data = adb('exec-out','cat',remote,binary=True)
        assert data.startswith(b'\x89PNG\r\n\x1a\n'); (evidence/f'capacitor-{name}.png').write_bytes(data)
assert re.search(r'^OK \(1 test\)\s*$',output,re.M), output[-6000:]
assert 'INSTRUMENTATION_CODE: -1' in output and not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=',output)
raw = adb('exec-out','cat',path,binary=True)
report = json.loads(raw); assert report['phase'] == phase and report['task'] == 'C01.2'
(evidence/f'capacitor-{phase}-native.json').write_bytes(raw)
assert all((evidence/f'capacitor-{name}.png').is_file() for name in names)
