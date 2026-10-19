"""PNG completeness guards; temporary pixels never establish native UI proof."""
import struct
import unittest
import zlib
from copy import deepcopy
from android.ci.inspection_summary import png
from android.ci.report_local import inspector_summary_matches


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def image(pixels=b'\x00\x01\x02\x03\xff', width=1, height=1):
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


class InspectorSummaryTest(unittest.TestCase):
    def test_publication_rejects_absent_and_falsified_corruption_proof(self):
        checked = dict(phases=[], native_test_executions=0, canonical=[], identity={}, contexts=[],
                       linked=[], screenshots=[], inputs={}, actual_report_corruptions=False)
        report = dict(checked, tested_commit='synthetic-guard', independent_native_validation=True,
                      execution=dict(kind='local_windows', local_run_id='synthetic-run'))
        with self.assertRaisesRegex(AssertionError, 'corruption proof'):
            inspector_summary_matches(report, checked, 'synthetic-guard', 'synthetic-run')
        fabricated = deepcopy(report); fabricated['actual_report_corruptions'] = True
        with self.assertRaisesRegex(AssertionError, 'Changed inspector proof'):
            inspector_summary_matches(fabricated, checked, 'synthetic-guard', 'synthetic-run')

    def test_complete_nonempty_pixels_and_every_chunk_crc_required(self):
        valid = image(); result = png(valid)
        self.assertEqual((1, 1, len(valid)), (result['width'], result['height'], result['bytes']))
        for invalid in (b'', valid[:8], valid[:-1], valid + b'extra', valid[:-12], image(width=0),
                        image(height=2), image(pixels=b''), image(pixels=b'\x05\x01\x02\x03\xff'),
                        valid[:29] + bytes([valid[29] ^ 1]) + valid[30:]):
            with self.subTest(raw=invalid[:30]), self.assertRaises(AssertionError): png(invalid)


if __name__ == '__main__': unittest.main()
