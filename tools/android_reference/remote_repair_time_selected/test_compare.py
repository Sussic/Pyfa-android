import copy
import unittest
from .compare import curve, numeric, envelope, selected_samples

class ComparisonTests(unittest.TestCase):
    def test_exact_order_and_count(self):
        expected=dict(x=[0.,1000.,1000.],y=[0.,2.,2.]); actual=dict(fit_id='a',revision=1,source_rates={},x=[0.,1.,1.],y=[0.,2.,2.])
        curve(expected,actual,'test')
        for field,value in [('x',[0.,1.]),('x',[1.,0.,1.]),('y',[0.,2.])]:
            bad=copy.deepcopy(actual);bad[field]=value
            with self.assertRaises(AssertionError):curve(expected,bad,'bad')
    def test_zero_boolean_nonfinite(self):
        for left,right in [(0,1e-12),(1,True),(1,float('nan')),(1,float('inf'))]:
            with self.assertRaises(AssertionError):numeric(left,right,'bad')
    def test_reject_wrong_horizon(self):
        fit={'samples':[dict(distance_m=None,request={'horizon':80},curves=[dict(axis='distance',ordinate='rate',time=40)])]}
        with self.assertRaises(AssertionError):list(selected_samples(fit))
    def test_complete_error_only(self):
        request=dict(version=2,request_id='id'); response=dict(version=2,request_id='id',ok=False,error=dict(code='cancelled',message='cancelled'))
        envelope(request,response)
        response['series']=[]
        with self.assertRaises(AssertionError):envelope(request,response)


class EnvelopeTests(unittest.TestCase):
    def example(self):
        request=dict(version=2,request_id='a',context={},fits=[dict(fit_id='fit',revision=1)],x=dict(quantity='distance',unit='km',range=[0,100]),y=dict(quantity='repair_rate',unit='HP/s'),time=-5,distance=None,ancillary_reload=True,ignore_lock_range=True,ignore_drone_control_range=False,budget_ms=10000)
        response={k:v for k,v in request.items() if k not in ('budget_ms','fits')}
        response.update(ok=True,error=None,effective=dict(x_range=[0,100],time=0,distance=None),total_points=1,series=[dict(fit_id='fit',revision=1,source_rates=dict(shield=0,armor=0,hull=0),x=[0.],y=[0.])])
        return request,response
    def test_exact_echo_and_effective(self):
        request,response=self.example();envelope(request,response)
        for field,value in [('time',0),('total_points',2),('effective',dict(x_range=[0,100],time=-5,distance=None)),('version',True)]:
            changed=copy.deepcopy(response);changed[field]=value
            with self.assertRaises(AssertionError):envelope(request,changed)
    def test_reject_partial_or_wrong_revision(self):
        request,response=self.example()
        for rows in ([],[dict(response['series'][0],revision=2)]):
            changed=copy.deepcopy(response);changed['series']=rows
            with self.assertRaises(AssertionError):envelope(request,changed)

if __name__=='__main__':unittest.main()
