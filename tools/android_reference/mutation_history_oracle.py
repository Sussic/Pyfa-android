"""Original remaining desktop Do/Undo definitions, with their imports kept intact."""
import ast
import hashlib
import math
from pathlib import Path
import sys
from types import ModuleType


def load(source):
    from tools.android_reference.cargo_actions_oracle import load as cargo_load
    from eos.saveddata.mode import Mode
    from eos.const import ImplantLocation
    oracle = cargo_load(source)
    common = dict(oracle['cargo_namespace'], Mode=Mode, ImplantLocation=ImplantLocation, math=math)
    common['GE'].FitRenamed = common['GE'].FitChanged
    common.update({c.__name__: c for c in oracle['variation_commands'].values()})
    common.update({c.__name__: c for c in oracle['commands'].values()})
    common.update(DroneInfo=oracle['DroneInfo'], ImplantInfo=oracle['ImplantInfo'])

    def original(relative, namespace):
        path = Path(source) / relative
        raw = path.read_bytes()
        oracle['source_files'][relative] = hashlib.sha256(raw).hexdigest()
        classes = [node for node in ast.parse(raw, filename=str(path)).body if isinstance(node, ast.ClassDef)]
        assert len(classes) == 1, relative
        exec(compile(ast.Module(body=classes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace[classes[0].name]

    commands = dict(oracle['cargo_commands'])
    # Original Undo methods import siblings. Private packages retain those imports
    # without loading unrelated GUI/account services or rewriting their bodies.
    for family, filenames in {
        'drone': ('localAdd', 'localRemove'),
        'implant': ('add', 'remove', 'toggleStates', 'changeLocation'),
        'projectedFit': ('add', 'remove', 'changeState', 'changeProjectionRange', 'changeAmount'),
        'commandFit': ('add', 'remove', 'toggleStates'),
    }.items():
        package = ModuleType('_pinned_mutation_' + family)
        package.__path__ = []
        sys.modules[package.__name__] = package
        for filename in filenames:
            module = ModuleType(package.__name__ + '.' + filename)
            module.__package__ = package.__name__
            module.__dict__.update(common)
            command = original(f'gui/fitCommands/calc/{family}/{filename}.py', module.__dict__)
            sys.modules[module.__name__] = module
            common[command.__name__] = command
            commands[f'{family}/{filename}'] = command
    # Variation GUI definitions were loaded by the forward-edit oracle. Give
    # their unchanged Undo bodies the same original sibling-import context.
    for command in oracle['variation_commands'].values():
        command.__init__.__globals__.update({name: value for name, value in common.items()
            if name.startswith('Calc')})
    for filename in ('fitRename', 'shipModeChange'):
        command = original('gui/fitCommands/calc/' + filename + '.py', common)
        common[command.__name__] = command
    command = original('gui/fitCommands/calc/module/changeCharges.py', common)
    common[command.__name__] = command
    for path in ('fitRename', 'shipModeChange', 'localModule/add', 'implant/add', 'implant/remove',
            'implant/toggleStates', 'commandFit/add', 'commandFit/remove',
            'commandFit/toggleStates', 'projectedFit/add', 'projectedFit/changeAmount',
            'localModuleCargo/localModuleToCargo', 'localModuleCargo/cargoToLocalModule'):
        command = original('gui/fitCommands/gui/' + path + '.py', common)
        common[command.__name__] = command
        commands['gui/' + path] = command
    return {**oracle, 'mutation_commands': commands, 'mutation_namespace': common}
