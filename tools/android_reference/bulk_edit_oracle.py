"""Execute pinned desktop selection handlers and bulk variation/removal commands."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    import wx.lib.newevent
    import eos.db
    from service.market import Market
    from tools.android_reference.variation_oracle import load as variation_load

    oracle = variation_load(source)
    files = oracle['source_files']
    receiver = oracle['event_receiver']
    service, market = oracle['service'], Market.getInstance()

    def original(relative, name, namespace):
        path = Path(source) / relative
        raw = path.read_bytes()
        files[relative] = hashlib.sha256(raw).hexdigest()
        nodes = [node for node in ast.parse(raw, filename=str(path)).body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name]
        if len(nodes) != 1:
            raise ValueError('Missing pinned desktop definition: ' + relative + ':' + name)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace[name]

    gui = SimpleNamespace(mainFrame=SimpleNamespace(MainFrame=SimpleNamespace(getInstance=lambda: receiver)))
    gui_scope = dict(wx=wx, eos=eos, gui=gui, Fit=type(service), Market=Market,
                     GE=SimpleNamespace(FitChanged=wx.lib.newevent.NewEvent()[0]),
                     CalcRemoveLocalModulesCommand=oracle['commands']['localRemove'],
                     InternalCommandHistory=oracle['module_menu_scope']['InternalCommandHistory'],
                     restoreRemovedDummies=oracle['module_menu_scope']['restoreRemovedDummies'])
    remove_command = original('gui/fitCommands/gui/localModule/remove.py',
                              'GuiRemoveLocalModuleCommand', gui_scope)

    menu_scope = dict(wx=SimpleNamespace(MOD_ALT=wx.MOD_ALT, MOD_CONTROL=wx.MOD_CONTROL),
                      ContextMenuCombined=object, Fit=type(service), Market=Market,
                      cmd=SimpleNamespace(GuiRemoveLocalModuleCommand=remove_command))
    original('gui/fitCommands/helpers.py', 'getSimilarModPositions', menu_scope)
    remove_menu = original('gui/builtinContextMenus/itemRemove.py', 'RemoveItem', menu_scope)
    variation_menu = oracle['module_menu_type']
    variation_scope = oracle['module_menu_scope']
    variation_scope['cmd'] = SimpleNamespace(
        GuiChangeLocalModuleMetasCommand=oracle['variation_commands']['module'])
    variation_scope['getSimilarModPositions'] = menu_scope['getSimilarModPositions']

    def run(fit, kind, main_position, selected_positions, scope, item_id=None):
        if scope not in ('SELECTED', 'SIMILAR') or kind not in ('variation', 'variation_direct', 'remove'):
            raise ValueError('Unknown original bulk action')
        if main_position not in selected_positions:
            raise ValueError('Include the clicked module in selection')
        selected = [fit.modules[index] for index in selected_positions]
        main = fit.modules[main_position]
        if main.isEmpty or any(module.isEmpty for module in selected):
            raise ValueError('Select fitted modules')
        state = SimpleNamespace(GetModifiers=lambda: wx.MOD_ALT if scope == 'SIMILAR' else 0)
        if kind == 'variation_direct':
            command = oracle['variation_commands']['module'](fit.ID, selected_positions, item_id)
            return {'positions': list(command.positions), 'changed': bool(command.Do())}
        if kind == 'variation':
            variation_scope['wx'].GetMouseState = lambda: state
            variation_scope['wx'].MOD_ALT, variation_scope['wx'].MOD_CONTROL = wx.MOD_ALT, wx.MOD_CONTROL
            menu = object.__new__(variation_menu)
            menu.mainItem, menu.selection = main, selected
            menu.mainVariations = market.getVariationsByItems((main.item,))
        else:
            menu_scope['wx'].GetMouseState = lambda: state
            menu = object.__new__(remove_menu)
        submitted = []
        def submit(command):
            changed = command.Do()
            submitted.append({'positions': list(command.positions), 'changed': bool(changed)})
            return changed
        menu.mainFrame = SimpleNamespace(getActiveFit=lambda: fit.ID,
                                         command=SimpleNamespace(Submit=submit))
        if kind == 'variation':
            menu._ChangeItemToVariation__handleModule(eos.db.getItem(item_id))
        else:
            menu._RemoveItem__handleModule(None, main, selected)
        if len(submitted) != 1:
            raise AssertionError('Original handler did not submit exactly one command')
        return submitted[0]

    return {**oracle, 'bulk_run': run, 'remove_command': remove_command,
            'source_files': files}
