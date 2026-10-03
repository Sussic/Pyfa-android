"""Execute the unchanged pinned targeting/misc refresh on actual wx controls."""
import ast,hashlib
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    from gui.utils.numberFormatter import formatAmount
    path=Path(source)/'gui/builtinStatsViews/targetingMiscViewMinimal.py'
    text=path.read_text(encoding='utf-8');tree=ast.parse(text)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='refreshPanel')
    namespace=dict(wx=wx,formatAmount=formatAmount,OrderedDict=OrderedDict,_t=lambda x:x)
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),namespace)
    # Extract the original finite families, without copying a guessed list from Android.
    for node in ast.walk(method):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('cargoNamesOrder','RADII') for t in node.targets):
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    app=wx.App(False);frame=wx.Frame(None);panel=wx.Panel(frame)
    mapping=dict(targets='labelTargets',range='labelRange',scan_resolution='labelScanRes',sensor='labelSensorStr',
        drone_range='labelCtrlRange',speed='labelFullSpeed',align='labelFullAlignTime',signature='labelFullSigRadius',warp_speed='labelFullWarpSpeed',cargo='labelFullCargo')
    view=SimpleNamespace(panel=panel,headerPanel=panel,_cachedValues=[None]*10)
    for name in mapping.values():setattr(view,name,wx.StaticText(panel))
    def scalar(value,unit,display=None,detail=None,precision=3):
        assert value is None or type(value) in (int,float)
        formatted=None if value is None else formatAmount(value,precision,0,0)
        return dict(value=value,value_type='unavailable' if value is None else 'integer' if type(value) is int else 'decimal',
            unit=unit,display=formatted if display is None else display,detail=formatted if detail is None else detail)
    def observe(fit):
        view._cachedValues=[None]*10;namespace['refreshPanel'](view,fit)
        ship=fit.ship.getModifiedItemAttr
        values=dict(targets=(fit.maxTargets,'count'),range=(fit.maxTargetRange,'m'),scan_resolution=(ship('scanResolution'),'mm'),
            sensor=(fit.scanStrength,'points'),drone_range=(fit.extraAttributes['droneControlRange'],'m'),speed=(fit.maxSpeed,'m/s'),
            align=(fit.alignTime,'s'),signature=(ship('signatureRadius'),'m'),warp_speed=(fit.warpSpeed,'AU/s'),cargo=(ship('capacity'),'m³'))
        main={}
        for key,(value,unit) in values.items():
            label=getattr(view,mapping[key]);main[key]=scalar(value,unit,label.GetLabel(),label.GetToolTip().GetTip())
        holds=[dict(attribute=key,name=name,present=(ship(key,default=None) or 0)>0,
                    capacity=scalar(ship(key,default=None),'m³',precision=4)) for key,name in namespace['cargoNamesOrder'].items()]
        locks=[dict(name=name,radius=radius,time=scalar(fit.calculateLockTime(radius),'s','%.1fs'%fit.calculateLockTime(radius),'%.1fs'%fit.calculateLockTime(radius))) for name,radius in namespace['RADII']]
        return dict(targeting=dict(main=main,lock_times=locks,sensor_type=fit.scanType,jam_chance=scalar(fit.jamChance,'%'),
            mass=scalar(ship('mass'),'kg'),agility=scalar(ship('agility') or 0,'x'),probe_size=scalar(fit.probeSize,'x'),
            warp_distance=scalar(fit.maxWarpDistance,'AU'),warp_core=scalar(-ship('warpScrambleStatus') if ship('warpScrambleStatus') else 0,'points'),
            cargo_used=scalar(fit.cargoBayUsed,'m³',precision=4),additional_cargo=scalar(sum(row['capacity']['value'] or 0 for row in holds),'m³',precision=4),holds=holds))
    return dict(observe=observe,holds=tuple(namespace['cargoNamesOrder']),radii=namespace['RADII'],
        source_sha256=hashlib.sha256(text.replace('\r\n','\n').encode()).hexdigest(),close=lambda:frame.Destroy(),app=app)
