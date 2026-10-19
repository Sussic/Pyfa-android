"""Run and compare each C04 independent reference with the pinned fixture."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from drone_delivery import ROOT,REFERENCE_FILES,sha
sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import compare


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--family',choices=REFERENCE_FILES,required=True)
    for name in ('source','database','output'): p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args(); out=a.output.resolve(); assert not out.exists() and not out.is_relative_to(ROOT)
    out.mkdir(parents=True)
    producer={'drone_core':'drone_edits.py','drone_details':'drone_details.py','drone_acceptance':'drone_acceptance.py','drone_conservation':'drone_conservation.py'}[a.family]
    subprocess.run([sys.executable,'-I','-B',str(ROOT/'tools/android_reference'/producer),
                    '--source',str(a.source),'--database',str(a.database),'--output',str(out/'actual.json')],check=True,timeout=180)
    fixture=ROOT/'tools/android_reference/fixtures'/REFERENCE_FILES[a.family]
    compare(json.loads(fixture.read_text(encoding='utf-8')),json.loads((out/'actual.json').read_text(encoding='utf-8')))
    (out/'evidence.json').write_text(json.dumps(dict(independent_reference=True,fixture_sha256=sha(fixture),
        actual_sha256=sha(out/'actual.json'),producer=producer),indent=2)+'\n',encoding='utf-8')


if __name__=='__main__': main()
