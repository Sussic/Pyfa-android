"""Reject every change beyond the exact missing persistent C01.2 flag and hooks."""
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from zipfile import ZipFile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from capacitor_runner_retry import PATH,OLD,NEW,runner_source,report_source,validate_sources,packages_equal
ROOT=Path(__file__).resolve().parents[2]
BASE='855c87c304d9feca8e0c1fce1c8332f4c04072e6'
class Guard(unittest.TestCase):
    def setUp(self):
        self.paths=(PATH,'android/ci/local_verification.py','android/ci/report_local.py')
        self.old={p:subprocess.check_output(['git','show',BASE+':'+p],cwd=ROOT,text=True,encoding='utf-8') for p in self.paths}
        self.new={p:(ROOT/p).read_text(encoding='utf-8') for p in self.paths}
    def test_actual_exact_repair(self):validate_sources(self.old,self.new,list(self.paths))
    def test_all_inherited_flags(self):
        old=set(re.findall(r'containsKey\("([^"]+)"\)',self.old[PATH]));new=set(re.findall(r'containsKey\("([^"]+)"\)',self.new[PATH]))
        self.assertEqual(old|{'c012_phase'},new)
        for flag in old:self.assertFalse(new.isdisjoint({flag}))
    def test_no_flag_remains_ephemeral(self):
        keys=set(re.findall(r'containsKey\("([^"]+)"\)',self.new[PATH]));self.assertTrue(keys.isdisjoint(set()))
    def test_capacitor_phase_requires_persistence(self):
        old=set(re.findall(r'containsKey\("([^"]+)"\)',self.old[PATH]));new=set(re.findall(r'containsKey\("([^"]+)"\)',self.new[PATH]))
        self.assertTrue(old.isdisjoint({'c012_phase'}));self.assertFalse(new.isdisjoint({'c012_phase'}))
    def test_other_runner_change_rejected(self):
        self.new[PATH]+='\n// unrelated\n'
        with self.assertRaises(AssertionError):validate_sources(self.old,self.new,list(self.paths))
    def test_other_product_source_rejected(self):
        with self.assertRaises(AssertionError):validate_sources(self.old,self.new,[*self.paths,'android_bridge/capacitor.py'])
    def test_host_command_change_rejected(self):
        self.new['android/ci/local_verification.py']=self.new['android/ci/local_verification.py'].replace("'--no-daemon'","'--daemon'",1)
        with self.assertRaises(AssertionError):validate_sources(self.old,self.new,list(self.paths))
    def test_report_bypass_rejected(self):
        self.new['android/ci/report_local.py']=self.new['android/ci/report_local.py'].replace("assert state['mode']=='full'","assert True",1)
        with self.assertRaises(AssertionError):validate_sources(self.old,self.new,list(self.paths))
    def package_pair(self,changed_asset=False):
        with tempfile.TemporaryDirectory() as temp:
            paths=[Path(temp)/name for name in ('old.apk','new.apk')]
            for index,path in enumerate(paths):
                with ZipFile(path,'w') as archive:
                    archive.writestr('classes.dex',bytes([index]))
                    archive.writestr('META-INF/signature',bytes([index]))
                    archive.writestr('AndroidManifest.xml',b'unchanged')
                    archive.writestr('assets/capacitor-expected.json',b'changed' if changed_asset and index else b'fixture')
            packages_equal(*paths)
    def test_only_bytecode_signature_change_allowed(self):self.package_pair()
    def test_fixture_bytes_change_rejected(self):
        with self.assertRaises(AssertionError):self.package_pair(True)
if __name__=='__main__':unittest.main(verbosity=2)
