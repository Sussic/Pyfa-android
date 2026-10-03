"""Observe the unmodified pinned recharge refresh using real wx controls."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    from gui.utils.numberFormatter import formatAmount
    path = Path(source) / 'gui/builtinStatsViews/rechargeViewFull.py'
    text = path.read_text(encoding='utf-8')
    cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef))
    refresh = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'refreshPanel')
    namespace = dict(wx=wx, formatAmount=formatAmount)
    exec(compile(ast.Module(body=[refresh], type_ignores=[]), str(path), 'exec'), namespace)
    app = wx.App(False)
    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    view = SimpleNamespace(panel=panel, headerPanel=panel, effective=False)
    for stability in ('Reinforced', 'Sustained'):
        for layer in ('Shield', 'Armor', 'Hull'):
            for prefix in ('labelTank', 'unitLabelTank'):
                setattr(view, prefix + stability + layer + 'Active', wx.StaticText(panel))
    view.labelTankSustainedShieldPassive = wx.StaticText(panel)
    view.unitLabelTankSustainedShieldPassive = wx.StaticText(panel)

    def scalar(value, unit, display, detail):
        assert type(value) in (int, float)
        return dict(value=value, value_type='integer' if type(value) is int else 'decimal',
                    unit=unit, display=display, detail=detail)

    def observe(fit):
        result = {}
        for mode, effective in (('raw', False), ('effective', True)):
            view.effective = effective
            namespace['refreshPanel'](view, fit)
            reinforced = fit.effectiveTank if effective else fit.tank
            sustained = fit.effectiveSustainableTank if effective else fit.sustainableTank
            passive = view.labelTankSustainedShieldPassive
            unit = view.unitLabelTankSustainedShieldPassive.GetLabel().strip()
            values = dict(passive_shield=scalar(reinforced['passiveShield'], unit,
                passive.GetLabel(), passive.GetToolTip().GetTip()))
            for stability, source in (('reinforced', reinforced), ('sustained', sustained)):
                repairs = {}
                for layer in ('shield', 'armor', 'hull'):
                    key = stability.capitalize() + layer.capitalize() + 'Active'
                    label = getattr(view, 'labelTank' + key)
                    observed_unit = getattr(view, 'unitLabelTank' + key).GetLabel().strip()
                    value = source[layer + 'Repair']
                    repairs[layer + 'Repair'] = scalar(value, observed_unit, label.GetLabel(), '{:.1f}'.format(value))
                    if layer == 'armor':
                        tooltip = label.GetToolTip().GetTip()
                spool = {name: scalar(source[field], unit, '{:.1f}'.format(source[field]), '{:.1f}'.format(source[field]))
                    for name, field in (('pre', 'armorRepairPreSpool'), ('full', 'armorRepairFullSpool'))}
                values[stability] = dict(repairs=repairs, armor_spool=dict(**spool, indicated=bool(tooltip), tooltip=tooltip))
            result[mode] = values
        return dict(tank=result)

    return dict(observe=observe, source_sha256=hashlib.sha256(text.replace('\r\n', '\n').encode()).hexdigest(),
                close=lambda: frame.Destroy(), app=app)
