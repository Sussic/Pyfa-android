"""Storage-reader regressions, including the pathlib API available in Python 3.11."""
import ast
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import execution_policy as reader


@contextmanager
def without_junction_api(path):
    methods=[(owner,owner.__dict__['is_junction']) for owner in type(path).__mro__
             if 'is_junction' in owner.__dict__]
    for owner,_ in methods:delattr(owner,'is_junction')
    try:
        yield
    finally:
        for owner,method in methods:setattr(owner,'is_junction',method)


class StorageReaderTests(unittest.TestCase):
    def setUp(self):
        # The retained cleanup path must use the same Windows extended syntax.
        self.temporary=tempfile.TemporaryDirectory(dir=reader.filesystem_path(tempfile.gettempdir()))
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.policy={'locations':{'execution_root':str(self.root/'execution')},
                     'storage':{'accounting_roots':[str(self.root)]}}

    def test_reader_works_with_python311_pathlib_api(self):
        (self.root/'proof').write_bytes(b'preserved')
        with without_junction_api(self.root):
            self.assertFalse(hasattr(self.root,'is_junction'))
            self.assertEqual(9,reader.project_usage(self.policy,self.root,'msi'))

    @unittest.skipUnless(os.name=='nt','Windows extended-path syntax')
    def test_extended_local_unc_and_existing_prefix_are_normalized_once(self):
        self.assertEqual('\\\\?\\C:\\owned\\proof',str(reader.filesystem_path(r'C:\owned\one\..\proof')))
        self.assertEqual('\\\\?\\UNC\\server\\share\\proof',str(reader.filesystem_path(r'\\server\share\proof')))
        extended=r'\\?\C:\owned\proof'
        self.assertEqual(extended,str(reader.filesystem_path(extended)))

    def test_junction_metadata_does_not_require_newer_pathlib_method(self):
        mount=getattr(stat,'IO_REPARSE_TAG_MOUNT_POINT',0xA0000003)
        info=SimpleNamespace(st_mode=stat.S_IFDIR,st_reparse_tag=mount)
        self.assertTrue(reader.storage_redirect(info))
        self.assertTrue(reader.storage_redirect(SimpleNamespace(st_mode=stat.S_IFLNK)))
        self.assertFalse(reader.storage_redirect(SimpleNamespace(st_mode=stat.S_IFDIR)))

    @unittest.skipUnless(os.name=='nt','Actual Windows long-path filesystem')
    def test_deep_tree_and_hardlink_are_counted_once(self):
        deep=reader.filesystem_path(self.root)
        for number in range(6):
            deep=deep/('historical-'+str(number)+'-'+'x'*45)
            deep.mkdir()
        file=deep/'proof.bin';file.write_bytes(b'long-path-proof')
        self.assertGreater(len(str(file)),260)
        os.link(file,reader.filesystem_path(self.root/'alias.bin'))
        self.policy['storage']['accounting_roots'].append(str(deep))
        self.assertEqual(len(b'long-path-proof'),reader.project_usage(self.policy,self.root,'msi'))
        self.assertEqual(b'long-path-proof',file.read_bytes())

    def test_absent_declared_root_has_no_usage(self):
        self.policy['storage']['accounting_roots']=[str(self.root/'not-installed-here')]
        self.assertEqual(0,reader.project_usage(self.policy,self.root,'msi'))

    def test_unreadable_declared_root_fails_instead_of_looking_absent(self):
        actual=os.stat
        def unreadable(path,*args,**kwargs):
            if Path(path).name==self.root.name:raise PermissionError('synthetic unreadable declared root')
            return actual(path,*args,**kwargs)
        with patch.object(reader.os,'stat',side_effect=unreadable):
            with self.assertRaises(reader.PolicyError):reader.project_usage(self.policy,self.root,'msi')

    def test_unreadable_child_fails_with_root_context(self):
        (self.root/'unreadable').write_bytes(b'preserve')
        actual=Path.lstat
        def unreadable(path,*args,**kwargs):
            if path.name=='unreadable':raise PermissionError('synthetic unreadable child')
            return actual(path,*args,**kwargs)
        with patch.object(Path,'lstat',new=unreadable):
            with self.assertRaises(reader.PolicyError):reader.project_usage(self.policy,self.root,'msi')
        self.assertEqual(b'preserve',(self.root/'unreadable').read_bytes())

    def test_genuinely_deleted_temporary_child_is_tolerated(self):
        transient=self.root/'transient';transient.write_bytes(b'temporary')
        actual=os.scandir
        class Entries:
            def __init__(self,path):
                with actual(path) as entries:self.entries=list(entries)
            def __enter__(self):
                def iterate():
                    for entry in self.entries:
                        if entry.name=='transient':Path(entry.path).unlink()
                        yield entry
                return iterate()
            def __exit__(self,*_):pass
        with patch.object(reader.os,'scandir',side_effect=Entries):
            self.assertEqual(0,reader.project_usage(self.policy,self.root,'msi'))

    def test_module_uses_python311_grammar_and_no_is_junction_calls(self):
        tree=ast.parse(Path(reader.__file__).read_text(encoding='utf-8'),feature_version=(3,11))
        self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                             and node.func.attr=='is_junction' for node in ast.walk(tree)))


if __name__=='__main__':unittest.main(verbosity=2)
