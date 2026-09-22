"""Load unchanged pinned desktop command definitions without its login/window tree.

This is reference-only source isolation, not an Android implementation. Real wx,
EOS, Market and settings remain in use. No calculation body or import inside a
body is rewritten. Relative command imports resolve to the same original classes
in a private package. The caller validates the source pin before loading.
"""
import ast
import hashlib
import itertools
from pathlib import Path
import sys
from time import time
from types import ModuleType
from weakref import WeakSet


def load(source):
    import wx
    from logbook import Logger
    import eos.db
    from eos.const import FittingModuleState, FittingSlot, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.damagePattern import DamagePattern as SavedDamagePattern
    from eos.saveddata.fighter import Fighter
    from eos.saveddata.fit import Fit as SavedFit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship
    from service.damagePattern import DamagePattern
    from service.market import Market
    from service.settings import SettingsProvider
    from utils.repr import makeReprStr

    files = {}

    def definitions(relative, names, namespace):
        path = Path(source) / relative
        content = path.read_bytes()
        files[relative] = hashlib.sha256(content).hexdigest()
        tree = ast.parse(content, filename=str(path))
        selected = [node for node in tree.body
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        if {node.name for node in selected} != set(names):
            raise ValueError('Missing pinned desktop definitions: ' + relative)
        # Retain the original AST nodes, including every method/decorator/body.
        exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), namespace)

    common = dict(wx=wx, eos=eos, FittingModuleState=FittingModuleState,
                  FittingSlot=FittingSlot, Module=Module, Market=Market,
                  makeReprStr=makeReprStr, pyfalog=Logger('independent-module-oracle'))
    service = dict(common, time=time, WeakSet=WeakSet, DamagePattern=DamagePattern,
                   saveddata_Character=Character, es_Citadel=Citadel, es_Ship=Ship,
                   es_DamagePattern=SavedDamagePattern, FitType=SavedFit,
                   ImplantLocation=ImplantLocation, SettingsProvider=SettingsProvider)
    definitions('service/fit.py', ['Fit'], service)
    fit_service = service['Fit']
    common['Fit'] = fit_service
    definitions('gui/fitCommands/helpers.py', ['ModuleInfo', 'activeStateLimit',
                'restoreCheckedStates', 'restoreRemovedDummies'], common)

    package = ModuleType('_pinned_module_commands')
    package.__path__ = []
    sys.modules[package.__name__] = package
    commands = {}
    for filename, name in [('localRemove', 'CalcRemoveLocalModulesCommand'),
                           ('localReplace', 'CalcReplaceLocalModuleCommand'),
                           ('localAdd', 'CalcAddLocalModuleCommand')]:
        module = ModuleType(package.__name__ + '.' + filename)
        module.__package__ = package.__name__
        module.__dict__.update(common)
        definitions('gui/fitCommands/calc/module/' + filename + '.py', [name], module.__dict__)
        sys.modules[module.__name__] = module
        commands[filename] = getattr(module, name)

    requirements = dict(common, itertools=itertools, es_Module=Module,
                        es_Slot=FittingSlot, es_Fighter=Fighter)
    definitions('service/character.py', ['Character'], requirements)
    # Only checkRequirements/_checkRequirements are called. Its constructor opens
    # character/login services, so the pure requirement walker needs no instance
    # initialization. Both executed methods remain original and unmodified.
    checker = object.__new__(requirements['Character'])
    return dict(service=fit_service.getInstance(), commands=commands,
                ModuleInfo=common['ModuleInfo'], activeStateLimit=common['activeStateLimit'],
                requirements=checker, source_files=files)
