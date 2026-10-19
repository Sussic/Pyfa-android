"""Bounded remote repair rates and event amounts using original graph methods."""
import math
import time
from copy import deepcopy
from types import SimpleNamespace
from android_bridge.history import _same
from android_bridge.projected_drone_admission import AdmissionRejected
from .capacitor_samples import SamplingError, _keys, _number, _integer, _text, _context
from .remote_repair_math import (Distance2RpsGetter, CurrentRateCache, graph_settings,
                                 ShieldRRColumn, ArmorRRColumn, HullRRColumn)


def sample_remote_repair(request, *, resolve_fit, current_context, cancelled=lambda: False,
                         clock=time.monotonic, prepare_fit=None, time_reserve=None, encode=None):
    request_id = None
    version = 2 if type(request) is dict and type(request.get("version")) is int and request["version"] == 2 else 1
    def fail(code, message):
        raise SamplingError(code, message)
    try:
        expected_keys = ('version','request_id','context','fits','x','y','time','ancillary_reload',
                        'ignore_lock_range','ignore_drone_control_range','budget_ms')
        _keys(request, expected_keys + (('distance',) if version == 2 else ()), 'request')
        _integer(request['version'],version,version,'version')
        _text(request['request_id'],'request_id'); request_id=request['request_id']
        _context(request['context'])
        _keys(request['x'],('quantity','unit','range'),'x')
        _keys(request['y'],('quantity','unit'),'y')
        time_axis = version == 2 and request['x']['quantity'] == 'time' and request['x']['unit'] == 's'
        if not time_axis and (request['x']['quantity']!='distance' or request['x']['unit']!='km'):
            fail('invalid_request','Remote repair axis must be distance in km or v2 time in s')
        amount = request['y'] == {'quantity':'repair_amount','unit':'HP'}
        if version == 1:
            if request['y']!={'quantity':'repair_rate','unit':'HP/s'} or request['time'] is not None:
                fail('invalid_request','Only current remote repair rate in HP/s is supported')
        elif not amount and request['y']!={'quantity':'repair_rate','unit':'HP/s'}:
            fail('invalid_request','Remote repair ordinate must be rate in HP/s or amount in HP')
        if amount and not time_axis and request['time'] is None:
            fail('invalid_request','Accumulated remote repair requires an explicit finite time')
        selected_time = request['time']
        secondary_distance = None
        if time_axis:
            if selected_time is not None: fail('invalid_request','Time parameter must be null for time axis')
            if request['distance'] is not None:
                _number(request['distance'],0,math.inf,'distance')
                secondary_distance = request['distance'] * 1000
                _number(secondary_distance,0,math.inf,'normalized distance')
        elif version == 2:
            if request['distance'] is not None: fail('invalid_request','Distance parameter must be null for distance axis')
            if selected_time is not None:
                _number(selected_time,-math.inf,math.inf,'time')
                selected_time = min(max(selected_time,0),2500)
        for key in ('ancillary_reload','ignore_lock_range','ignore_drone_control_range'):
            if type(request[key]) is not bool: fail('invalid_request',key+' must be boolean')
        bounds=request['x']['range']
        if type(bounds) is not list or len(bounds)!=2: fail('invalid_request','Provide two axis endpoints')
        low,high=bounds
        if time_axis:
            _number(low,-math.inf,math.inf,'lower time'); _number(high,low,math.inf,'upper time')
            normalized=[min(max(value,0),2500) for value in bounds]
        else:
            _number(low,0,math.inf,'lower distance'); _number(high,low,math.inf,'upper distance')
            normalized=[low*1000,high*1000]
            for value in normalized: _number(value,0,math.inf,'normalized distance')
        _integer(request['budget_ms'],1,10000,'budget_ms')
        rows=request['fits']
        if type(rows) is not list or not 1<=len(rows)<=8: fail('invalid_request','Select one to eight fits')
        ids=set()
        for row in rows:
            _keys(row,('fit_id','revision'),'fit'); _text(row['fit_id'],'fit_id')
            _integer(row['revision'],1,2**63-1,'revision')
            if row['fit_id'] in ids: fail('invalid_request','Select each fit once')
            ids.add(row['fit_id'])
        started=clock(); _number(started,-math.inf,math.inf,'clock','clock_error'); previous=started
        def check():
            nonlocal previous
            if cancelled(): fail('cancelled','Remote repair sampling was cancelled')
            tick=clock(); _number(tick,previous,math.inf,'clock','clock_error'); previous=tick
            if (tick-started)*1000>=request['budget_ms']: fail('deadline_exceeded','The cooperative sampling budget expired')
            if not _same(current_context(),request['context']): fail('stale_context','The fitting graph changed; sample again')
        def resolve(row):
            try: fit,revision=resolve_fit(row['fit_id'])
            except KeyError: fail('fit_not_found','A selected fit no longer exists')
            if type(revision) is not int or revision!=row['revision']: fail('stale_fit','A selected fit changed; sample again')
            return fit
        from .remote_repair_time_math import (CheckedTimeCache, CheckedDistance2RpsGetter,
                                               CheckedDistance2RepAmountGetter,
                                               CheckedTime2RpsGetter, CheckedTime2RepAmountGetter)
        cached = time_axis or selected_time is not None
        if cached and time_reserve is None:
            from .remote_repair_resource import RepairReservation
            time_reserve = RepairReservation()
        if cached:
            from .remote_repair_resource import PRICES
            supplied_reserve = time_reserve
            charged = 0
            def time_reserve(kind, count):
                nonlocal charged
                check()
                if kind not in PRICES or type(count) is not int or count < 0 or count > 2**63 - 1 - charged:
                    raise AdmissionRejected('Remote repair request accounting overflow')
                supplied_reserve(kind, count)
                charged += count
            # Bound covers <=8 fits / <=1608 points and bounded string/numeric
            # request fields, including response copies and encoding coexistence.
            if not time_axis: time_reserve('serialization_unit', 135680)
        output = None
        if time_axis:
            from .remote_repair_time_output import TimeOutput
            output = TimeOutput(time_reserve, check)
            # Time-only scalar aggregation workspace, held for the whole request.
            # Bounded coexistence (not per-event allocation), no ledger rebates.
            time_reserve('output_slot', 32)
            time_reserve('container', 4)
            time_reserve('container', 8)
            time_reserve('output_slot', 32 + len(rows) * 12)
        base_getter = ((CheckedTime2RepAmountGetter if amount else CheckedTime2RpsGetter) if time_axis else
                       CheckedDistance2RepAmountGetter if amount else
                       Distance2RpsGetter if selected_time is None else CheckedDistance2RpsGetter)
        class CheckedGetter(base_getter):
            count=0
            def _calculatePoint(self,x,miscParams,src,tgt,commonData):
                check()
                _number(x,0,math.inf,'sample distance','invalid_engine_data')
                self.count+=1
                if self.count>201: fail('invalid_engine_data','Original adaptive sample ceiling exceeded')
                try: value=super()._calculatePoint(x,miscParams,src,tgt,commonData)
                except AdmissionRejected: raise
                except (ArithmeticError,ValueError): fail('invalid_engine_data','Original remote repair calculation is undefined or overflowed')
                _number(value,-math.inf,math.inf,'repair amount' if amount else 'repair rate','invalid_engine_data')
                check()
                return value
        check(); series=[]; handles=[]; total=0
        with graph_settings(request['ignore_lock_range'],request['ignore_drone_control_range']):
            for row in rows:
                check(); fit=resolve(row); handles.append((row,fit))
                if prepare_fit is not None: prepare_fit(fit)
                check()
                source_rates={}
                for layer,cls in (('shield',ShieldRRColumn),('armor',ArmorRRColumn),('hull',HullRRColumn)):
                    if cached:
                        time_reserve('source_column_call', 1)
                        time_reserve('source_column_row', len(fit.modules) + len(fit.drones))
                    value,unit=cls()._getValue(fit)
                    if cached: check()
                    _number(value,-math.inf,math.inf,'source '+layer+' rate','invalid_engine_data')
                    if unit!='HP/s': fail('invalid_engine_data','Unexpected source repair unit')
                    source_rates[layer]=value
                check()
                cache = CheckedTimeCache(check, time_reserve) if cached else CurrentRateCache()
                try:
                    if cached: cache.reserve('container', 3)
                    getter=CheckedGetter(SimpleNamespace(_timeCache=cache, _timeOutput=output))
                    xs,ys=getter.getRange(normalized,{'time':selected_time,'distance':secondary_distance,'ancReload':request['ancillary_reload']},SimpleNamespace(item=fit),None)
                    if time_axis:
                        if not 1<=len(xs)==len(ys): fail('invalid_engine_data','Invalid original time samples')
                    elif not 1<=len(xs)==len(ys)==getter.count<=201 or any(a>b for a,b in zip(xs,xs[1:])):
                        fail('invalid_engine_data','Invalid original adaptive samples')
                    if cached and not time_axis:
                        cache.reserve('output_slot', len(xs) * 2 + 12)
                    total+=len(xs)
                    series.append(dict(fit_id=row['fit_id'],revision=row['revision'],source_rates=source_rates,x=xs if time_axis else [x/1000 for x in xs],y=ys))
                finally:
                    if cached: cache.clearAll()
        check()
        for row,fit in handles:
            if resolve(row) is not fit: fail('stale_fit','A selected fit was replaced; sample again')
        result={key:deepcopy(request[key]) for key in ('context','x','y','time','ancillary_reload','ignore_lock_range','ignore_drone_control_range')}
        if version == 2:
            result.update(distance=request['distance'],effective=dict(x_range=deepcopy(normalized if time_axis else bounds),time=selected_time,distance=secondary_distance))
        if version == 2: check()
        response = dict(version=version,request_id=request_id,ok=True,total_points=total,series=series,error=None,**result)
        if time_axis:
            # Exercise the real production encoder under the pre-reserved bound.
            # Direct host callers may request the dict; native returns this exact text.
            from android_bridge.contract import _json
            encoded = output.encode(response, encode or _json)
            for row,fit in handles:
                if resolve(row) is not fit: fail('stale_fit','A selected fit was replaced; sample again')
            check()
            if encode is not None: return encoded
        return response
    except SamplingError as error:
        return dict(version=version,request_id=request_id,ok=False,error=dict(code=error.code,message=str(error)))
    except AdmissionRejected as error:
        return dict(version=version,request_id=request_id,ok=False,error=dict(code='resource_exhausted',message=str(error)))
    except Exception:
        return dict(version=version,request_id=request_id,ok=False,error=dict(code='engine_error',message='Remote repair samples unavailable; no partial graph was returned'))
