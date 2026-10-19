"""Execute pinned ItemParams methods without the desktop window lifecycle."""
import ast
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    import config
    from gui.utils.numberFormatter import formatAmount, roundDec
    from gui.builtinItemStatsViews.attributeGrouping import (
        AttrGroupDict, AttrGroups, CategoryGroups, GroupedAttributes, GuiAttrGroup, RequiredSkillAttrs)
    path = Path(source) / 'gui/builtinItemStatsViews/itemAttributes.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'ItemParams')
    methods = [node for node in cls.body if isinstance(node, ast.FunctionDef) and
               node.name in ('GetData', 'FormatValue', 'AddAttribute', 'ExpandOrDelete', 'PopulateList')]
    namespace = dict(wx=wx, config=config, formatAmount=formatAmount, roundDec=roundDec,
                     GroupedAttributes=GroupedAttributes, RequiredSkillAttrs=RequiredSkillAttrs,
                     CategoryGroups=CategoryGroups, GuiAttrGroup=GuiAttrGroup, AttrGroupDict=AttrGroupDict,
                     AttrGroups=AttrGroups, AttributeView=SimpleNamespace(NORMAL=1, RAW=-1),
                     BitmapLoader=SimpleNamespace(getBitmap=lambda *args: None))
    for method in methods:
        # Original function bodies are compiled unchanged. Only remove the
        # staticmethod wrapper when executing outside the wx class definition.
        method.decorator_list = []
    exec(compile(ast.Module(body=methods, type_ignores=[]), str(path), 'exec'), namespace)
    app = wx.App(False)
    config.debug = False

    class Tree:
        def __init__(self):
            self.rows, self.path = [], {}

        def AddRoot(self, text):
            self.path[0] = []
            return 0

        def AppendItem(self, parent, text):
            key = len(self.path)
            self.path[key] = self.path[parent] + [text]
            self.rows.append(dict(key=key, groups=list(self.path[parent]), label=text))
            return key

        def SetItemText(self, key, value, column):
            next(row for row in self.rows if row['key'] == key)[column] = value

        def GetChildrenCount(self, key):
            return sum(row['groups'] == self.path[key] for row in self.rows)

        def SetItemTextColour(self, *args): pass
        def SetItemImage(self, *args, **kwargs): pass
        def Delete(self, key): pass
        def Expand(self, key): pass
        def GetMainWindow(self): return self
        def GetColumnCount(self): return 0
        def SetColumnWidth(self, *args): pass

    def observe(stuff, item, charge=False):
        values = dict(item.attributes if stuff is None else
                      stuff.chargeModifiedAttributes if charge else stuff.itemModifiedAttributes)
        view = SimpleNamespace(stuff=stuff, item=item, attrInfo=dict(item.attributes), attrValues=values,
                               isStuffItem=stuff is not None and not charge,
                               isStuffCharge=charge, blank_icon=0, unknown_icon=0,
                               imageList=SimpleNamespace(Add=lambda image: 0), SetupImageList=lambda: None,
                               Layout=lambda: None)
        for name in ('GetData', 'AddAttribute', 'ExpandOrDelete'):
            setattr(view, name, lambda *args, _name=name: namespace[_name](view, *args))
        view.FormatValue = namespace['FormatValue']
        result = {}
        precise = []
        for name in sorted(values):
            attribute = item.attributes.get(name)
            current = getattr(values[name], 'value', values[name])
            base = getattr(attribute, 'value', None)
            if stuff is not None:
                getter = stuff.getChargeBaseAttrValue if charge else stuff.getItemBaseAttrValue
                base = getter(name, base)
            if base is None:
                base = current
            unit = attribute.unit if attribute is not None else None
            precise.append(dict(name=name, id=None if attribute is None else attribute.ID,
                                current=current, base=base,
                                unit=None if unit is None else dict(id=unit.ID, name=unit.name, display=unit.displayName)))
        result['precise'] = precise
        for mode, label in ((1, 'normal'), (-1, 'raw')):
            view.toggleView = mode
            view.paramList = Tree()
            namespace['PopulateList'](view)
            # GetData isn't told the attribute key by TreeCtrl. Resolve the
            # source's same group order by tracing AddAttribute calls directly.
            ordered = []
            original = view.AddAttribute

            def trace(parent, name):
                before = len(view.paramList.rows)
                original(parent, name)
                added = view.paramList.rows[before:]
                if added and 1 in added[-1]:
                    row = added[-1]
                    ordered.append(dict(name=name[0] if isinstance(name, tuple) else name,
                                        groups=row['groups'], label=row['label'], current=row[1],
                                        base=row.get(2, row[1])))
            view.AddAttribute = trace
            view.paramList = Tree()
            namespace['PopulateList'](view)
            view.AddAttribute = original
            result[label] = ordered
        return result

    return dict(observe=observe, app=app)
