"""Unchanged original module commands, including their Undo bodies and real wx history."""
import ast
import copy
import hashlib
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace


def load(source):
    import wx
    import wx.lib.newevent
    from tools.android_reference.module_oracle import load as module_load
    oracle = module_load(source)
    namespace = dict(oracle['ModuleInfo'].toModule.__globals__, copy=copy)
    receiver = wx.EvtHandler()
    namespace.update(gui=SimpleNamespace(mainFrame=SimpleNamespace(MainFrame=SimpleNamespace(getInstance=lambda: receiver))),
        GE=SimpleNamespace(FitChanged=wx.lib.newevent.NewEvent()[0], ItemChangedInplace=wx.lib.newevent.NewEvent()[0]))

    def original(relative, names, scope=namespace):
        path = Path(source) / relative
        raw = path.read_bytes()
        oracle['source_files'][relative] = hashlib.sha256(raw).hexdigest()
        nodes = [node for node in ast.parse(raw, filename=str(path)).body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        assert {node.name for node in nodes} == set(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)

    original('gui/fitCommands/helpers.py', ['InternalCommandHistory', 'getSimilarModPositions'])
    for name, command in oracle['commands'].items():
        namespace[command.__name__] = command
    for filename, name in [('changeCharges', 'CalcChangeModuleChargesCommand'),
            ('localChangeStates', 'CalcChangeLocalModuleStatesCommand'),
            ('localSwap', 'CalcSwapLocalModuleCommand'), ('localClone', 'CalcCloneLocalModuleCommand')]:
        # Retain original relative imports inside Undo (clone -> localRemove).
        module = ModuleType('_pinned_module_commands.' + filename)
        module.__package__ = '_pinned_module_commands'
        module.__dict__.update(namespace)
        original('gui/fitCommands/calc/module/' + filename + '.py', [name], module.__dict__)
        sys.modules[module.__name__] = module
        namespace[name] = module.__dict__[name]
    commands = {}
    for key, filename, name in [
            ('add', 'add', 'GuiAddLocalModuleCommand'),
            ('replace', 'replace', 'GuiReplaceLocalModuleCommand'),
            ('remove', 'remove', 'GuiRemoveLocalModuleCommand'),
            ('charges', 'changeCharges', 'GuiChangeLocalModuleChargesCommand'),
            ('states', 'changeStates', 'GuiChangeLocalModuleStatesCommand'),
            ('variation', 'changeMetas', 'GuiChangeLocalModuleMetasCommand'),
            ('swap', 'swap', 'GuiSwapLocalModulesCommand'),
            ('clone', 'clone', 'GuiCloneLocalModuleCommand'),
            ('fill_item', 'fillAdd', 'GuiFillWithNewLocalModulesCommand'),
            ('fill_clone', 'fillClone', 'GuiFillWithClonedLocalModulesCommand')]:
        original('gui/fitCommands/gui/localModule/' + filename + '.py', [name])
        commands[key] = namespace[name]
    original('gui/fitCommands/gui/fitRestrictionToggle.py', ['GuiToggleFittingRestrictionsCommand'])
    commands['restrictions'] = namespace['GuiToggleFittingRestrictionsCommand']
    # Selection cloning is an Android user-action grouping of original commands.
    # The reference executes each original Do/Undo; no fitting result is synthesized.
    class CloneSelection(wx.Command):
        def __init__(self, fit, positions):
            super().__init__(True, 'Clone Selected Local Modules')
            self.fit, self.positions, self.commands = fit, positions, []
        def Do(self):
            self.commands = []
            for position in sorted(self.positions):
                source_module = self.fit.modules[position]
                destination = next(i for i, value in enumerate(self.fit.modules)
                                   if value.isEmpty and value.slot == source_module.slot)
                command = commands['clone'](self.fit.ID, position, destination)
                assert command.Do()
                self.commands.append(command)
            return bool(self.commands)
        def Undo(self):
            return all(command.Undo() for command in reversed(self.commands))
    commands['clone_selected'] = CloneSelection
    return {**oracle, 'history_commands': commands, 'event_receiver': receiver}
