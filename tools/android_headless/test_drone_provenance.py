"""C04 provenance writer contract using disposable real Git repositories only."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.android_headless.check_drone_details import source_provenance

class SourceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='c04-provenance-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.git('init','--quiet')
        self.git('config','core.autocrlf','false')
        for name in ('modified.py','removed.kt','unchanged.py','notes.txt'):
            (self.root/name).write_bytes(b'before\n')
        self.git('add','.')
        self.git('-c','user.name=Synthetic','-c','user.email=synthetic.invalid@example.invalid',
                 '-c','commit.gpgsign=false','commit','--quiet','-m','synthetic baseline')
        self.baseline=self.git('rev-parse','HEAD').strip()

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],text=True,
            env={**os.environ,'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull})

    def test_modified_added_and_deleted_sources_have_explicit_provenance(self):
        (self.root/'modified.py').write_bytes(b'after\n')
        (self.root/'removed.kt').unlink()
        (self.root/'staged.py').write_bytes(b'staged\n')
        self.git('add','staged.py')
        (self.root/'untracked space \u03bb.kt').write_bytes(b'untracked\n')
        (self.root/'notes.txt').write_bytes(b'not source\n')
        evidence=source_provenance(self.root,self.baseline)
        self.assertEqual(self.baseline,evidence['source_baseline_commit'])
        self.assertEqual({'removed.kt':'D'},evidence['deleted_source_files'])
        self.assertEqual({
            'modified.py':hashlib.sha256(b'after\n').hexdigest(),
            'staged.py':hashlib.sha256(b'staged\n').hexdigest(),
            'untracked space \u03bb.kt':hashlib.sha256(b'untracked\n').hexdigest(),
        },evidence['source_files'])
        self.assertFalse((self.root/'removed.kt').exists())

    def test_missing_baseline_refuses_provenance_instead_of_assuming_empty_history(self):
        with self.assertRaises(subprocess.CalledProcessError):
            source_provenance(self.root,'missing-c04-baseline')

if __name__=='__main__':
    unittest.main(verbosity=2)