"""Load original pinned desktop state command without its window tree."""
import ast
import hashlib
from pathlib import Path


def load(source):
    import wx
    from logbook import Logger
    from eos.saveddata.module import Module
    from service.market import Market
    from tools.android_reference.module_oracle import load as module_load

    oracle = module_load(source)
    namespace = {'wx': wx, 'pyfalog': Logger('independent-bulk-states'),
                 'Module': Module, 'Fit': type(oracle['service']), 'Market': Market}

    def original(relative, name):
        path = Path(source) / relative
        raw = path.read_bytes()
        oracle['source_files'][relative] = hashlib.sha256(raw).hexdigest()
        nodes = [node for node in ast.parse(raw, filename=str(path)).body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name]
        assert len(nodes) == 1
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace[name]

    similar = original('gui/fitCommands/helpers.py', 'getSimilarModPositions')
    command = original('gui/fitCommands/calc/module/localChangeStates.py',
                       'CalcChangeLocalModuleStatesCommand')
    return {**oracle, 'similar': similar, 'command': command}
