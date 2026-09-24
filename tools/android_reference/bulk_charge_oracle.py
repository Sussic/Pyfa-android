"""Original desktop charge selector/commands; only window event plumbing is supplied.

No Android implementation or expected-value reconstruction is used. The original
AST bodies execute against real pinned Market/Ammo/EOS and wx command history.
"""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    import wx.lib.newevent
    from service.ammo import Ammo
    from tools.android_reference.module_oracle import load as module_load
    oracle = module_load(source)
    namespace = dict(oracle['ModuleInfo'].toModule.__globals__, Ammo=Ammo)
    receiver = wx.EvtHandler()
    namespace.update(gui=SimpleNamespace(mainFrame=SimpleNamespace(MainFrame=SimpleNamespace(getInstance=lambda: receiver))),
                     GE=SimpleNamespace(FitChanged=wx.lib.newevent.NewEvent()[0]))

    def parsed(relative):
        path = Path(source) / relative
        raw = path.read_bytes()
        oracle['source_files'][relative] = hashlib.sha256(raw).hexdigest()
        return ast.parse(raw, filename=str(path))

    for relative, names in (
            ('gui/fitCommands/helpers.py', ['InternalCommandHistory', 'getSimilarModPositions']),
            ('gui/fitCommands/calc/module/changeCharges.py', ['CalcChangeModuleChargesCommand']),
            ('gui/fitCommands/gui/localModule/changeCharges.py', ['GuiChangeLocalModuleChargesCommand'])):
        nodes = [node for node in parsed(relative).body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in names]
        assert {node.name for node in nodes} == set(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(Path(source) / relative), 'exec'), namespace)

    relative = 'gui/builtinContextMenus/moduleAmmoChange.py'
    cls = next(node for node in parsed(relative).body if isinstance(node, ast.ClassDef) and node.name == 'ChangeModuleAmmo')
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in ('_getAmmo', 'handleAmmoSwitch')]
    assert len(methods) == 2
    # The selector reads mouse state only. Supply a deterministic input without
    # opening a desktop window or changing any calculation/selector body.
    mouse = SimpleNamespace(modifier=wx.MOD_NONE)
    selection_namespace = dict(namespace, cmd=SimpleNamespace(GuiChangeLocalModuleChargesCommand=namespace['GuiChangeLocalModuleChargesCommand']),
        wx=SimpleNamespace(MOD_ALT=wx.MOD_ALT, MOD_CONTROL=wx.MOD_CONTROL,
                           GetMouseState=lambda: SimpleNamespace(GetModifiers=lambda: mouse.modifier)))
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(Path(source) / relative), 'exec'), selection_namespace)

    def select(fit, main, selected, charge, scope, invert=False):
        captured = []
        holder = SimpleNamespace(module=fit.modules[main], selection=[fit.modules[p] for p in selected],
            srcContext='fittingModule', loadableChargesCache={}, chargeEventMap={1: charge},
            mainFrame=SimpleNamespace(getActiveFit=lambda: fit.ID, command=SimpleNamespace(Submit=captured.append)))
        holder._getAmmo = lambda mod: selection_namespace['_getAmmo'](holder, mod)
        holder.mainCharges = holder._getAmmo(holder.module)
        settings = oracle['service'].serviceFittingOptions
        previous = settings['ammoChangeAll']
        settings['ammoChangeAll'] = (scope == 'SIMILAR') != invert
        mouse.modifier = wx.MOD_ALT if invert else wx.MOD_NONE
        try:
            selection_namespace['handleAmmoSwitch'](holder, SimpleNamespace(Id=1))
        finally:
            settings['ammoChangeAll'] = previous
        assert len(captured) == 1
        return captured[0]

    parsed('service/ammo.py')
    return {**oracle, 'select': select, 'similar': namespace['getSimilarModPositions'], 'event_receiver': receiver}
