"""Execute the pinned resource view on real hidden wx controls, without Android."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    from eos.const import FittingHardpoint
    from gui.pyfa_gauge import PyGauge
    from gui.utils.numberFormatter import formatAmount
    path = Path(source) / 'gui/builtinStatsViews/resourcesViewFull.py'
    text = path.read_text(encoding='utf-8')
    cls = next(n for n in ast.parse(text).body if isinstance(n, ast.ClassDef))
    refresh = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'refreshPanel')
    stats = next(n.value for n in refresh.body if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id == 'stats' for t in n.targets))
    namespace = dict(wx=wx, FittingHardpoint=FittingHardpoint, formatAmount=formatAmount)
    # Compile the original method intact. Only construct its presentation controls;
    # no fit getter, numeric expression, formatter or warning decision is replaced.
    exec(compile(ast.Module(body=[refresh], type_ignores=[]), str(path), 'exec'), namespace)
    app = wx.App(False)
    frame = wx.Frame(None)
    panel = wx.Panel(frame)
    pairs = (
        ('turret_hardpoints', 'TurretHardpoints', 'count'),
        ('launcher_hardpoints', 'LauncherHardpoints', 'count'),
        ('active_drones', 'DronesActive', 'count'),
        ('fighter_tubes', 'FighterTubes', 'count'),
        ('calibration', 'CalibrationPoints', 'points'),
        ('cpu', 'Cpu', 'tf'), ('powergrid', 'Pg', 'MW'),
        ('drone_bay', 'DroneBay', 'm³'), ('fighter_bay', 'FighterBay', 'm³'),
        ('drone_bandwidth', 'DroneBandwidth', 'Mbit/s'), ('cargo_bay', 'CargoBay', 'm³'),
    )
    view = SimpleNamespace(panel=panel, headerPanel=panel)
    for _, suffix, _ in pairs:
        for prefix in ('Used', 'Total'):
            setattr(view, f'labelFull{prefix}{suffix}', wx.StaticText(panel))
    for name in ('Cpu', 'Pg', 'DroneBay', 'FighterBay', 'DroneBandwidth', 'CargoBay'):
        setattr(view, 'gaugeFull' + name, PyGauge(panel, panel.GetFont()))

    def observe(fit):
        expressions = eval(compile(ast.Expression(stats), str(path), 'eval'), {**namespace, 'fit': fit})
        raw = {label % 'Full': getter() for label, getter, *_ in expressions}
        namespace['refreshPanel'](view, fit)
        rows = {}
        for name, suffix, unit in pairs:
            used_name, total_name = f'labelFullUsed{suffix}', f'labelFullTotal{suffix}'
            used, total = raw[used_name], raw[total_name]
            left, right = getattr(view, used_name), getattr(view, total_name)
            rows[name] = dict(used=used, total=total, unit=unit,
                overloaded=None if used is None or total is None else used > total,
                desktop_used=left.GetLabel(), desktop_total=right.GetLabel(),
                desktop_used_detail=left.GetToolTip().GetTip(),
                desktop_total_detail=right.GetToolTip().GetTip())
        return rows

    return dict(observe=observe, source_sha256=hashlib.sha256(text.encode()).hexdigest(),
                close=lambda: frame.Destroy(), app=app)
