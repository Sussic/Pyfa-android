"""Observe unchanged pinned C02 refresh methods on actual wx controls."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    import eos.config
    import eos.db
    from eos.utils.spoolSupport import SpoolOptions, SpoolType
    from gui.utils.numberFormatter import formatAmount, roundToPrec
    app=wx.App(False); frame=wx.Frame(None); panel=wx.Panel(frame)
    namespaces={}; views={}; hashes={}
    for name,file in (('firepower','firepowerViewFull'),('mining','miningyieldViewFull'),
                      ('bombing','bombingViewFull'),('outgoing','outgoingViewFull')):
        path=Path(source)/'gui/builtinStatsViews'/f'{file}.py';text=path.read_text(encoding='utf-8')
        tree=ast.parse(text); cls=next(n for n in tree.body if isinstance(n,ast.ClassDef))
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='refreshPanel')
        nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='stats' for t in n.targets)]
        if name=='outgoing':
            minimal_path=Path(source)/'gui/builtinStatsViews/outgoingViewMinimal.py'
            minimal=ast.parse(minimal_path.read_text(encoding='utf-8'))
            minimal_cls=next(n for n in minimal.body if isinstance(n,ast.ClassDef))
            minimal_method=next(n for n in minimal_cls.body if isinstance(n,ast.FunctionDef) and n.name=='refreshPanel')
            minimal_stats=[n for n in minimal.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='stats' for t in n.targets)]
            assert ast.dump(ast.Module(body=[*nodes,method],type_ignores=[]))==ast.dump(ast.Module(body=[*minimal_stats,minimal_method],type_ignores=[]))
        namespace=dict(wx=wx,eos=__import__('eos'),math=__import__('math'),formatAmount=formatAmount,
            roundToPrec=roundToPrec,SpoolOptions=SpoolOptions,SpoolType=SpoolType,_t=lambda x:x,
            FittingModuleState=__import__('eos.const',fromlist=['FittingModuleState']).FittingModuleState,
            Market=SimpleNamespace(getInstance=lambda:SimpleNamespace(getItem=eos.db.getItem)))
        exec(compile(ast.Module(body=[*nodes,method],type_ignores=[]),str(path),'exec'),namespace)
        view=SimpleNamespace(panel=panel,headerPanel=panel,_cachedValues=[None]*5,stEff=wx.StaticText(panel))
        labels={'firepower':['labelFullDpsWeapon','labelFullDpsDrone','labelFullDpsTotal','labelFullVolleyTotal'],
                'mining':['labelFullminingyieldMiner','labelFullminingyieldDrone','labelFullminingyieldTotal'],
                'outgoing':['labelRemoteCapacitor','labelRemoteShield','labelRemoteArmor','labelRemoteHull'],
                'bombing':[f'labelDamagetypeCovertlevel{k.capitalize()}{level}' for level in range(6) for k in ('em','thermal','kinetic','explosive')]}[name]
        for label in labels:setattr(view,label,wx.StaticText(panel))
        namespaces[name]=namespace;views[name]=view
        hashes[name]=hashlib.sha256(text.replace('\r\n','\n').encode()).hexdigest()

    def scalar(value,unit,display=None,detail=None,prec=3):
        assert type(value) in (int,float)
        text=formatAmount(value,prec,0,0)
        return dict(value=value,value_type='integer' if type(value) is int else 'decimal',unit=unit,
                    display=text if display is None else display,detail=text if detail is None else detail)
    def tip(label):return label.GetToolTip().GetTip() if label.GetToolTip() else ''

    def observe(fit):
        modes={};original=fit.targetProfile
        for mode in ('raw','effective'):
            fit.targetProfile=None if mode=='raw' else original;fit.clear();fit.calculateModifiedAttributes()
            view=views['firepower'];view._cachedValues=[None]*5
            namespaces['firepower']['refreshPanel'](view,fit)
            default=eos.config.settings['globalDefaultSpoolupPercentage']
            options=[SpoolOptions(SpoolType.SPOOL_SCALE,value,force) for value,force in ((default,False),(0,True),(1,True))]
            source=dict(weapon=[fit.getWeaponDps(spoolOptions=o) for o in options],drone=[fit.getDroneDps()]*3,
                        total=[fit.getTotalDps(spoolOptions=o) for o in options],volley=[fit.getTotalVolley(spoolOptions=o) for o in options])
            rows={}
            for name,values in source.items():
                label=getattr(view,dict(weapon='labelFullDpsWeapon',drone='labelFullDpsDrone',total='labelFullDpsTotal',volley='labelFullVolleyTotal')[name])
                unit='HP' if name=='volley' else 'DPS';current,pre,full=values
                display=label.GetLabel().removesuffix(' DPS')
                parts={k:dict(amount=scalar(getattr(current,k),unit),share=scalar(getattr(current,k)/current.total*100 if current.total else 0.0,'%'))
                       for k in current.names(includePure=True)}
                rows[name]=dict(current=scalar(current.total,unit,display),pre=scalar(pre.total,unit),full=scalar(full.total,unit),
                                indicated='\u02e2' in display,tooltip=tip(label),damage=parts)
            modes[mode]=rows
        fit.targetProfile=original;fit.clear();fit.calculateModifiedAttributes()
        mining={};view=views['mining'];view._cachedValues=[None]*5
        namespaces['mining']['refreshPanel'](view,fit)
        for name,field,label in (('module','miner','Miner'),('drone','drone','Drone'),('total','total','Total')):
            y=getattr(fit,field+'Yield');d=getattr(fit,field+'Drain')
            control=getattr(view,'labelFullminingyield'+label)
            efficiency=y/d*100 if d else 0.0
            mining[name]=dict(yield_second=scalar(y,'m³/s',control.GetLabel().removesuffix(' m³/s')),
                drain_second=scalar(d,'m³/s'),yield_hour=scalar(y*3600,'m³/hour'),drain_hour=scalar(d*3600,'m³/hour'),efficiency=scalar(efficiency,'%',prec=4))
            expected='{} m³ yield per second ({} m³ per hour)\n{} m³ drain per second ({} m³ per hour)\n{}% efficiency'.format(
                mining[name]['yield_second']['display'],mining[name]['yield_hour']['display'],mining[name]['drain_second']['display'],
                mining[name]['drain_hour']['display'],mining[name]['efficiency']['display'])
            assert tip(control)==expected
        outgoing={};view=views['outgoing'];view._cachedValues=[None]*5
        namespaces['outgoing']['refreshPanel'](view,fit)
        values=[fit.getRemoteReps(spoolOptions=o) for o in options]
        for name in ('capacitor','shield','armor','hull'):
            current,pre,full=[getattr(row,name) for row in values];unit='GJ/s' if name=='capacitor' else 'HP/s'
            label=getattr(view,'labelRemote'+name.capitalize());display=label.GetLabel().removesuffix(' '+unit)
            outgoing[name]=dict(current=scalar(current,unit,display),pre=scalar(pre,unit),full=scalar(full,unit),indicated='\u02e2' in display,tooltip=tip(label))
        view=views['bombing'];namespaces['bombing']['refreshPanel'](view,fit)
        levels=[]
        for level in range(6):
            counts={}
            for kind in ('em','thermal','kinetic','explosive'):
                label=getattr(view,f'labelDamagetypeCovertlevel{kind.capitalize()}{level}');text=label.GetLabel()
                counts[kind]=scalar(float(text),'bombs',text,text)
            levels.append(dict(covert_ops_level=level,counts=counts))
        modifier=1.0
        for effect in fit.projectedModules:
            if effect.state==namespace['FittingModuleState'].ONLINE and effect.fullName in [f'Class {i} Red Giant Effects' for i in range(1,7)]:
                modifier*=effect.item.attributes['smartbombDamageMultiplier'].value
        return dict(output=dict(firepower=modes,mining=mining,
            bombing=dict(signature=scalar(fit.ship.getModifiedItemAttr('signatureRadius'),'m'),environment_multiplier=scalar(modifier,'x'),levels=levels),
            outgoing=outgoing,effective=original is not None,default_spool_percentage=float(default)*100))
    return dict(observe=observe,source_sha256=hashes,close=lambda:frame.Destroy(),app=app)
