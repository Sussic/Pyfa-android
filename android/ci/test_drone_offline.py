"""Host-only Android 16 prerequisite fixtures; never invokes adb or an emulator."""
import importlib.util
from pathlib import Path
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'check-drones.py'
spec = importlib.util.spec_from_file_location('drone_offline_runner', RUNNER)
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)

# Reduced current-state fixtures derived from AOSP android16-release dump methods.
# These are synthetic parser inputs, never native-device evidence.
TELEPHONY = '''PhoneFactory:
 sMadeDefaults=true
  Phone: subId=1
   mPhoneId=0
  DataSettingsManager-0:
    mIsDataEnabled=false
    isDataEnabled(internet)=false
    isDataEnabled(mms)=false
    isUserDataEnabled=false
    Local logs:
      historical isUserDataEnabled=true
  UiccController:
Flag Configurations:
  synthetic_flag: true
++++++++++++++++++++++++++++++++
'''
CONNECTIVITY = '''NetworkProviders for:
  1: wifi
Active default network: none
Current network preferences:
Current Networks:

Status for known UIDs:
Network Requests:
Historical logs: CONNECTED network 100
'''
WIFI = 'Wifi is disabled\nWifi scanning is always available\n'


class StateTests(unittest.TestCase):
    def check(self, airplane='1', wifi=WIFI, connectivity=CONNECTIVITY):
        return runner.offline_state(airplane, wifi, connectivity)
    def test_complete_current_state_ignores_history(self):
        self.assertTrue(self.check()['networking_unavailable'])
        self.assertNotIn('mobile_data_disabled', self.check())
    def test_windows_line_endings(self):
        self.check(connectivity=CONNECTIVITY.replace('\n','\r\n'))
    def test_airplane_setting_alone_is_insufficient(self):
        for wifi in ('Wifi is enabled\n', '', WIFI + 'Wifi is enabled\n'):
            with self.subTest(wifi=wifi), self.assertRaises(runner.OfflineStateError): self.check(wifi=wifi)
    def test_airplane_not_enabled(self):
        with self.assertRaises(runner.OfflineStateError): self.check(airplane='0')
    def test_default_and_non_default_networks_are_rejected(self):
        for value in (CONNECTIVITY.replace('network: none','network: 100'), CONNECTIVITY.replace('Current Networks:\n','Current Networks:\n  NetworkAgentInfo: netId=101 CONNECTED\n'), 'historical Active default network: none\n', CONNECTIVITY.replace('Status for known UIDs:','unrecognised:')):
            with self.subTest(value=value), self.assertRaises(runner.OfflineStateError): self.check(connectivity=value)
    def test_no_default_does_not_hide_cellular_wifi_or_vpn_network(self):
        for transport in ('CELLULAR','WIFI','VPN'):
            value=CONNECTIVITY.replace('Current Networks:\n','Current Networks:\n  NetworkAgentInfo: '+transport+' CONNECTED\n')
            with self.subTest(transport=transport), self.assertRaises(runner.OfflineStateError): self.check(connectivity=value)
    def test_duplicate_or_truncated_current_sections_fail(self):
        for value in (CONNECTIVITY+'\nCurrent Networks:\n', CONNECTIVITY+'\nStatus for known UIDs:\n', CONNECTIVITY.split('Status for known UIDs:')[0], CONNECTIVITY+'\nActive default network: none\n'):
            with self.subTest(value=value), self.assertRaises(runner.OfflineStateError): self.check(connectivity=value)
    def test_timeout_even_with_current_fields_fails(self):
        with self.assertRaises(runner.OfflineStateError): self.check(connectivity=CONNECTIVITY+'\n*** SERVICE connectivity DUMP TIMEOUT\n')
    def test_historical_offline_fields_cannot_supply_current_proof(self):
        with self.assertRaises(runner.OfflineStateError): self.check(connectivity='Local logs: previously Active default network: none\n')


class Clock:
    def __init__(self): self.now=0
    def __call__(self): return self.now
    def sleep(self,seconds): self.now+=seconds


class GateTests(unittest.TestCase):
    def exercise(self,mode='ready'):
        clock=Clock(); calls=[]; phones=0
        def command(label,*args,timeout):
            nonlocal phones
            calls.append((label,args,timeout)); self.assertGreater(timeout,0)
            clock.now+=.1
            if label=='offline-features': return '' if mode=='feature-missing' else 'feature:android.hardware.telephony.data\n'
            if label.startswith('offline-phone-ready'):
                phones+=1
                if mode=='late-response':clock.now+=20
                if mode=='unknown-service':return 'unknown'
                return 'Service phone: not found' if mode=='missing-phone' or (mode=='delayed-phone' and phones<3) else 'Service phone: found'
            if label=='offline-data' and mode in ('data-failure','diagnostic-failure'):
                raise subprocess.CalledProcessError(20,args,stderr=b"cmd: Can't find service: phone")
            if label.startswith('offline-failure'):
                if mode=='diagnostic-failure':clock.now+=timeout;raise TimeoutError('mock diagnostic timeout')
                return 'retained diagnostic'
            if label.endswith('-airplane') and label.startswith('offline-state'):return '1'
            if label.endswith('-wifi') and label.startswith('offline-state'):return WIFI
            if label=='offline-telephony-diagnostic':
                if mode=='optional-diagnostic-failure':raise subprocess.CalledProcessError(1,args)
                if mode=='optional-diagnostic-timeout':return '*** SERVICE activity DUMP TIMEOUT ***'
                if mode=='data-preferences-true':return TELEPHONY.replace('=false','=true')
                return TELEPHONY
            if label.endswith('-connectivity'):
                if mode=='online' or (mode=='settling' and label.startswith('offline-state-0-')):
                    return CONNECTIVITY.replace('network: none','network: 100')
                return CONNECTIVITY
            return ''
        error=None; result=None
        try: result=runner.require_offline(command,clock=clock,sleep=clock.sleep,seconds=8)
        except Exception as caught:error=caught
        return result,error,calls,clock.now
    def test_delayed_phone_is_waited_for_before_mutation(self):
        result,error,calls,_=self.exercise('delayed-phone')
        self.assertIsNone(error);self.assertEqual(3,result['readiness_polls'])
        self.assertLess(next(i for i,c in enumerate(calls) if c[0]=='offline-phone-ready-2'), next(i for i,c in enumerate(calls) if c[0]=='offline-data'))
    def test_no_phone_times_out_without_mutations(self):
        result,error,calls,elapsed=self.exercise('missing-phone')
        self.assertIsNone(result);self.assertIsInstance(error,TimeoutError);self.assertLess(elapsed,29)
        self.assertFalse(any(c[0] in ('offline-airplane','offline-wifi','offline-data') for c in calls))
        self.assertTrue(any(c[0]=='offline-failure-logcat' for c in calls))
    def test_absent_capability_is_not_a_bypass(self):
        result,error,calls,_=self.exercise('feature-missing')
        self.assertIsNone(result);self.assertIsInstance(error,runner.OfflineStateError)
        self.assertFalse(any(c[0]=='offline-data' for c in calls))
    def test_nonzero_mobile_data_command_fails(self):
        result,error,calls,_=self.exercise('data-failure')
        self.assertIsNone(result);self.assertIsInstance(error,subprocess.CalledProcessError)
        self.assertFalse(any(c[0].startswith('offline-state') for c in calls))
    def test_diagnostics_cannot_mask_failure_or_exceed_shared_cap(self):
        result,error,calls,elapsed=self.exercise('diagnostic-failure')
        self.assertIsNone(result);self.assertIsInstance(error,subprocess.CalledProcessError)
        self.assertLessEqual(elapsed,21)
    def test_online_never_passes(self):
        result,error,_,elapsed=self.exercise('online')
        self.assertIsNone(result);self.assertIsInstance(error,(runner.OfflineStateError,TimeoutError));self.assertLess(elapsed,29)
    def test_state_settles_within_same_deadline(self):
        result,error,_,_=self.exercise('settling')
        self.assertIsNone(error);self.assertEqual(2,result['state_polls'])
    def test_late_response_rejected(self):
        result,error,_,_=self.exercise('late-response')
        self.assertIsNone(result);self.assertIsInstance(error,TimeoutError)
    def test_unknown_readiness_fails_closed(self):
        result,error,_,_=self.exercise('unknown-service')
        self.assertIsNone(result);self.assertIsInstance(error,runner.OfflineStateError)

    def test_data_preference_is_not_effective_connectivity(self):
        result,error,calls,_=self.exercise('data-preferences-true')
        self.assertIsNone(error);self.assertTrue(result['networking_unavailable'])
        self.assertFalse(result['telephony_preferences_are_offline_requirement'])
        self.assertEqual(0,result['mobile_data_disable_command_exit'])
        self.assertEqual(1,len([c for c in calls if c[0]=='offline-telephony-diagnostic']))
    def test_optional_diagnostics_cannot_replace_or_block_network_proof(self):
        for mode in ('optional-diagnostic-failure','optional-diagnostic-timeout'):
            result,error,calls,_=self.exercise(mode)
            with self.subTest(mode=mode):
                self.assertIsNone(error);self.assertTrue(result['networking_unavailable'])
                self.assertTrue(any(c[0].endswith('-connectivity') for c in calls))
                self.assertEqual(mode=='optional-diagnostic-failure',result['telephony_diagnostic_error'] is not None)


if __name__=='__main__': unittest.main(verbosity=2)
