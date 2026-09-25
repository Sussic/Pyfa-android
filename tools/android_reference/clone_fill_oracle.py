"""Execute pinned desktop clone/fill command bodies without a window tree."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx as real_wx
    import eos.db
    from logbook import Logger
    from service.market import Market
    from tools.android_reference.module_oracle import load as module_load

    oracle = module_load(source)
    namespace = {
        'wx': SimpleNamespace(Command=real_wx.Command, CommandProcessor=real_wx.CommandProcessor,
                              PostEvent=lambda *_: None),
        'eos': eos, 'pyfalog': Logger('independent-clone-fill'),
        'Fit': type(oracle['service']), 'Market': Market,
        'ModuleInfo': oracle['ModuleInfo'], 'activeStateLimit': oracle['activeStateLimit'],
        'restoreCheckedStates': lambda *args: None, 'restoreRemovedDummies': lambda *args: None,
        'copy': SimpleNamespace(deepcopy=deepcopy),
        'gui': SimpleNamespace(mainFrame=SimpleNamespace(MainFrame=SimpleNamespace(
            getInstance=lambda: None))),
        'GE': SimpleNamespace(FitChanged=lambda **_: None),
    }

    def original(relative, name):
        path = Path(source) / relative
        raw = path.read_bytes()
        oracle['source_files'][relative] = hashlib.sha256(raw).hexdigest()
        nodes = [node for node in ast.parse(raw, filename=str(path)).body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name]
        if len(nodes) != 1:
            raise ValueError('Missing pinned desktop definition: ' + relative + ':' + name)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace[name]

    namespace['InternalCommandHistory'] = original(
        'gui/fitCommands/helpers.py', 'InternalCommandHistory')
    namespace['CalcAddLocalModuleCommand'] = oracle['commands']['localAdd']
    add = original('gui/fitCommands/gui/localModule/fillAdd.py',
                   'GuiFillWithNewLocalModulesCommand')
    fill_clone = original('gui/fitCommands/gui/localModule/fillClone.py',
                          'GuiFillWithClonedLocalModulesCommand')
    clone = original('gui/fitCommands/calc/module/localClone.py',
                     'CalcCloneLocalModuleCommand')
    return {**oracle, 'fill_item': add, 'fill_clone': fill_clone, 'clone': clone}
