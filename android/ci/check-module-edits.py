"""Run native module editing and real process restart after all prior gates."""
import json
from pathlib import Path
import re
import subprocess
from module_edit_summary import summarize

evidence = Path(__file__).resolve().parents[1] / 'build/evidence'
package = 'io.github.sussic.pyfa.dev'


def adb(*args, timeout=30):
    return subprocess.run(['adb', *args], capture_output=True, text=True, check=True, timeout=timeout).stdout


assert adb('shell', 'settings', 'get', 'global', 'airplane_mode_on').strip() == '1'
prior = {row['pid'] for row in json.loads((evidence / 'empty-hulls-native.json').read_text())}
reports = []
for phase in ('prepare', 'restored'):
    adb('shell', 'am', 'force-stop', package)
    path = f'/sdcard/Download/pyfa-b0422-{phase}.json'
    adb('shell', 'rm', '-f', path)
    output = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class', 'io.github.sussic.pyfa.ModuleEditingTest',
        '-e', 'b0422_phase', phase, f'{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner', timeout=600)
    (evidence / f'module-edits-{phase}-instrumentation.txt').write_text(output, encoding='utf-8')
    names = ('rack', 'resources', 'skills', 'override', 'service', 'recent') if phase == 'prepare' else ('restored',)
    for name in (*names, 'failure'):
        picture = f'/sdcard/Download/pyfa-b0422-{name}.png'
        if subprocess.run(['adb', 'shell', 'test', '-f', picture], timeout=30).returncode == 0:
            png = subprocess.check_output(['adb', 'exec-out', 'cat', picture], timeout=30)
            assert png.startswith(b'\x89PNG\r\n\x1a\n')
            (evidence / f'module-edits-{name}.png').write_bytes(png)
    assert re.search(r'OK \(1 test\)', output), output[-6000:]
    assert 'INSTRUMENTATION_CODE: -1' in output and not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=', output)
    report = json.loads(adb('exec-out', 'cat', path))
    assert report['pid'] not in prior
    prior.add(report['pid'])
    reports.append(report)
    (evidence / f'module-edits-{phase}-native.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for name in names:
        assert (evidence / f'module-edits-{name}.png').is_file()
(evidence / 'module-edits-native.json').write_text(json.dumps(reports, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summarize(reports, json.loads((evidence / 'engine-native.json').read_text())), indent=2))
