"""Execute unchanged pinned cargo GUI/context commands with inert UI sinks."""
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
    from service.market import Market
    from tools.android_reference.variation_oracle import load as variation_load

    oracle = variation_load(source)
    files = oracle['source_files']
    service, market = oracle['service'], Market.getInstance()

    def original(relative, name, namespace):
        path = Path(source) / relative
        raw = path.read_bytes()
        files[relative] = hashlib.sha256(raw).hexdigest()
        nodes = [node for node in ast.parse(raw, filename=str(path)).body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name == name]
        assert len(nodes) == 1, (relative, name)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), namespace)
        return namespace[name]

    gui = SimpleNamespace(mainFrame=SimpleNamespace(MainFrame=SimpleNamespace(
        getInstance=lambda: oracle['event_receiver'])))
    common = dict(oracle['ModuleInfo'].toModule.__globals__, wx=wx, math=math,
                  eos=eos, Cargo=Cargo, gui=gui,
                  GE=SimpleNamespace(FitChanged=wx.lib.newevent.NewEvent()[0]))
    original('gui/fitCommands/helpers.py', 'CargoInfo', common)
    original('gui/fitCommands/helpers.py', 'InternalCommandHistory', common)
    package = ModuleType('_pinned_cargo_commands')
    package.__path__ = []
    sys.modules[package.__name__] = package
    for filename, name in [('add', 'CalcAddCargoCommand'),
                           ('remove', 'CalcRemoveCargoCommand'),
                           ('changeAmount', 'CalcChangeCargoAmountCommand')]:
        module = ModuleType(package.__name__ + '.' + filename)
        module.__package__ = package.__name__
        module.__dict__.update(common)
        common[name] = original('gui/fitCommands/calc/cargo/' + filename + '.py', name, module.__dict__)
        sys.modules[module.__name__] = module
    commands = {}
    for filename, name in [('add', 'GuiAddCargoCommand'), ('remove', 'GuiRemoveCargosCommand'),
                           ('changeAmount', 'GuiChangeCargosAmountCommand'),
                           ('changeMetas', 'GuiChangeCargoMetasCommand')]:
        commands[filename] = original('gui/fitCommands/gui/cargo/' + filename + '.py', name, common)

    menu_scope = dict(common, ContextMenuSingle=object, _t=lambda value: value,
                      cmd=SimpleNamespace(GuiAddCargoCommand=commands['add']))
    preset_type = original('gui/builtinContextMenus/cargoAddAmmo.py', 'AddToCargoAmmo', menu_scope)
    fill_type = original('gui/builtinContextMenus/cargoFill.py', 'FillCargoWithItem', menu_scope)
    variation_type = oracle['module_menu_type']
    oracle['module_menu_scope']['cmd'] = SimpleNamespace(GuiChangeCargoMetasCommand=commands['changeMetas'])

    def item(name):
        value = eos.db.getItem(name)
        assert value is not None, name
        return value

    def run(fit, operation):
        kind = operation['kind']
        submitted = []

        def submit(command):
            changed = bool(command.Do())
            submitted.append({'changed': changed,
                'item_ids': list(command.itemIDs) if hasattr(command, 'itemIDs') else [command.itemID],
                'quantity': getattr(command, 'amount', None)})
            return changed

        frame = SimpleNamespace(getActiveFit=lambda: fit.ID,
            command=SimpleNamespace(Submit=submit),
            additionsPane=SimpleNamespace(select=lambda *args, **kwargs: None))
        visible = True
        if kind == 'add':
            submit(commands['add'](fit.ID, item(operation['item']).ID, operation['quantity']))
        elif kind in ('quantity', 'remove'):
            ids = [item(name).ID for name in operation['selected']]
            submit(commands['changeAmount'](fit.ID, ids, operation['quantity']) if kind == 'quantity'
                   else commands['remove'](fit.ID, ids))
        elif kind in ('preset', 'fill_market', 'fill_cargo'):
            value = item(operation['item'])
            if kind == 'fill_cargo':
                value = next(cargo for cargo in fit.cargo if cargo.itemID == value.ID)
            menu = object.__new__(preset_type if kind == 'preset' else fill_type)
            menu.mainFrame = frame
            context = 'cargoItem' if kind == 'fill_cargo' else 'marketItemMisc'
            visible = bool(menu.display(None, context, value))
            if visible:
                menu.activate(None, (context,), value, 0)
        elif kind == 'variation':
            lookup = {cargo.itemID: cargo for cargo in fit.cargo}
            menu = object.__new__(variation_type)
            menu.mainFrame = frame
            main = lookup[item(operation['main']).ID]
            selection = [lookup[item(name).ID] for name in operation['selected']]
            visible = bool(menu.display(None, 'cargoItem', main, selection))
            target = item(operation['item'])
            assert target in market.getVariationsByItems((main.item,))
            variations = oracle['choices'](fit, main.item, 'cargo')
            assert any(row['id'] == target.ID and row['enabled'] for row in variations)
            if visible:
                menu._ChangeItemToVariation__handleCargo(target)
        else:
            raise ValueError(kind)
        assert len(submitted) <= 1
        return {'visible': visible, 'submitted': submitted,
                'changed': any(row['changed'] for row in submitted),
                **({'variations': variations} if kind == 'variation' else {})}

    def volume_boundaries(fit):
        results = []
        for volume in (None, 0.0, -1.0):
            submitted = []
            menu = object.__new__(fill_type)
            menu.mainFrame = SimpleNamespace(getActiveFit=lambda: fit.ID,
                command=SimpleNamespace(Submit=lambda command: submitted.append(command)))
            value = SimpleNamespace(ID=222, isCharge=True, isCommodity=False,
                                    attributes={'volume': SimpleNamespace(value=volume)})
            visible = bool(menu.display(None, 'marketItemMisc', value))
            menu.activate(None, ('marketItemMisc',), value, 0)
            results.append({'volume': volume, 'visible': visible, 'submitted_count': len(submitted)})
        return results

    return {**oracle, 'run': run, 'source_files': files, 'volume_boundaries': volume_boundaries}
