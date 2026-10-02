"""Observe the unmodified pinned resistance refresh on real wx controls."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    from gui.pyfa_gauge import PyGauge
    from gui.utils.numberFormatter import formatAmount
    path=Path(source)/'gui/builtinStatsViews/resistancesViewFull.py'
    text=path.read_text(encoding='utf-8')
    cls=next(n for n in ast.parse(text).body if isinstance(n,ast.ClassDef))
    refresh=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='refreshPanel')
    calls=[]
    def formatted(value,*args,**kwargs):
        result=formatAmount(value,*args,**kwargs);calls.append((value,result));return result
    namespace=dict(wx=wx,formatAmount=formatted,_t=wx.GetTranslation)
    exec(compile(ast.Module(body=[refresh],type_ignores=[]),str(path),'exec'),namespace)
    app=wx.App(False);frame=wx.Frame(None);panel=wx.Panel(frame)
    class ObservedGauge(PyGauge):
        def SetValue(self,value,animate=True):
            self.raw_value=value
            return super().SetValue(value,animate)
    view=SimpleNamespace(panel=panel,headerPanel=panel,showEffective=True,
        stEHPs=wx.Button(panel),stEff=wx.StaticText(panel),labelEhp=wx.StaticText(panel))
    damage=('em','thermal','kinetic','explosive');layers=('shield','armor','hull')
    for layer in (*layers,'damagePattern'):
        setattr(view,'labelResistance'+layer.capitalize()+'Ehp',wx.StaticText(panel))
        for kind in damage:
            gauge=ObservedGauge(panel,wx.Font(10,wx.FONTFAMILY_DEFAULT,wx.FONTSTYLE_NORMAL,wx.FONTWEIGHT_NORMAL),100)
            gauge.SetFractionDigits(1)
            setattr(view,'gaugeResistance'+layer.capitalize()+kind.capitalize(),gauge)
    def scalar(value,unit,display,detail):
        return dict(value=value,value_type='integer' if type(value) is int else 'decimal',unit=unit,display=display,detail=detail)
    def observe(fit):
        result=dict(layers={},total={},pattern={})
        labels={}
        for effective in (False,True):
            calls.clear();view.showEffective=effective;namespace['refreshPanel'](view,fit)
            assert len(calls)==4
            field='ehp' if effective else 'hp'
            for index,layer in enumerate(layers):
                row=result['layers'].setdefault(layer,{})
                value,display=calls[index]
                row[field]=scalar(value,'HP',display,'%d'%value)
                labels[layer+'_'+field]=getattr(view,'labelResistance'+layer.capitalize()+'Ehp').GetToolTip().GetTip()
                if effective:
                    multiplier=fit.ehp[layer]/fit.hp[layer]
                    row['multiplier']=scalar(multiplier,'x','%.2f'%multiplier,'%.2f'%multiplier)
                    row['resistances']={}
                    for kind in damage:
                        gauge=getattr(view,'gaugeResistance'+layer.capitalize()+kind.capitalize())
                        value=gauge.raw_value
                        row['resistances'][kind]=scalar(value,'%','%.1f'%gauge._percentage,'%.2f'%value)
            value,display=calls[-1];result['total'][field]=scalar(value,'HP',display,'%d'%value)
            labels['total_'+field]=view.labelEhp.GetToolTip().GetTip()
        for kind in damage:
            gauge=getattr(view,'gaugeResistanceDamagepattern'+kind.capitalize())
            result['pattern'][kind]=dict(amount=gauge.GetValue(),percentage=gauge._percentage,display='%.1f'%gauge._percentage)
        return dict(defenses=result,desktop_tooltips=labels)
    return dict(observe=observe,source_sha256=hashlib.sha256(text.replace('\r\n','\n').encode()).hexdigest(),
        close=lambda:frame.Destroy(),app=app)
