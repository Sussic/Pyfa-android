"""G06 read-only, bounded lock-time graph samples from original EOS.

Range semantics match graphs/data/base/getter.py SmoothPointGetter; point values
call fit.calculateLockTime as the pinned fitLockTime getter does. Cancellation is
cooperative between EOS calls, never a hard interruption of an EOS calculation.
"""
from android_bridge.projected_drone_admission import AdmissionRejected
import math
import time
from copy import deepcopy
from .capacitor_samples import SamplingError, _keys, _number, _integer, _text, _context
from android_bridge.history import _same


def sample_locktime(request, *, resolve_fit, current_context, cancelled=lambda: False,
                    clock=time.monotonic, prepare_fit=None):
    request_id=None
    def fail(code,message):raise SamplingError(code,message)
    try:
        _keys(request, ('version','request_id','context','fits','x','y','resolution','budget_ms'), 'request')
        _integer(request['version'],1,1,'version');_text(request['request_id'],'request_id');request_id=request['request_id']
        _context(request['context']);_keys(request['x'],('quantity','unit','range'),'x');_keys(request['y'],('quantity','unit'),'y')
        if (request['x']['quantity'],request['x']['unit'])!=('signature_radius','m') or request['y']!={'quantity':'lock_time','unit':'s'}:
            fail('invalid_request','Lock-time axes must be target signature radius in metres and time in seconds')
        bounds=request['x']['range']
        if type(bounds) is not list or len(bounds)!=2:fail('invalid_request','Provide two signature-radius endpoints')
        low,high=bounds;_number(low,1,1e9,'lower radius');_number(high,low,1e9,'upper radius')
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
            if cancelled():fail('cancelled','Lock-time sampling was cancelled')
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
            scan=fit.ship.getModifiedItemAttr('scanResolution')
            if scan is not None:_number(scan,-math.inf,math.inf,'scan resolution','invalid_engine_data')
            xs=[];ys=[]
            for index in range(1 if step==0 else request['resolution']+1):
                check();x=low+step*index;y=fit.calculateLockTime(radius=x)
                _number(y,0,math.inf,'lock time','invalid_engine_data')
                xs.append(x);ys.append(y);total+=1
            series.append(dict(fit_id=row['fit_id'],revision=row['revision'],scan_resolution=scan,x=xs,y=ys))
        check()
        for row,fit in handles:
            if resolve(row) is not fit:fail('stale_fit','A selected fit was replaced; sample again')
        return dict(version=1,request_id=request_id,ok=True,context=deepcopy(request['context']),x=deepcopy(request['x']),
                    y=deepcopy(request['y']),total_points=total,series=series,error=None)
    except SamplingError as error:
        return dict(version=1,request_id=request_id,ok=False,error=dict(code=error.code,message=str(error)))
    except AdmissionRejected as error:
        return dict(version=1,request_id=request_id,ok=False,error=dict(code='resource_exhausted',message=str(error)))
    except Exception:
        return dict(version=1,request_id=request_id,ok=False,error=dict(code='engine_error',message='Lock-time samples unavailable; no partial graph was returned'))
