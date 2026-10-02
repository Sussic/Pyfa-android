"""Execute the unmodified pinned capacitor refresh on real hidden wx controls."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    from gui.utils.numberFormatter import formatAmount
    path = Path(source) / 'gui/builtinStatsViews/capacitorViewFull.py'
    text = path.read_text(encoding='utf-8')
    cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef))
    refresh = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'refreshPanel')
    calls = []
    def observe_format(value, *args, **kwargs):
        result = formatAmount(value, *args, **kwargs)
        calls.append((value, result))
        return result
    namespace = dict(wx=wx, formatAmount=observe_format, _t=wx.GetTranslation)
    exec(compile(ast.Module(body=[refresh], type_ignores=[]), str(path), 'exec'), namespace)
    app = wx.App(False)
    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    view = SimpleNamespace(panel=panel, headerPanel=panel)
    for suffix in ('Capacity', 'Delta', 'Resist', 'Time', 'State'):
        setattr(view, 'labelFullCapacitor' + suffix, wx.StaticText(panel))

    def observe(fit):
        calls.clear()
        namespace['refreshPanel'](view, fit)
        # Capture arguments supplied by the original method to its formatter:
        # values include its exact rounded excess/resistance expressions.
        capacity, delta = calls[:2]
        offset = 2
        recharge, use, excess = (fit.capRecharge, None), (fit.capUsed, None), (None, None)
        if fit.capRecharge or fit.capUsed:
            recharge, use = calls[offset:offset + 2]
            offset += 2
            if 'Effective excessive gain:' in view.labelFullCapacitorDelta.GetToolTip().GetTip():
                excess = (calls[offset][0], '+' + calls[offset][1]); offset += 1
        resist = calls[offset]; offset += 1
        effective = (None, None)
        if 'Effective capacity:' in view.labelFullCapacitorResist.GetToolTip().GetTip():
            effective = calls[offset]; offset += 1
        assert offset == len(calls)
        values = {}
        for name, pair, unit in (
            ('capacity', capacity, 'GJ'), ('effective_capacity', effective, 'GJ'),
            ('recharge', recharge, 'GJ/s'), ('use', use, 'GJ/s'), ('delta', delta, 'GJ/s'),
            ('effective_excess', excess, 'GJ/s'), ('neutralizer_resistance', resist, '%')):
            raw, display = pair
            # Zero rates omit the desktop tooltip, but use its unchanged formatter.
            if raw is not None and display is None: display = formatAmount(raw, 3, 0, 3)
            values[name] = dict(value=raw, value_type='unavailable' if raw is None else 'integer' if type(raw) is int else 'decimal',
                unit=unit, display=display, detail=None if raw is None else '%.1f' % raw)
        state, stable = fit.capState, fit.capStable
        assert type(state) in (int, float) and type(stable) is bool
        return dict(capacitor=values, stability=dict(kind='stable' if stable else 'depletion',
            unit='%' if stable else 's', values=[state], value_types=['integer' if type(state) is int else 'decimal'],
            display=view.labelFullCapacitorTime.GetLabel()), desktop_labels={suffix:getattr(view,'labelFullCapacitor'+suffix).GetLabel()
                for suffix in ('Capacity','Delta','Resist','Time','State')},
            desktop_tooltips={suffix:getattr(view,'labelFullCapacitor'+suffix).GetToolTip().GetTip()
                for suffix in ('Capacity','Delta','Resist')})
    return dict(observe=observe, source_sha256=hashlib.sha256(text.replace('\r\n','\n').encode()).hexdigest(),
        close=lambda:frame.Destroy(), app=app)
