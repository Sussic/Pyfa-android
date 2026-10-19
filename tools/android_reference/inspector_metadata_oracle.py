"""Observe unchanged pinned effects and comparison methods without price networking."""
import ast
from pathlib import Path
from types import SimpleNamespace


class ListRecorder:
    def __init__(self):
        self.columns, self.rows = [], []

    def InsertColumn(self, index, label): self.columns.append(label)
    def SetColumnWidth(self, *args): pass
    def setResizeColumn(self, *args): pass
    def GetItemCount(self): return len(self.rows)
    def InsertItem(self, index, label):
        self.rows.append([label] + [''] * (len(self.columns) - 1))
        return len(self.rows) - 1
    def SetItem(self, index, column, value): self.rows[index][column] = value
    def RefreshRows(self): pass


def load(source, effects_only=False, sorts_only=False):
    import wx
    import config
    from service.market import Market
    from service.attribute import Attribute
    from gui.utils.numberFormatter import formatAmount
    namespace = dict(wx=wx, config=config, _t=wx.GetTranslation, Market=Market,
                     Attribute=Attribute, formatAmount=formatAmount)

    def methods(filename, names):
        path = Path(source) / 'gui/builtinItemStatsViews' / filename
        tree = ast.parse(path.read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        result = {}
        for node in cls.body:
            if isinstance(node, ast.FunctionDef) and node.name in names:
                node.decorator_list = []
                exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), namespace)
                result[node.name] = namespace[node.name]
        return path, tree, cls, result

    _, _, _, effects = methods('itemEffects.py', ('PopulateList',))
    path, tree, cls, comparison = methods('itemCompare.py', ('PopulateList', 'TranslateValueUnit'))
    default_sort = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'defaultSort')
    exec(compile(ast.Module(body=[default_sort], type_ignores=[]), str(path), 'exec'), namespace)
    init = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == '__init__')
    # Execute the complete original attribute-union and differing-column loops.
    # The excluded constructor statements instantiate wx controls and start the
    # optional network price service; neither generates attribute expectations.
    loops = [node for node in init.body if isinstance(node, ast.For)]
    assert len(loops) == 2
    prepare = compile(ast.Module(body=loops, type_ignores=[]), str(path), 'exec')

    def observe(item):
        config.debug = True
        table = ListRecorder()
        view = SimpleNamespace(item=item, effectList=table, Layout=lambda: None)
        effects['PopulateList'](view)
        effect_rows = [dict(id=effect.ID, name=name, implemented=bool(effect.isImplemented),
                            active=bool(effect.activeByDefault) if effect.isImplemented else None,
                            types=list(effect.type or ()), runtime=effect.runTime if effect.isImplemented else None,
                            published=bool(effect.published), description=effect.description)
                       for name, effect in sorted(item.effects.items())]
        effect_presentation = dict(columns=table.columns, rows=table.rows)
        if effects_only:
            return dict(item_id=item.ID, effects=effect_rows, effect_presentation=effect_presentation)
        family = sorted(Market.getInstance().getVariationsByItems([item]), key=namespace['defaultSort'])
        view = SimpleNamespace(items=family, attrs={}, item=item, currentSort=None, sortReverse=False,
                               highlightedNames=[], Layout=lambda: None,
                               TranslateValueUnit=comparison['TranslateValueUnit'])
        exec(prepare, namespace, dict(self=view))
        columns = [dict(name=name, id=info.ID, label=info.displayName) for name, info in view.attrs.items()]
        if sorts_only:
            view.toggleView = 1
            clicks = [('name', 0), ('name', 0)]
            clicks += [(column['name'], index + 1) for index, column in enumerate(columns) for _ in range(2)]
            clicks += [('price', len(columns) + 1), ('price', len(columns) + 1), ('name', 0)]
            if columns: clicks.append((columns[0]['name'], 1))
            clicks += [('name', 0), ('name', 0), ('default', len(columns) + 2)]
            sequence = []
            for key, column in clicks:
                view.paramList = ListRecorder()
                comparison['PopulateList'](view, column)
                sequence.append(dict(key=key, reverse=view.sortReverse, ids=[member.ID for member in view.items]))
            return dict(item_id=item.ID, columns=columns, initial_ids=[member.ID for member in family], sequence=sequence)
        presentation = {}
        for mode, label in ((1, 'normal'), (-1, 'raw')):
            view.toggleView = mode; view.paramList = ListRecorder()
            comparison['PopulateList'](view)
            presentation[label] = dict(columns=view.paramList.columns, rows=view.paramList.rows)
        return dict(item_id=item.ID, effects=effect_rows, effect_presentation=effect_presentation,
                    variation_ids=[member.ID for member in family], variation_columns=columns,
                    variation_presentation=presentation)

    def sort_probes():
        # Explicitly virtual presentation inputs; no game item or price record
        # is added to either database. Expectations execute original code.
        inputs = [dict(id=1, name='Alpha', meta=1, value=None, price=None),
                  dict(id=2, name='Beta', meta=1, value=0.0, price=0.0),
                  dict(id=3, name='éclair', meta=0, value=2.0, price=12.5),
                  dict(id=4, name='\ue000', meta=1, value=2.0, price=12.5),
                  dict(id=5, name='🧪', meta=1, value=None, price=25.0)]
        items = [SimpleNamespace(ID=row['id'], name=row['name'], metaLevel=row['meta'],
                 attributes={} if row['value'] is None else {'probe': SimpleNamespace(value=row['value'])},
                 price=SimpleNamespace(price=row['price'] or 0.0)) for row in inputs]
        items.sort(key=namespace['defaultSort'])
        initial = [row.ID for row in items]
        view = SimpleNamespace(items=items, attrs={'probe': SimpleNamespace(displayName='Probe', unit=None)}, currentSort=None, sortReverse=False,
            toggleView=-1, highlightedNames=[], Layout=lambda: None, TranslateValueUnit=comparison['TranslateValueUnit'])
        sequence = []
        for key, column in [('name', 0), ('name', 0), ('probe', 1), ('probe', 1), ('price', 2),
                            ('price', 2), ('name', 0), ('price', 2), ('name', 0), ('name', 0), ('default', 3)]:
            view.paramList = ListRecorder()
            comparison['PopulateList'](view, column)
            sequence.append(dict(key=key, reverse=view.sortReverse, ids=[row.ID for row in view.items]))
        return dict(inputs=inputs, initial_ids=initial, sequence=sequence)
    observe.sort_probes = sort_probes
    return observe
