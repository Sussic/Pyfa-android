"""Recover only read-only evidence transport; incomplete evidence still fails."""
import os,subprocess,unittest
from unittest.mock import patch
import native_suite as native

class ArtifactReadTest(unittest.TestCase):
    def read(self,results,identities=('pyfa-local-test\nOK','1','36','1'),binary=True):
        with patch.object(native.os,'name','nt'),patch.dict(os.environ,{'ANDROID_SERIAL':'emulator-5560','PYFA_LOCAL_RUN_ID':'test'}),patch.object(native.subprocess,'run',side_effect=results) as run,patch.object(native.subprocess,'check_output',side_effect=identities):
            value=native.adb('exec-out','cat','/sdcard/Download/report.json',binary=binary)
            return value,run.call_args_list
    def result(self,code=0,out=b'{}',err=b''):
        return subprocess.CompletedProcess(['adb'],code,out,err)
    def test_success_without_retry(self):
        value,calls=self.read([self.result()]);self.assertEqual(b'{}',value);self.assertEqual(1,len(calls))
    def test_exact_offline_error_reconnects_owned_emulator_once(self):
        value,calls=self.read([self.result(1,err=b'error: device offline\n'),self.result(),self.result(),self.result()])
        self.assertEqual(b'{}',value);self.assertEqual(4,len(calls))
        self.assertEqual(['adb','-s','emulator-5560','reconnect'],calls[1].args[0])
    def test_text_read_preserves_exact_bytes_as_text(self):
        value,_=self.read([self.result(out='{"a":1}\n',err='')],binary=False);self.assertEqual('{"a":1}\n',value)
    def test_missing_file_and_other_errors_do_not_retry(self):
        for error in (b'No such file',b'permission denied',b'error: device offline\nother error'):
            with self.subTest(error=error),self.assertRaises(subprocess.CalledProcessError):self.read([self.result(1,err=error)])
    def test_repeated_offline_error_still_fails(self):
        with self.assertRaises(subprocess.CalledProcessError):self.read([self.result(1,err=b'error: device offline'),self.result(),self.result(),self.result(1,err=b'error: device offline')])
    def test_wrong_emulator_api_or_offline_state_fails(self):
        for identity in (('other\nOK','1','36','1'),('pyfa-local-test\nOK','0','36','1'),('pyfa-local-test\nOK','1','35','1'),('pyfa-local-test\nOK','1','36','0')):
            with self.subTest(identity=identity),self.assertRaises(AssertionError):self.read([self.result(1,err=b'error: device offline'),self.result(),self.result()],identity)
    def test_instrumentation_and_mutations_keep_original_no_retry_path(self):
        with patch.object(native.os,'name','nt'),patch.object(native.subprocess,'check_output',return_value='original') as call,patch.object(native.subprocess,'run') as run:
            self.assertEqual('original',native.adb('shell','am','instrument'))
            self.assertEqual('original',native.adb('uninstall','synthetic'))
            self.assertEqual(2,call.call_count);run.assert_not_called()
    def test_linux_read_keeps_original_path(self):
        with patch.object(native.os,'name','posix'),patch.object(native.subprocess,'check_output',return_value=b'original'),patch.object(native.subprocess,'run') as run:
            self.assertEqual(b'original',native.adb('exec-out','cat','report',binary=True));run.assert_not_called()

class HistoricalFixtureGuardTest(unittest.TestCase):
    old='self.new={path:(ROOT/path).read_text() for path in self.old}'
    new="self.new={path:subprocess.check_output(['git','show','7812de8024259d890e77435f794e69f71e75326b:'+path],cwd=ROOT,text=True,encoding='utf-8') for path in self.old}"
    def check(self,after):
        from local_verification import pending_stale_test_fixture_fix
        with patch.object(subprocess,'check_output',side_effect=[self.old,after]):pending_stale_test_fixture_fix(None,'before','after')
    def test_exact_historical_fixture_passes(self):self.check(self.new)
    def test_wrong_historical_revision_fails(self):
        with self.assertRaises(AssertionError):self.check(self.new.replace('7812de80','00000000'))
    def test_unrelated_test_change_fails(self):
        with self.assertRaises(AssertionError):self.check(self.new+'\nassert True')
