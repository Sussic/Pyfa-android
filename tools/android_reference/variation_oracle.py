"""Execute unchanged pinned variation commands/menu bodies with inert UI sinks.

Real wx command history, EOS, Market and Fit are used. The menu sink records
items/enabled states emitted by the original method; event delivery is irrelevant
to calculation and uses a real wx event handler. No calculation body is rewritten.
"""
import ast
import hashlib
import itertools
import math
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


def load(source):
    import wx
    import wx.lib.newevent
    import eos.db
    from eos.saveddata.drone import Drone
    from eos.saveddata.implant import Implant
    from service.market import Market
    from tools.android_reference.module_oracle import load as module_load
    oracle = module_load(source)
    files = oracle['source_files']

    def definitions(relative, names, namespace):
        path = Path(source) / relative
        content = path.read_bytes()
        files[relative] = hashlib.sha256(content).hexdigest()
        tree = ast.parse(content, filename=str(path))
        nodes = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
        assert {n.name for n in nodes} == set(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)

    common = dict(oracle['ModuleInfo'].toModule.__globals__, math=math, Drone=Drone, Implant=Implant)
    definitions('gui/fitCommands/helpers.py', ['DroneInfo', 'ImplantInfo', 'InternalCommandHistory', 'droneStackLimit'], common)
    # EOS makeRoom imports the original helper only when replacing an implant.
    gui = ModuleType('gui'); gui.__path__ = []
    commands_package = ModuleType('gui.fitCommands'); commands_package.__path__ = []
    helpers = ModuleType('gui.fitCommands.helpers'); helpers.__dict__.update(common)
    gui.fitCommands = commands_package
    for mod in (gui, commands_package, helpers):
        sys.modules[mod.__name__] = mod
    receiver = wx.EvtHandler()
    gui.mainFrame = SimpleNamespace(MainFrame=SimpleNamespace(getInstance=lambda: receiver))
    events = SimpleNamespace(FitChanged=wx.lib.newevent.NewEvent()[0], ItemChangedInplace=wx.lib.newevent.NewEvent()[0])
    common.update(gui=gui, GE=events)
    common['CalcReplaceLocalModuleCommand'] = oracle['commands']['localReplace']
    for path, name in (
            ('calc/drone/localRemove', 'CalcRemoveLocalDroneCommand'),
            ('calc/drone/localAdd', 'CalcAddLocalDroneCommand'),
            ('calc/implant/add', 'CalcAddImplantCommand'),
            ('gui/localModule/changeMetas', 'GuiChangeLocalModuleMetasCommand'),
            ('gui/localDrone/changeMetas', 'GuiChangeLocalDroneMetasCommand'),
            ('gui/implant/changeMeta', 'GuiChangeImplantMetaCommand')):
        definitions('gui/fitCommands/' + path + '.py', [name], common)
    command_types = {context: common[name] for context, name in (
        ('module', 'GuiChangeLocalModuleMetasCommand'), ('drone', 'GuiChangeLocalDroneMetasCommand'),
        ('implant', 'GuiChangeImplantMetaCommand'))}

    class MenuItem:
        def __init__(self, parent, identity, name):
            self.id, self.name, self.enabled = identity, name, True
        def Enable(self, enabled):
            self.enabled = enabled

    class Menu:
        def __init__(self): self.items = []
        def Bind(self, *args): pass
        def Append(self, *args):
            self.items.append(args[0] if len(args) == 1 else MenuItem(self, *args))
        def Enable(self, identity, value):
            next(item for item in self.items if item.id == identity).Enable(value)

    sequence = itertools.count(1)
    class ContextMenu:
        nextID = staticmethod(lambda: next(sequence))
    menu_scope = dict(common, ContextMenuCombined=ContextMenu,
                      wx=SimpleNamespace(Menu=Menu, MenuItem=MenuItem, PlatformInfo=(), EVT_MENU=None))
    definitions('gui/builtinContextMenus/itemVariationChange.py', ['ChangeItemToVariation'], menu_scope)
    menu_type = menu_scope['ChangeItemToVariation']
    service, market = oracle['service'], Market.getInstance()

    def choices(fit, item, context):
        owner = object.__new__(menu_type)
        owner.mainFrame = SimpleNamespace(getActiveFit=lambda: fit.ID)
        context_name = {'module': 'fittingModule', 'drone': 'droneItem', 'implant': 'implantItem'}[context]
        if not owner.display(None, context_name, SimpleNamespace(item=item), ()):
            return []
        menu = owner.getSubMenu(None, context_name, None, (), Menu(), 0, None)
        result, group = [], None
        for entry in menu.items:
            if entry.id not in owner.moduleLookup:
                group = entry.name.removeprefix('─ ').removesuffix(' ─')
            else:
                value, _ = owner.moduleLookup[entry.id]
                result.append({'id': value.ID, 'name': entry.name, 'group': group, 'enabled': entry.enabled})
        return result

    return {**oracle, 'variation_commands': command_types, 'choices': choices,
            'module_menu_type': menu_type, 'module_menu_scope': menu_scope,
            'DroneInfo': common['DroneInfo'], 'ImplantInfo': common['ImplantInfo'],
            'event_receiver': receiver}
