"""Pure oracle/comparator self-tests. No production calculation or EOS boot."""
import copy,json,unittest
from pathlib import Path
from .compare import curve
from .replay import OriginalReplay
ROOT=Path(__file__).resolve().parents[4]
SOURCE=ROOT.parent/'cloud-source-receipts/pyfa/reconstructed-source'
PREFLIGHT=ROOT.parent/'pyfa-g052-preflight-20261018'

class ComparatorTests(unittest.TestCase):
    def test_order_and_duplicates_not_normalized(self):
        want=dict(x=[0,6,6,0],y=[0,0,256,256])
        actual=dict(want,fit_id='f',revision=1,source_rates=dict(shield=0,armor=42,hull=0))
        curve(want,actual,'overshoot')
        for bad in (dict(actual,x=sorted(actual['x'])),dict(actual,x=[0,6,0],y=[0,256,256]),dict(actual,y=[0,0,257,257])):
            with self.assertRaises(AssertionError):curve(want,bad,'mutated')
    def test_larger_horizon_rejected(self):
        with self.assertRaises(AssertionError):OriginalReplay(SOURCE).curve([],80,[0,0])
    def test_source_replay_matches_existing_exact_horizon_null_curves(self):
        replay=OriginalReplay(SOURCE);count=0
        for filename in ('ordinary-attempt-2.json','drones-attempt-1.json','spool-attempt-1.json','ancillary-attempt-2.json','linked-seed-attempt-2.json','linked-reopen-attempt-2.json','resource-attempt-1.json'):
            data=json.loads((PREFLIGHT/filename).read_text())
            for stage in data['states'].values():
                for fit in stage['fits'].values():
                    for sample in fit['samples']:
                        if sample['distance_m'] is not None:continue
                        for c in sample['curves']:
                            if c['axis']!='time' or c['range'][1]!=sample['request']['horizon']:continue
                            key='finalRps' if c['ordinate']=='rate' else 'finalRepAmount'
                            x,y=replay.curve(sample['maps'][key],sample['request']['horizon'],c['range'])
                            self.assertEqual(json.dumps([c['x'],c['y']]),json.dumps([x,y]));count+=1
        self.assertEqual(count,540)

if __name__=='__main__':unittest.main()
