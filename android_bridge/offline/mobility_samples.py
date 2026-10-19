"""G07 read-only, bounded mobility samples from original graph calculation methods.

Range semantics match graphs/data/base/getter.py SmoothPointGetter; point values
call the unchanged original mobility getter methods over EOS attributes. Cancellation is
cooperative between EOS calls, never a hard interruption of an EOS calculation.
"""
from android_bridge.projected_drone_admission import AdmissionRejected
import math
import time
from copy import deepcopy
from .capacitor_samples import SamplingError, _keys, _number, _integer, _text, _context
from android_bridge.history import _same
from types import SimpleNamespace
from .mobility_math import (Time2SpeedGetter, Time2DistanceGetter, Time2MomentumGetter,
                            Time2BumpSpeedGetter, Time2BumpDistanceGetter)
MODES = {
    'speed': ('m/s', Time2SpeedGetter, 1),
    'distance': ('km', Time2DistanceGetter, 1000),
    'momentum': ('Gkg⋅m/s', Time2MomentumGetter, 10**9),
    'bumpSpeed': ('m/s', Time2BumpSpeedGetter, 1),
    'bumpDistance': ('km', Time2BumpDistanceGetter, 1000),
}


def sample_mobility(request, *, resolve_fit, current_context, cancelled=lambda: False,
                    clock=time.monotonic, prepare_fit=None):
    request_id=None
    def fail(code,message):raise SamplingError(code,message)
    try:
        _keys(request, ('version','request_id','context','fits','x','y','resolution','budget_ms','target_mass_mkg','target_inertia'), 'request')
        _integer(request['version'],1,1,'version');_text(request['request_id'],'request_id');request_id=request['request_id']
        _context(request['context']);_keys(request['x'],('quantity','unit','range'),'x');_keys(request['y'],('quantity','unit'),'y')
        mode=request['y']['quantity']
        if type(mode) is not str or mode not in MODES or request['y']['unit']!=MODES[mode][0]:
            fail('invalid_request','Select a supported mobility mode and its original unit')
        if (request['x']['quantity'],request['x']['unit'])!=('time','s'):
            fail('invalid_request','Mobility x must be time in seconds')
        bounds=request['x']['range']
        if type(bounds) is not list or len(bounds)!=2:fail('invalid_request','Provide two time endpoints')
        low,high=bounds;_number(low,0,math.inf,'lower time');_number(high,low,math.inf,'upper time')
        mass=request['target_mass_mkg'];inertia=request['target_inertia']
        bump=mode in ('bumpSpeed','bumpDistance')
        if bump:
            _number(mass,0,math.inf,'target mass');_number(mass*10**6,0,math.inf,'normalized target mass')
        elif mass is not None:fail('invalid_request','Target mass is only applicable to bump modes')
        if mode=='bumpDistance':_number(inertia,0,math.inf,'target inertia')
        elif inertia is not None:fail('invalid_request','Target inertia is only applicable to bump distance')
        params={'tgtMass':mass*10**6 if bump else None,'tgtInertia':inertia}
        _,getter_type,divisor=MODES[mode]
        _integer(request['resolution'],1,1024,'resolution');_integer(request['budget_ms'],1,10000,'budget_ms')
        rows=request['fits']
        if type(rows) is not list or not 1<=len(rows)<=8:fail('invalid_request','Select one to eight fits')
        ids=set()
        for row in rows:
            _keys(row,('fit_id','revision'),'fit');_text(row['fit_id'],'fit_id');_integer(row['revision'],0,2**63-1,'revision')
            if row['fit_id'] in ids:fail('invalid_request','Select each fit once')
            ids.add(row['fit_id'])
        started=clock();_number(started,-math.inf,math.inf,'clock','clock_error');previous=started
        def check():
            nonlocal previous
            if cancelled():fail('cancelled','Mobility sampling was cancelled')
            tick=clock();_number(tick,previous,math.inf,'clock','clock_error');previous=tick
            if (tick-started)*1000>=request['budget_ms']:fail('deadline_exceeded','The cooperative sampling budget expired')
            if not _same(current_context(),request['context']):fail('stale_context','The fitting graph changed; sample again')
        def resolve(row):
            try:fit,revision=resolve_fit(row['fit_id'])
            except KeyError:fail('fit_not_found','A selected fit no longer exists')
            if type(revision) is not int or revision!=row['revision']:fail('stale_fit','A selected fit changed; sample again')
            return fit
        check();series=[];handles=[];total=0
        step=(high-low)/request['resolution']
        for row in rows:
            check();fit=resolve(row);handles.append((row,fit))
            if prepare_fit is not None:
                prepare_fit(fit)
                check()
            speed=fit.ship.getModifiedItemAttr('maxVelocity')
            _number(speed,0,math.inf,'maximum velocity','invalid_engine_data')
            source=SimpleNamespace(item=fit,getMaxVelocity=lambda:speed)
            getter=getter_type();common=getter._getCommonData(params,source,None)
            _number(common['mass'],0,math.inf,'source mass','invalid_engine_data')
            _number(common['agility'],0,math.inf,'source inertia','invalid_engine_data')
            if common['mass']==0 or common['agility']==0:
                fail('invalid_engine_data','Mobility requires positive source mass and inertia')
            align=fit.alignTime
            if align is not None:_number(align,0,math.inf,'align time','invalid_engine_data')
            xs=[];ys=[]
            for index in range(1 if step==0 else request['resolution']+1):
                check();x=low+step*index
                _number(x,0,math.inf,'sample time','invalid_engine_data')
                try:y=getter._calculatePoint(x,params,source,None,common)/divisor
                except (ArithmeticError,ValueError):fail('invalid_engine_data','Original mobility calculation is undefined or overflowed for these inputs')
                _number(y,-math.inf,math.inf,'mobility sample','invalid_engine_data')
                xs.append(x);ys.append(y);total+=1
            series.append(dict(fit_id=row['fit_id'],revision=row['revision'],max_velocity_mps=speed,align_time_s=align,x=xs,y=ys))
        check()
        for row,fit in handles:
            if resolve(row) is not fit:fail('stale_fit','A selected fit was replaced; sample again')
        return dict(version=1,request_id=request_id,ok=True,context=deepcopy(request['context']),x=deepcopy(request['x']),
                    y=deepcopy(request['y']),target_mass_mkg=mass,target_inertia=inertia,total_points=total,series=series,error=None)
    except SamplingError as error:
        return dict(version=1,request_id=request_id,ok=False,error=dict(code=error.code,message=str(error)))
    except AdmissionRejected as error:
        return dict(version=1,request_id=request_id,ok=False,error=dict(code='resource_exhausted',message=str(error)))
    except Exception:
        return dict(version=1,request_id=request_id,ok=False,error=dict(code='engine_error',message='Mobility samples unavailable; no partial graph was returned'))
