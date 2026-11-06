"""Exercise the real existing offline-state validator using synthetic stdout."""
import copy
import hashlib
import unittest

from c10_collection import CollectionError
from c10_offline import check_offline_states, LABELS
from test_c10_collection import PROTOCOL


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.samples={label:dict(airplane=b'1\n',wifi=b'Wifi is disabled\n',
                                connectivity=b'Active default network: none\nCurrent Networks:\n\nStatus for known UIDs:\n') for label in LABELS}
        self.bind()

    def bind(self):
        self.pins={label:{key:hashlib.sha256(raw).hexdigest() for key,raw in sample.items()}
                   for label,sample in self.samples.items()}

    def check(self):
        return check_offline_states(self.samples,self.pins,PROTOCOL.offline_state)

    def test_all_samples_valid_still_leave_prerequisites_and_acceptance_pending(self):
        before=copy.deepcopy((self.samples,self.pins))
        result=self.check()
        self.assertEqual(6,result['checked_samples'])
        self.assertIs(False,result['native_accepted'])
        self.assertIn('phone_readiness_and_data_disable',result['remaining'])
        self.assertEqual(before,(self.samples,self.pins))

    def test_missing_extra_or_tampered_sample_is_rejected(self):
        original=copy.deepcopy(self.samples)
        for samples in ({k:v for k,v in original.items() if k!='initial'},
                        {**original,'extra':original['initial']},
                        {**original,'initial':{**original['initial'],'wifi':b'tampered'}}):
            with self.subTest(labels=samples.keys()):
                self.samples=samples
                with self.assertRaises(CollectionError):self.check()

    def test_unknown_online_timeout_and_error_outputs_are_rejected_by_real_validator(self):
        for field,raw in [('airplane',b'0'),('wifi',b'Wifi is enabled'),
                          ('connectivity',b'Active default network: 123\n'),
                          ('connectivity',b'Active default network: none\nDUMP TIMEOUT\n'),
                          ('connectivity',b'Active default network: none\nCurrent Networks:\nNetworkAgentInfo active\nStatus for known UIDs:\n'),
                          ('wifi',b'unknown'),('wifi',b'\xff')]:
            with self.subTest(field=field,raw=raw):
                self.setUp();self.samples['duration-reopen'][field]=raw;self.bind()
                with self.assertRaises(CollectionError):self.check()

    def test_preferences_or_partial_fields_cannot_replace_effective_evidence(self):
        self.samples['contract']={'telephony_preference':b'false'};self.bind()
        with self.assertRaises(CollectionError):self.check()

    def test_each_phase_requires_current_observations(self):
        for label in LABELS:
            with self.subTest(label=label):
                self.setUp();self.samples[label]['connectivity']=b'';self.bind()
                with self.assertRaises(CollectionError):self.check()
