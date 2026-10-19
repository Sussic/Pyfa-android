"""Unmodified pinned desktop drone commands, with the established inert UI sinks."""
import ast
import hashlib
from pathlib import Path
import sys
from types import ModuleType


def load(source):
    from tools.android_reference.variation_oracle import load as variation_load
    oracle = variation_load(source)
    common = dict(oracle['DroneInfo'].toDrone.__globals__)
    files = dict(oracle['source_files'])
    for package in ('gui.fitCommands.calc', 'gui.fitCommands.calc.drone'):
        module = ModuleType(package)
        module.__path__ = []
        sys.modules[package] = module
    commands = {}
    for family, stem, classname in (
        ('calc/drone', 'localAdd', 'CalcAddLocalDroneCommand'),
        ('calc/drone', 'localRemove', 'CalcRemoveLocalDroneCommand'),
        ('calc/drone', 'localChangeAmount', 'CalcChangeLocalDroneAmountCommand'),
        ('calc/drone', 'localToggleStates', 'CalcToggleLocalDroneStatesCommand'),
        ('gui/localDrone', 'add', 'GuiAddLocalDroneCommand'),
        ('gui/localDrone', 'remove', 'GuiRemoveLocalDronesCommand'),
        ('gui/localDrone', 'changeAmount', 'GuiChangeLocalDroneAmountCommand'),
        ('gui/localDrone', 'toggleStates', 'GuiToggleLocalDroneStatesCommand'),
        ('gui/localDrone', 'stackSplit', 'GuiSplitLocalDroneStackCommand'),
        ('gui/localDrone', 'stacksMerge', 'GuiMergeLocalDroneStacksCommand'),
        ('gui/localDrone', 'clone', 'GuiCloneLocalDroneCommand')):
        relative = f'gui/fitCommands/{family}/{stem}.py'
        path = Path(source) / relative
        raw = path.read_bytes()
        files[relative] = hashlib.sha256(raw).hexdigest()
        nodes = [n for n in ast.parse(raw, filename=str(path)).body
                 if isinstance(n, ast.ClassDef) and n.name == classname]
        assert len(nodes) == 1
        name = 'gui.fitCommands.' + family.replace('/', '.') + '.' + stem
        module = ModuleType(name)
        module.__dict__.update(common)
        module.__name__, module.__package__ = name, name.rpartition('.')[0]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), module.__dict__)
        sys.modules[name] = module
        commands[stem] = getattr(module, classname)
        common[classname] = commands[stem]
    return {**oracle, 'drone_commands': commands, 'source_files': files}
