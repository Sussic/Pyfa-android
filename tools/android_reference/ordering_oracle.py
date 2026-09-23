"""Execute unchanged pinned swap commands and the desktop heat estimator."""
import ast
import hashlib
import math
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    import wx.lib.newevent
    from tools.android_reference.module_oracle import load as module_load
    oracle = module_load(source)
    namespace = dict(oracle['ModuleInfo'].toModule.__globals__, math=math)
    receiver = wx.EvtHandler()
    namespace.update(gui=SimpleNamespace(mainFrame=SimpleNamespace(MainFrame=SimpleNamespace(getInstance=lambda: receiver))),
                     GE=SimpleNamespace(FitChanged=wx.lib.newevent.NewEvent()[0]))
    for relative, names in (
            ('gui/fitCommands/helpers.py', ['InternalCommandHistory']),
            ('gui/fitCommands/calc/module/localSwap.py', ['CalcSwapLocalModuleCommand']),
            ('gui/fitCommands/gui/localModule/swap.py', ['GuiSwapLocalModulesCommand']),
            ('gui/builtinViewColumns/heat.py', ['Thermodynamics'])):
        path = Path(source) / relative
        raw = path.read_bytes()
        oracle['source_files'][relative] = hashlib.sha256(raw).hexdigest()
        nodes = [node for node in ast.parse(raw, filename=str(path)).body
                 if isinstance(node, ast.ClassDef) and node.name in names]
        assert {node.name for node in nodes} == set(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
    oracle['source_files']['gui/builtinViews/fittingView.py'] = hashlib.sha256(
        (Path(source) / 'gui/builtinViews/fittingView.py').read_bytes()).hexdigest()
    return {**oracle, 'swap': namespace['GuiSwapLocalModulesCommand'],
            'thermodynamics': namespace['Thermodynamics'], 'event_receiver': receiver}
