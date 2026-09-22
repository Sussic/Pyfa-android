"""Run B04.1 after all existing native phases, retaining the same offline saved fits."""
import json
from pathlib import Path
import re
import subprocess
from market_summary import summarize

evidence = Path(__file__).resolve().parents[1] / 'build/evidence'
package = 'io.github.sussic.pyfa.dev'
def adb(*args, timeout=30):
    return subprocess.run(['adb', *args], capture_output=True, text=True, check=True, timeout=timeout).stdout

assert adb('shell', 'settings', 'get', 'global', 'airplane_mode_on').strip() == '1'
adb('shell', 'am', 'force-stop', package)
adb('shell', 'rm', '-f', '/sdcard/Download/pyfa-b041.json')
output = adb('shell', 'am', 'instrument', '-w', '-r', '-e', 'class', 'io.github.sussic.pyfa.EquipmentBrowserTest',
    '-e', 'b041_phase', 'browse', f'{package}.test/io.github.sussic.pyfa.DiagnosticTestRunner', timeout=300)
(evidence / 'market-instrumentation.txt').write_text(output, encoding='utf-8')
for name in ('root', 'search', 'group', 'meta', 'empty', 'failure'):
    path = f'/sdcard/Download/pyfa-b041-{name}.png'
    if subprocess.run(['adb', 'shell', 'test', '-f', path], timeout=30).returncode == 0:
        raw = subprocess.check_output(['adb', 'exec-out', 'cat', path], timeout=30)
        assert raw.startswith(b'\x89PNG\r\n\x1a\n')
        (evidence / f'market-{name}.png').write_bytes(raw)
assert re.search(r'OK \(1 test\)', output), output[-6000:]
assert 'INSTRUMENTATION_CODE: -1' in output and not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=', output)
report = json.loads(adb('exec-out', 'cat', '/sdcard/Download/pyfa-b041.json'))
assert report['pid'] not in {row['pid'] for row in json.loads((evidence / 'navigation-native.json').read_text())}
(evidence / 'market-native.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
for name in ('root', 'search', 'group', 'meta', 'empty'):
    assert (evidence / f'market-{name}.png').is_file()
print(json.dumps(summarize(report, json.loads((evidence / 'engine-native.json').read_text())), indent=2))
