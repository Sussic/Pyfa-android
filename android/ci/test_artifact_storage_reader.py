"""Win32 artifact accounting must distinguish a path-reader error from deletion."""
import ctypes
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import artifact_retention as retention


@unittest.skipUnless(os.name=='nt','Actual Win32 allocated-file reader')
class ArtifactStorageReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.file=self.root/'proof';self.file.write_bytes(b'preserve')

    def kernel(self,read):
        class Compressed:
            def __call__(self,path,high):return read(path)
        class Kernel:GetCompressedFileSizeW=Compressed()
        return Kernel()

    def test_win32_reader_receives_extended_paths_and_hardlinks_count_once(self):
        os.link(self.file,self.root/'alias')
        paths=[]
        def allocated(path):
            paths.append(str(path))
            if not str(path).startswith('\\\\?\\'):
                ctypes.set_last_error(3);return 0xffffffff
            return 4096
        with patch.object(ctypes,'WinDLL',return_value=self.kernel(allocated)):
            result=retention.usage([self.root,self.root])
        self.assertEqual(4096,result['allocated_bytes'])
        self.assertEqual(1,result['files'])
        self.assertEqual(1,len(paths))
        self.assertTrue(all(path.startswith('\\\\?\\') for path in paths))

    def test_winerror3_for_still_existing_file_is_an_error(self):
        def refused(_):
            ctypes.set_last_error(3);return 0xffffffff
        with patch.object(ctypes,'WinDLL',return_value=self.kernel(refused)):
            with self.assertRaises(OSError):retention.usage([self.root])
        self.assertEqual(b'preserve',self.file.read_bytes())

    def test_winerror2_after_confirmed_temporary_deletion_is_tolerated(self):
        def deleted(path):
            Path(path).unlink()
            ctypes.set_last_error(2);return 0xffffffff
        with patch.object(ctypes,'WinDLL',return_value=self.kernel(deleted)):
            result=retention.usage([self.root])
        self.assertEqual(0,result['allocated_bytes'])
        self.assertFalse(self.file.exists())

    def test_actual_deep_file_and_hardlink_have_allocated_usage(self):
        deep=retention.filesystem_path(self.root)
        for number in range(6):
            deep=deep/('restored-'+str(number)+'-'+'y'*45)
            deep.mkdir()
        file=deep/'evidence.bin';file.write_bytes(b'x'*8192)
        self.assertGreater(len(str(file)),260)
        os.link(file,retention.filesystem_path(self.root/'deep-alias'))
        actual=retention.usage([self.root])
        self.assertEqual(2,actual['files'])
        self.assertGreaterEqual(actual['allocated_bytes'],8192)
        self.assertEqual(b'x'*8192,file.read_bytes())

    def test_unreadable_root_is_not_silently_ignored(self):
        with patch.object(retention.os,'scandir',side_effect=PermissionError('synthetic unreadable root')):
            with self.assertRaises((OSError,retention.RetentionError)):retention.usage([self.root])


if __name__=='__main__':unittest.main(verbosity=2)
