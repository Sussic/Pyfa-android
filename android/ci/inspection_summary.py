"""Independently validate every retained inspector native phase and fresh restart.

This report does not establish screenshot review or actual-report corruption
proof. Those remain separate, mandatory publication requirements.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import re
import zlib

from evidence_paths import evidence_dir
from inspection_delivery import PHASES, SCREENSHOTS, artifacts, methods
from inspection_native import Collector, sha
from inspection_canonical_summary import decode, validate_fresh_restores
from inspection_identity_summary import validate as identity_validate
from inspection_links_summary import validate as links_validate
from inspection_context_summary import load_fixture, validate_restores as context_validate
import inspection_mutations as mutations

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tools/android_reference/fixtures'


def png(raw):
    """Require complete nonempty PNG bytes, including every chunk CRC and pixels."""
    assert raw.startswith(b'\x89PNG\r\n\x1a\n')
    assert len(raw) > 8
    offset = 8; chunks = []; compressed = bytearray()
    while offset < len(raw):
        assert offset + 12 <= len(raw)
        size = struct.unpack('>I', raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 8 + size
        assert end + 4 <= len(raw)
        content = raw[offset + 8:end]
        assert zlib.crc32(kind + content) == struct.unpack('>I', raw[end:end + 4])[0]
        chunks.append(kind)
        if kind == b'IHDR':
            assert len(chunks) == 1 and size == 13
            width, height, depth, colour, compression, filtering, interlace = struct.unpack('>IIBBBBB', content)
            assert width > 0 and height > 0 and width * height <= 20_000_000
            assert depth == 8 and colour in (2, 6) and (compression, filtering, interlace) == (0, 0, 0)
        if kind == b'IDAT': compressed.extend(content)
        if kind == b'IEND': assert size == 0 and end + 4 == len(raw)
        offset = end + 4
    assert chunks and chunks[0] == b'IHDR' and chunks[-1] == b'IEND' and chunks.count(b'IHDR') == chunks.count(b'IEND') == 1
    decoder = zlib.decompressobj(); pixels = decoder.decompress(bytes(compressed), height * (width * (3 if colour == 2 else 4) + 1) + 1)
    assert decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
    stride = width * (3 if colour == 2 else 4) + 1
    assert len(pixels) == height * stride and all(pixels[row * stride] <= 4 for row in range(height))
    return dict(width=width, height=height, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def validate(directory):
    directory = Path(directory).resolve()
    assert directory.name == 'native'
    # Pure retained-file checks must also work during publication after shutdown.
    collector = object.__new__(Collector); collector.directory = directory
    receipts = {}
    for phase in PHASES:
        receipt = decode((directory / f'inspection-{phase}-collection.json').read_bytes())
        identity = receipt['device']
        assert set(identity) == {'serial', 'avd', 'api', 'qemu', 'airplane_mode'}
        assert re.fullmatch(r'emulator-\d+', identity['serial'])
        assert identity['avd'] == 'pyfa-local-' + directory.parent.name
        assert type(identity['api']) is int and identity['api'] == 36 and identity['qemu'] is True and identity['airplane_mode'] is True
        if receipts: assert identity == next(iter(receipts.values()))['device']
        collector.retained(receipt, phase, identity)
        receipts[phase] = receipt
    def path(phase, index): return directory / receipts[phase]['artifacts'][index]['file']
    canonical = ('canonical', 'canonical-restored1', 'canonical-restored2')
    original_bytes = (FIXTURES / 'inspector-attributes.json').read_bytes()
    original = decode(original_bytes)
    canonical_result = validate_fresh_restores([decode(path(phase, 0).read_bytes()) for phase in canonical],
                                             [path(phase, 1).read_bytes() for phase in canonical], original)
    identity_result = identity_validate([decode(path('identity-' + phase, 0).read_bytes())
                                         for phase in ('prepare', 'restored1', 'restored2')], original, original_bytes)
    fixture = load_fixture(); context_results = []
    corruption_results = [mutations.canonical(decode(path(phase, 0).read_bytes()), path(phase, 1).read_bytes(), original)
                          for phase in canonical]
    corruption_results.append(mutations.identity([decode(path('identity-' + phase, 0).read_bytes())
                                                 for phase in ('prepare', 'restored1', 'restored2')], original, original_bytes))
    for part in range(5):
        phases = (f'contexts{part}', f'contexts{part}-restored1', f'contexts{part}-restored2')
        context_results.append(context_validate([decode(path(phase, 0).read_bytes()) for phase in phases],
                                               [path(phase, 1) for phase in phases], fixture))
        corruption_results.extend(mutations.context(decode(path(phase, 0).read_bytes()), path(phase, 1), fixture)
                                  for phase in phases)
    linked_results = []
    for index, kind in enumerate(('projection', 'command')):
        reference_bytes = (FIXTURES / f'inspector-{kind}.json').read_bytes()
        linked_results.append(links_validate(decode(path('linked', index).read_bytes()),
                                            decode(reference_bytes), reference_bytes, kind))
        corruption_results.append(mutations.linked(decode(path('linked', index).read_bytes()),
                                                   decode(reference_bytes), reference_bytes, kind))
    screenshots = []
    for remote, row in zip(artifacts('ui'), receipts['ui']['artifacts']):
        assert Path(remote).name in SCREENSHOTS
        screenshots.append(dict(name=row['file'], **png((directory / row['file']).read_bytes())))
    inputs = {}
    for phase, receipt in receipts.items():
        names = [f'inspection-{phase}-collection.json', receipt['runner_log'], *(row['file'] for row in receipt['artifacts'])]
        for name in names: inputs[name] = dict(bytes=(directory / name).stat().st_size, sha256=sha(directory / name))
    assert len(corruption_results) == 21 and sum(row['count'] for row in corruption_results) == 549
    return dict(schema=1, task='C03.2', independent_native_validation=True, phases=list(PHASES),
                native_test_executions=sum(len(methods(phase)[1]) for phase in PHASES),
                canonical=canonical_result, identity=identity_result, contexts=context_results, linked=linked_results,
                screenshots=screenshots, inputs=inputs, actual_report_corruptions=True,
                corruption_proof=dict(count=sum(row['count'] for row in corruption_results), groups=corruption_results),
                screenshot_review=False, full_delivery=False)


def main():
    directory = evidence_dir(); result = validate(directory)
    result['tested_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    result['execution'] = dict(kind='local_windows', local_run_id=directory.parent.name)
    (directory / 'inspection-summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('PASS complete inspector native payload validation and actual-report corruptions; screenshot review remains mandatory')


if __name__ == '__main__': main()
