"""Trace original property getters and presentation, retaining stable supported values."""
import ast
from collections.abc import Mapping
from enum import Enum
from functools import cmp_to_key
import math
import re
from pathlib import Path
from types import SimpleNamespace


def representation(value, depth=0):
    """Independent schema projection of original getter values, never Android values.

    Primitive values stay precise. Enums and EOS identities retain their named
    fields; collections retain every member. Diagnostics which cannot form a
    portable value are explicitly unavailable, including deep/cyclic structures.
    """
    if value is None or type(value) in (str, int, bool): return value
    if type(value) is float:
        if math.isnan(value): raise ValueError('NaN has no property value')
        if math.isinf(value): return {'number_kind': 'positive_infinity' if value > 0 else 'negative_infinity'}
        return value
    if isinstance(value, Enum): return {'enum': type(value).__name__, 'name': value.name, 'value': value.value}
    if depth >= 4: raise ValueError('Object requires further inspection')
    if isinstance(value, Mapping):
        if not all(type(key) is str for key in value): raise ValueError('Mapping keys are not strings')
        return {key: representation(value[key], depth + 1) for key in sorted(value)}
    if isinstance(value, tuple) and hasattr(value, '_fields'):
        return {key: representation(getattr(value, key), depth + 1) for key in value._fields}
    if isinstance(value, (tuple, list)): return [representation(member, depth + 1) for member in value]
    if type(value).__module__.startswith('eos.'):
        identity = getattr(value, 'ID', None)
        if type(identity) is int: return {'object_type': type(value).__name__, 'id': identity, 'name': getattr(value, 'name', None)}
    raise ValueError('Nonportable diagnostic object')


def load(source, app=None):
    import wx
    app = wx.App(False) if app is None else app
    path = Path(source) / 'gui/builtinItemStatsViews/itemProperties.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'PopulateList')
    namespace = dict(_t=wx.GetTranslation)
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)

    class Proxy:
        def __init__(self, owner):
            assert not any(name.startswith('_oracle_') for name in dir(owner))
            self._oracle_owner, self._oracle_reads, self._oracle_errors = owner, {}, {}
        def __dir__(self):
            self._oracle_names = dir(self._oracle_owner)
            return self._oracle_names
        def __bool__(self): return bool(self._oracle_owner)
        def __getattr__(self, name):
            try:
                value = getattr(self._oracle_owner, name)
                self._oracle_reads[name] = value
                self._oracle_last = name
                return value
            except (KeyboardInterrupt, SystemExit): raise
            except Exception as error:
                self._oracle_errors[name] = type(error).__name__
                raise

    class Table:
        def __init__(self, proxy): self.rows, self.proxy = [], proxy
        def InsertColumn(self, *args): pass
        def SetColumnWidth(self, *args): pass
        def setResizeColumn(self, *args): pass
        def GetItemCount(self): return len(self.rows)
        def InsertItem(self, index, label):
            self.rows.append(dict(name=self.proxy._oracle_last, label=label, value=None, data=None)); return index
        def SetItemData(self, index, data): self.rows[index]['data'] = data
        def SetItem(self, index, column, text): self.rows[index]['value'] = text
        def SortItems(self, compare): self.rows.sort(key=cmp_to_key(lambda left, right: compare(left['data'], right['data'])))
        def RefreshRows(self): pass

    def observe(stuff, item, fit):
        owner = item if stuff is None else stuff
        proxy = Proxy(owner); table = Table(proxy)
        view = SimpleNamespace(stuff=None if stuff is None else proxy, item=proxy, paramList=table,
                               totalAttrsLabel=SimpleNamespace(SetLabel=lambda *args: None), Layout=lambda: None)
        namespace['PopulateList'](view)
        rows = []
        for name in sorted(proxy._oracle_names, key=lambda name: (name.title(), name)):
            if name.startswith('__') and name.endswith('__'): continue
            stable_name = re.sub(r'^(_AssociationProxy_.+)_\d+_inst$', r'\1_inst', name)
            row = dict(name=stable_name, label=stable_name.title(), available=False, value=None, reason=None, display=None)
            text = next((entry['value'] for entry in table.rows if entry['name'] == name), None)
            if name.startswith('_'): row['reason'] = 'Private diagnostic member'
            elif name in proxy._oracle_errors: row['reason'] = f'Unavailable property ({proxy._oracle_errors[name]})'
            else:
                value = proxy._oracle_reads[name]
                if callable(value): row['reason'] = 'Callable diagnostic member'
                else:
                    try: row['value'] = representation(value); row['available'] = True
                    except (KeyboardInterrupt, SystemExit): raise
                    except Exception as error: row['reason'] = f'Unavailable property ({type(error).__name__})'
            # Original primitive formatting is portable; repr of an object or
            # structured collection may contain process addresses and is never
            # saved as an apparently stable expected value.
            portable_text = text if row['available'] and (row['value'] is None or type(row['value']) in (bool, int, float, str)) else None
            if row['available'] and name in proxy._oracle_reads and (proxy._oracle_reads[name] is None or type(proxy._oracle_reads[name]) in (bool, int, float, str)):
                row['display'] = text
            rows.append(dict(contract=row, original_present=text is not None, original_primitive_display=portable_text))
        rows.sort(key=lambda row: (row['contract']['label'], row['contract']['name']))
        if len({row['contract']['name'] for row in rows}) != len(rows): raise ValueError('Duplicate normalized property names')
        return rows
    observe.app = app
    return observe
