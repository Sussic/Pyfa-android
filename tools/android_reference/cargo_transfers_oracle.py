"""Execute unchanged pinned cargo/fitting transfer commands with real wx history."""
import ast
import hashlib
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


def load(source):
    import wx
    import wx.lib.newevent
    import eos.db
    from eos.saveddata.cargo import Cargo
    from tools.android_reference.module_oracle import load as module_load
    oracle = module_load(source)
    files = oracle['source_files']

    def original(relative, name, scope):
        path = Path(source) / relative
        raw = path.read_bytes()
        files[relative] = hashlib.sha256(raw).hexdigest()
        nodes = [node for node in ast.parse(raw, filename=str(path)).body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name]
        assert len(nodes) == 1, (relative, name)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
        return scope[name]

    receiver = wx.EvtHandler()
    common = dict(oracle['ModuleInfo'].toModule.__globals__, math=math, Cargo=Cargo,
        gui=SimpleNamespace(mainFrame=SimpleNamespace(MainFrame=SimpleNamespace(getInstance=lambda: receiver))),
        GE=SimpleNamespace(FitChanged=wx.lib.newevent.NewEvent()[0]),
        CalcReplaceLocalModuleCommand=oracle['commands']['localReplace'],
        CalcRemoveLocalModulesCommand=oracle['commands']['localRemove'])
    original('gui/fitCommands/helpers.py', 'CargoInfo', common)
    original('gui/fitCommands/helpers.py', 'InternalCommandHistory', common)
    package = ModuleType('_pinned_cargo_transfer_calcs')
    package.__path__ = []
    sys.modules[package.__name__] = package
    for filename, name in [('add', 'CalcAddCargoCommand'), ('remove', 'CalcRemoveCargoCommand')]:
        module = ModuleType(package.__name__ + '.' + filename)
        module.__package__ = package.__name__
        module.__dict__.update(common)
        common[name] = original('gui/fitCommands/calc/cargo/' + filename + '.py', name, module.__dict__)
        sys.modules[module.__name__] = module
    original('gui/fitCommands/calc/module/changeCharges.py', 'CalcChangeModuleChargesCommand', common)
    commands = {kind: original('gui/fitCommands/gui/localModuleCargo/' + filename + '.py', name, common)
        for kind, filename, name in (
            ('to_cargo', 'localModuleToCargo', 'GuiLocalModuleToCargoCommand'),
            ('from_cargo', 'cargoToLocalModule', 'GuiCargoToLocalModuleCommand'))}

    def run(fit, operation):
        positions = operation.get('positions', [operation.get('position')])
        changed = []
        for position in sorted(positions, reverse=True):
            command = commands[operation['kind']](fitID=fit.ID, modPosition=position,
                cargoItemID=operation['cargo_item_id'], copy=operation['copy'])
            changed.append(bool(command.Do()))
        return any(changed)

    return {**oracle, 'run': run, 'event_receiver': receiver}
