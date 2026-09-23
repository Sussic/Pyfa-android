"""Run native variation editing and actual process restart after prior gates."""
import json
from pathlib import Path
import re
import subprocess
from variation_edit_summary import summarize

evidence = Path(__file__).resolve().parents[1] / 'build/evidence'
package = 'io.github.sussic.pyfa.dev'


def adb(*args, timeout=30):
    return subprocess.run(['adb', *args], capture_output=True, text=True, check=True, timeout=timeout).stdout


assert adb('shell', 'settings', 'get', 'global', 'airplane_mode_on').strip() == '1'
prior = {row['pid'] for row in json.loads((evidence / 'charge-edits-native.json').read_text())}
reports = []
for phase in ('prepare', 'restored'):
    adb('shell', 'am', 'force-stop', package)
    path = f'/sdcard/Download/pyfa-b04232-{phase}.json'
    adb('shell', 'rm', '-f', path)
    output = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class', 'io.github.sussic.pyfa.VariationEditingTest',
        '-e', 'b04232_phase', phase, f'{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner', timeout=900)
    (evidence / f'variation-edits-{phase}-instrumentation.txt').write_text(output, encoding='utf-8')
    names = ('module', 'unloaded', 'drone-picker', 'drone', 'implant', 'disabled', 'empty') if phase == 'prepare' else ('restored',)
    for name in (*names, 'failure'):
        picture = f'/sdcard/Download/pyfa-b04232-{name}.png'
        if subprocess.run(['adb', 'shell', 'test', '-f', picture], timeout=30).returncode == 0:
            png = subprocess.check_output(['adb', 'exec-out', 'cat', picture], timeout=30)
            assert png.startswith(b'\x89PNG\r\n\x1a\n')
            (evidence / f'variation-edits-{name}.png').write_bytes(png)
    assert re.search(r'OK \(1 test\)', output), output[-6000:]
    assert 'INSTRUMENTATION_CODE: -1' in output and not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=', output)
    report = json.loads(adb('exec-out', 'cat', path))
    assert report['pid'] not in prior
    prior.add(report['pid']); reports.append(report)
    (evidence / f'variation-edits-{phase}-native.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for name in names: assert (evidence / f'variation-edits-{name}.png').is_file()
(evidence / 'variation-edits-native.json').write_text(json.dumps(reports, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summarize(reports, json.loads((evidence / 'engine-native.json').read_text())), indent=2))
