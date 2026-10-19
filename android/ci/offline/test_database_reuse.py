"""Preventive build-cache guards; no game database or subprocess is written."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('prepare_engine', ROOT / 'android/prepare-engine.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


@unittest.skipUnless(Path("/workspace/shared").is_dir(), "Cloud-only cache reuse tests")
class DatabaseReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir='/workspace/shared')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cache = self.root / 'cache.db'
        self.cache.write_bytes(b'fixture')
        self.link = self.root / 'eve.db'
        self.link.symlink_to(self.cache)
        self.sha = prepare.digest_file(self.cache)

    def reuse(self, **kwargs):
        args = dict(reuse_cache=self.cache, expected_sha=self.sha, expected_bytes=7)
        args.update(kwargs)
        prepare.prepare_database(self.link, 'logical', **args)

    def test_valid_reuse_is_readonly(self):
        with patch.object(prepare, 'logical_database_digest', return_value='logical'), patch.object(prepare.subprocess, 'run') as run:
            self.reuse()
            run.assert_not_called()
        self.assertEqual(self.cache.read_bytes(), b'fixture')

    def test_invalid_reuse_never_regenerates(self):
        for change in ({'expected_sha':'0'*64}, {'expected_bytes':8}, {'reuse_cache':self.root/'missing'}, {'expected_sha':None}):
            with self.subTest(change=change), patch.object(prepare.subprocess, 'run') as run:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.reuse(**change)
                run.assert_not_called()
        with patch.object(prepare, 'logical_database_digest', return_value='wrong'), patch.object(prepare.subprocess, 'run') as run:
            with self.assertRaises(ValueError): self.reuse()
            run.assert_not_called()
        with patch.object(prepare, 'logical_database_digest', side_effect=RuntimeError('corrupt')), patch.object(prepare.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError): self.reuse()
            run.assert_not_called()

    def test_normal_and_builder_link_refuse_before_bootstrap(self):
        with patch.object(prepare.subprocess, 'run') as run:
            with self.assertRaises(ValueError): prepare.prepare_database(self.link, 'logical')
            run.assert_not_called()
        with patch.object(prepare.sys, 'argv', ['prepare-engine.py','--build-database',str(self.link)]), patch.object(prepare, 'bootstrap') as boot:
            with self.assertRaises(ValueError): prepare.main()
            boot.assert_not_called()

    def test_combined_flags_refuse_before_bootstrap(self):
        with patch.object(prepare.sys, 'argv', ['prepare-engine.py','--build-database',str(self.cache),'--reuse-only-database',str(self.cache)]), patch.object(prepare, 'bootstrap') as boot, patch.object(prepare.subprocess, 'run') as run:
            with self.assertRaises(SystemExit): prepare.main()
            boot.assert_not_called(); run.assert_not_called()

    def test_ancestor_and_hardlink_refuse(self):
        alias=self.root/'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): prepare.require_private_database(alias/'new.db')
        hard=self.root/'hard.db'; hard.hardlink_to(self.cache)
        with self.assertRaises(ValueError): prepare.require_private_database(hard)
        with self.assertRaises(ValueError): self.reuse()

    def test_sidecars_refuse(self):
        for suffix in ('-wal','-shm','-journal'):
            side=Path(str(self.cache)+suffix); side.touch()
            with self.assertRaises(ValueError): self.reuse()
            side.unlink()

    def test_private_valid_database_unchanged(self):
        with patch.object(prepare, 'logical_database_digest', return_value='logical'), patch.object(prepare.subprocess,'run') as run:
            prepare.prepare_database(self.cache,'logical')
            run.assert_not_called()
