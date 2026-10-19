"""Independent original AST replay over frozen exact-horizon scalar caches.

No candidate imports, EOS boot, database or generated expected formula. Null
secondary distance uses source-qualified unit application; non-null is excluded.
"""
import ast
from pathlib import Path
from types import SimpleNamespace as NS

class OriginalReplay:
    def __init__(self,source):
        namespace={'PointGetter':object}
        stats=ast.parse((source/'eos/utils/stats.py').read_text())
        getter=ast.parse((source/'graphs/data/fitRemoteReps/getter.py').read_text())
        nodes=[n for n in stats.body if isinstance(n,ast.ClassDef) and n.name=='RRTypes']
        nodes += [n for n in getter.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in ('XTimeMixin','applyReps')]
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source/'graphs/data/fitRemoteReps/getter.py'),'exec'),namespace)
        self.namespace=namespace
    def curve(self,maps,horizon,window):
        assert window[1]==horizon,'Never substitute larger retained horizon'
        rr=self.namespace['RRTypes'];cache={row['time']:{r['key']:rr(**r['repair']) for r in row['rows']} for row in maps}
        keys={key for values in cache.values() for key in values}
        # Null distance bypasses source lock/DCR/range gates and applies 1 to all.
        self.namespace['getApplicationPerKey']=lambda src,distance: {k:1 for k in keys} if distance is None else (_ for _ in ()).throw(AssertionError('null only'))
        obj=self.namespace['XTimeMixin']()
        def prepare(src,ancReload,maxTime):assert maxTime==horizon
        obj._prepareTimeCache=prepare;obj._getTimeCacheData=lambda src,ancReload:cache
        return obj.getRange(window,{'ancReload':True,'distance':None},NS(item=None),None)
