"""Reject incomplete, duplicated or substituted actual Android runner results."""
from pathlib import Path
import re
import unittest

from android.ci.inspection_instrumentation import PHASES, ALL_PHASES, RESTORED_PHASES, CLASS, UI_CLASS, selector, validate, TIMEOUT_SECONDS


def output(phase):
    classname, methods = ALL_PHASES[phase]
    lines = []
    for current, method in enumerate(methods, 1):
        for code in (1, 0):
            lines.extend(f'INSTRUMENTATION_STATUS: {key}={value}' for key, value in
                         dict(id='AndroidJUnitRunner', numtests=len(methods), current=current,
                              **{'class': classname}, test=method).items())
            lines.append(f'INSTRUMENTATION_STATUS_CODE: {code}')
    label = 'test' if len(methods) == 1 else 'tests'
    lines += [f'OK ({len(methods)} {label})', 'INSTRUMENTATION_CODE: -1']
    return '\n'.join(lines)


class InspectionInstrumentationTest(unittest.TestCase):
    def test_every_authored_method_has_exactly_one_phase(self):
        root = Path(__file__).resolve().parents[1] / 'app/src/androidTest/java/io/github/sussic/pyfa'
        for classname in (CLASS, UI_CLASS):
            actual = re.findall(r'@Test\s+fun\s+(\w+)\(', (root / (classname.rsplit('.', 1)[1] + '.kt')).read_text())
            selected = [method for owner, methods in PHASES.values() if owner == classname for method in methods]
            self.assertCountEqual(actual, selected)
            self.assertEqual(len(selected), len(set(selected)))
        self.assertEqual(900, TIMEOUT_SECONDS)

    def test_explicit_selectors_and_complete_runner_events(self):
        for phase, (classname, methods) in ALL_PHASES.items():
            self.assertEqual([classname + '#' + method for method in methods], selector(phase).split(','))
            self.assertEqual(sorted(classname + '.' + method for method in methods), validate(output(phase), phase))

    def test_corrupted_runner_events_are_rejected(self):
        for phase in ALL_PHASES:
            good = output(phase)
            first = ALL_PHASES[phase][1][0]
            corruptions = (
                good.replace('INSTRUMENTATION_STATUS_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: -3', 1),
                good.replace('INSTRUMENTATION_STATUS_CODE: 0', 'INSTRUMENTATION_STATUS_CODE: 1', 1),
                good.replace('test=' + first, 'test=unselectedMethod'),
                good.replace('INSTRUMENTATION_CODE: -1', 'INSTRUMENTATION_CODE: 0'),
                good + '\nINSTRUMENTATION_CODE: -1',
                good + '\nINSTRUMENTATION_STATUS: test=incomplete',
                good.replace('INSTRUMENTATION_STATUS: id=AndroidJUnitRunner',
                             'INSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner', 1),
                good.replace('INSTRUMENTATION_STATUS: current=1', 'INSTRUMENTATION_STATUS: current=999', 1),
                good.replace('OK (', 'INCOMPLETE ('),
                good + '\nFAILURES!!!',
            )
            for bad in corruptions:
                with self.subTest(phase=phase, mutation=bad[-100:]):
                    with self.assertRaises(AssertionError): validate(bad, phase)

    def test_two_restores_reexecute_complete_canonical_method(self):
        self.assertEqual({'canonical-restored1', 'canonical-restored2'}, set(RESTORED_PHASES))
        for phase in RESTORED_PHASES:
            self.assertEqual(CLASS + '#canonicalAttributesCrossNativeWorkerOffline', selector(phase))


if __name__ == '__main__': unittest.main()
