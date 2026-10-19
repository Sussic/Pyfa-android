"""Host-only acceptance of the native result parser, without invoking adb."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('drone_runner', Path(__file__).with_name('check-drones.py'))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def output(names):
    parts = []
    for current, name in enumerate(names, 1):
        cls, method = name.split('#')
        for code in (1, 0):
            parts.extend([f'INSTRUMENTATION_STATUS: class={cls}', f'INSTRUMENTATION_STATUS: test={method}',
                          f'INSTRUMENTATION_STATUS: numtests={len(names)}', f'INSTRUMENTATION_STATUS: current={current}',
                          f'INSTRUMENTATION_STATUS_CODE: {code}'])
    return '\n'.join(parts + [f'OK ({len(names)} tests)', 'INSTRUMENTATION_CODE: -1'])


class NativeResultTests(unittest.TestCase):
    def test_exact_one_and_three_test_completions(self):
        for names in (['Drone#a'], ['Drone#a', 'Drone#b', 'Drone#c']):
            runner.passed(output(names), set(names))

    def test_incomplete_duplicate_wrong_and_failed_events_rejected(self):
        text = output(['Drone#a'])
        for malformed in (text.replace('STATUS_CODE: 0', 'STATUS_CODE: -2'),
                          text.replace('STATUS_CODE: 0', 'STATUS_CODE: 1'),
                          text.replace('test=a', 'test=b'),
                          text.replace('CODE: -1', 'CODE: 0'),
                          text.replace('OK (1 tests)', 'OK (0 tests)'),
                          text + '\nFAILURES!!!', text + '\nINSTRUMENTATION_CODE: -1',
                          output(['Drone#a', 'Drone#a'])):
            with self.subTest(output=malformed), self.assertRaises(AssertionError):
                runner.passed(malformed, {'Drone#a'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
