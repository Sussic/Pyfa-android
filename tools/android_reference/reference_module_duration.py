"""Deferred original-EOS reference fixture for fixed module399 duration73.

Adapted from frozen tools/android_reference/c10_module_rolls.py. Run only as a
separately admitted reference worker. No adapter/candidate observations supply
expectations. The fresh raw output is private supporting evidence, not acceptance.
"""
import argparse
import hashlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import site
import sqlite3
import struct
import sys


SOURCE_COMMIT = '8b04f3b271e614b3e103853b44a7851a63d79d0e'
UNIT_SOURCE_SHA256 = 'adf4053bc624f1be3ae83625246fb36f88fc3c38854c374f4803c7a4830a7072'
DATABASE_SHA256 = 'e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065'
DATABASE_LOGICAL_SHA256 = '5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607'
HELPER_SHA256 = '292b550ddb4552d74c87116ba82d12d828584f0a175913027cc17d2297f4ec20'
REFERENCE_PREFIX = Path(r'C:\Users\HallT\OneDrive\Desktop\Documents\PyfaDevelopment\.venv\reference')
LAUNCHER_SHA256 = '21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082'
BASE_ITEM_ID, MUTAPLASMID_ID, RESULT_ITEM_ID = 399, 47778, 47781
ATTRIBUTE_ID, UNIT_ID = 73, 101
ATTRIBUTE_IDS = (6, 30, 50, 68, 73)
UNIT_REL_TOL, UNIT_ABS_TOL = 1e-12, 1e-12
FORBIDDEN_IMPORTS = frozenset(('android_bridge', 'gui', 'service'))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def scalar_identity(value):
    if not finite(value):
        raise ValueError('Original EOS raw scalar is nonfinite or nonnumeric')
    return {'type': type(value).__name__,
            'encoding': value.hex() if type(value) is float else str(value)}


def exact_scalar(actual, expected):
    if scalar_identity(actual) != scalar_identity(expected):
        raise ValueError('Original EOS changed an intended raw scalar type or bits')


class NoAdapter(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.attempts = []

    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in FORBIDDEN_IMPORTS:
            self.attempts.append(fullname)
            raise ImportError('C10 reference must not import adapter/desktop modules: ' + fullname)


def reference_runtime(reference):
    prefix = REFERENCE_PREFIX.resolve(strict=True)
    executable = (prefix / 'Scripts/python.exe').resolve(strict=True)
    if (sys.version_info[:3] != (3, 11, 9) or struct.calcsize('P') * 8 != 64 or
            Path(sys.prefix).resolve() != prefix or sys.prefix == sys.base_prefix or
            Path(sys.executable).resolve() != executable or digest(executable) != LAUNCHER_SHA256 or
            not sys.flags.isolated or not sys.dont_write_bytecode or site.ENABLE_USER_SITE):
        raise ValueError('Use the pinned isolated reference venv Python3.11.9 x64 with -I -B')
    versions = {name: importlib.metadata.version(name) for name in reference.DEPENDENCIES}
    if versions != reference.DEPENDENCIES:
        raise ValueError('Use the established pinned desktop reference dependencies')
    roots = {name: Path(importlib.metadata.distribution(name).locate_file('')).resolve()
             for name in reference.DEPENDENCIES}
    if any(not root.is_relative_to(prefix / 'Lib/site-packages') for root in roots.values()):
        raise ValueError('Reference dependency metadata escaped its qualified venv')
    base = Path(sys._base_executable).resolve(strict=True)
    return versions, dict(version=list(sys.version_info[:3]), bits=64,
        executable=str(executable), launcher_sha256=LAUNCHER_SHA256,
        prefix=str(prefix), base_prefix=sys.base_prefix, base_executable=str(base),
        base_sha256=digest(base), isolated=True, dont_write_bytecode=True,
        user_site_enabled=site.ENABLE_USER_SITE,
        distribution_roots={name: str(root) for name, root in roots.items()})


def no_config_override(source):
    # configforced.py is ignored by Git, so a clean checkout alone is not enough.
    paths = (source / 'configforced.py', source / 'configforced.pyc', source / 'configforced')
    if ('configforced' in sys.modules or any(path.exists() or path.is_symlink() for path in paths) or
            importlib.machinery.PathFinder.find_spec('configforced', [str(source), *sys.path]) is not None):
        raise ValueError('Original reference must have no configforced override')


def wx_library_observation():
    # Original config.py imports real wx and constructs wx.Colour objects. This
    # library dependency is allowed; starting a desktop application is not.
    import wx
    root = (REFERENCE_PREFIX / 'Lib/site-packages/wx').resolve(strict=True)
    if wx.__version__ != '4.2.1' or wx.GetApp() is not None:
        raise ValueError('Use real pinned wx4.2.1 without a wx application')
    files = {}
    for name, module in list(sys.modules.items()):
        if name.split('.')[0] == 'wx' and getattr(module, '__file__', None):
            path = Path(module.__file__).resolve(strict=True)
            if not path.is_relative_to(root):
                raise ValueError('wx library import escaped the qualified reference venv: ' + name)
            files[str(path)] = digest(path)
    module_path = Path(wx.__file__).resolve(strict=True)
    core_file = getattr(sys.modules.get('wx._core'), '__file__', None)
    core = None if core_file is None else Path(core_file).resolve(strict=True)
    if (str(module_path) not in files or core is None or core.suffix.lower() != '.pyd' or
            str(core) not in files):
        raise ValueError('Authentic wx package/native core were not loaded')
    return dict(version=wx.__version__, module=str(module_path),
                module_sha256=files[str(module_path)], native_core_file=str(core),
                native_core_sha256=files[str(core)], loaded_files=files, app_is_none=True)


def export(source, database, helper_path):
    """Derive the complete baseline and duration-only target from original EOS."""
    if any(name.split('.')[0] in FORBIDDEN_IMPORTS | {'eos', 'utils', 'config', 'staticdata', 'wx', 'configforced'}
           for name in sys.modules):
        raise ValueError('Reference generation requires a fresh process')
    barrier = NoAdapter()
    sys.meta_path.insert(0, barrier)
    producer = Path(__file__).resolve(strict=True)
    producer_pin = digest(producer)
    unit_source = source / 'eos/gamedata.py'
    if (digest(database) != DATABASE_SHA256 or digest(helper_path) != HELPER_SHA256 or
            digest(unit_source) != UNIT_SOURCE_SHA256):
        raise ValueError('Frozen original reference database/helper/Unit identity differs')
    spec = importlib.util.spec_from_file_location('_c10_pinned_reference_helper', helper_path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    if reference.SOURCE_COMMIT != SOURCE_COMMIT:
        raise ValueError('Wrong original reference helper commit')
    versions, runtime = reference_runtime(reference)
    reference.validate_source(source)
    no_config_override(source)
    network_attempts = []

    def no_network(event, arguments):
        # Local gethostname can be used by logging; it does not create a socket
        # or resolve a remote host. Refuse socket creation, communication and DNS.
        if event in ('socket.__new__', 'socket.connect', 'socket.bind', 'socket.sendto',
                     'socket.sendmsg', 'socket.getaddrinfo', 'socket.gethostbyname',
                     'socket.gethostbyaddr', 'socket.getnameinfo'):
            network_attempts.append(event)
            raise RuntimeError('C10 reference calculation is offline')
    sys.addaudithook(no_network)
    wx_before = wx_library_observation()

    uri = database.as_uri() + '?mode=ro'

    def readonly_connection():
        connection = sqlite3.connect(uri, uri=True)
        connection.execute('PRAGMA query_only=ON')
        return connection

    connection = readonly_connection()
    try:
        pair = connection.execute(
            'SELECT m.typeID,m.resultingTypeID FROM mutaplasmidItems AS a '
            'JOIN mutaplasmids AS m ON m.typeID=a.typeID '
            'WHERE a.applicableTypeID=? AND m.typeID=? AND m.resultingTypeID=?',
            (BASE_ITEM_ID, MUTAPLASMID_ID, RESULT_ITEM_ID)).fetchall()
    finally:
        connection.close()
    if pair != [(MUTAPLASMID_ID, RESULT_ITEM_ID)]:
        raise ValueError('Pinned database does not contain the exact fixed compatible pair')
    configuration = reference.bootstrap(source, database)
    if configuration.saveddata_connectionstring != 'sqlite:///:memory:':
        raise ValueError('Original EOS must select in-memory saveddata before eos.db import')
    configuration.gamedata_connectionstring = readonly_connection
    configuration.gamedataCache = False
    import eos.db
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship
    import config as desktop_config

    initializers = (desktop_config.defPaths, desktop_config.defLogging)
    state_observations = []

    def reference_state(stage):
        no_config_override(source)
        if (any(getattr(desktop_config, name) is not None
                for name in ('savePath', 'saveDB', 'logging_setup')) or desktop_config.configforced is not None or
                configuration.saveddata_connectionstring != 'sqlite:///:memory:' or
                eos.db.saveddata_engine.url.drivername != 'sqlite' or
                eos.db.saveddata_engine.url.database != ':memory:' or
                eos.db.saveddata_session.bind is not eos.db.saveddata_engine):
            raise ValueError('Reference profile/logging must remain uninitialized and saveddata in memory')
        functions = (desktop_config.defPaths, desktop_config.defLogging)
        if (functions != initializers or any(function.__module__ != 'config' or
                Path(function.__code__.co_filename).resolve() != source / 'config.py' for function in functions)):
            raise ValueError('Original profile/logging initializer functions must not be replaced')
        wx = wx_library_observation()
        state_observations.append(dict(stage=stage, savePath=None, saveDB=None, logging_setup=None,
            configforced_absent=True, saveddata_database=':memory:', initializers_unchanged=True,
            wx_app_is_none=wx['app_is_none']))
        return wx

    reference_state('before_fit')

    base = eos.db.getItem(BASE_ITEM_ID)
    mutaplasmid = eos.db.getDynamicItem(MUTAPLASMID_ID)
    if (base is None or base.name != 'Small Shield Booster I' or mutaplasmid is None or
            mutaplasmid.resultingItem.ID != RESULT_ITEM_ID or
            mutaplasmid.resultingItem.name != 'Small Abyssal Shield Booster'):
        raise ValueError('Reference module identities do not resolve exactly')
    pattern = dict(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
    fit = Fit(Ship(eos.db.getItem('Rifter')), name='C10 independent module399 duration73')
    fit.character = Character('Independent synthetic all-V', defaultLevel=5)
    fit.damagePattern = DamagePattern(**pattern)
    fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
    fit.systemSecurity, fit.pilotSecurity, fit.ignoreRestrictions = FitSystemSecurity.HISEC, 0.0, False
    module = Module(mutaplasmid.resultingItem, baseItem=base, mutaplasmid=mutaplasmid)
    if tuple(sorted(module.mutators)) != ATTRIBUTE_IDS or not module.isValidState(FittingModuleState.ACTIVE):
        raise ValueError('Selected authentic module cannot exercise the fixed active full roll set')
    module.state, module.owner = FittingModuleState.ACTIVE, fit
    fit.modules.append(module)
    eos.db.saveddata_session.add(fit)
    eos.db.saveddata_session.flush()

    def capture(name, **state_metadata):
        eos.db.saveddata_session.flush()
        fit.clear()
        fit.calculateModifiedAttributes()
        reference_state(name)
        if tuple(sorted(module.mutators)) != ATTRIBUTE_IDS:
            raise ValueError('Original EOS must retain the complete fixed five-attribute roll set')
        if (fit.ignoreRestrictions or module.state != FittingModuleState.ACTIVE or
                not module.isValidState(FittingModuleState.ACTIVE) or not module.fits(fit) or not fit.fits):
            raise ValueError('Reference mutated module does not fit the selected hull in ACTIVE state')
        metrics = reference.snapshot(fit)
        if len(metrics) != 38:
            raise ValueError('Preserve the complete independent38-field reference snapshot')
        for used, output in (('cpu_used', 'cpu_output'), ('powergrid_used', 'powergrid_output')):
            if (not finite(metrics[used]['value']) or not finite(metrics[output]['value']) or
                    not 0 <= metrics[used]['value'] <= metrics[output]['value']):
                raise ValueError('Reference module exceeds actual EOS CPU/power output')
        rolls = [dict(attribute_id=key, value=mutator.value)
                 for key, mutator in sorted(module.mutators.items())]
        identities = [dict(attribute_id=row['attribute_id'], **scalar_identity(row['value'])) for row in rolls]
        return dict(name=name, attributes=rolls, raw_identity=identities,
                    metrics=metrics, **state_metadata)

    baseline_requests = {}
    for key, mutator in sorted(module.mutators.items()):
        requested = mutator.minValue + (mutator.maxValue - mutator.minValue) * 0.25
        if not finite(requested):
            raise ValueError('Original EOS baseline roll is not finite')
        mutator.value = requested
        exact_scalar(mutator.value, requested)
        baseline_requests[key] = requested
    baseline = capture('baseline', fraction=0.25)
    for row in baseline['attributes']:
        exact_scalar(row['value'], baseline_requests[row['attribute_id']])
    old = {row['attribute_id']: row['value'] for row in baseline['attributes']}
    duration = module.mutators[ATTRIBUTE_ID]
    low, high, base_value = duration.minValue, duration.maxValue, duration.baseValue
    if not all(finite(value) for value in (low, high, base_value)) or not low < high:
        raise ValueError('Original EOS duration endpoints are not finite and ordered')
    target_raw = high
    if scalar_identity(target_raw) == scalar_identity(old[ATTRIBUTE_ID]):
        raise ValueError('Original EOS endpoint must change the baseline duration')
    attribute = duration.attribute
    info = getattr(attribute, 'info', attribute)
    unit = getattr(attribute, 'unit', None) or getattr(info, 'unit', None)
    if (getattr(info, 'unitID', None) != UNIT_ID or unit is None or unit.name != 'Milliseconds' or
            type(duration.highIsGood) is not bool or duration.highIsGood):
        raise ValueError('Original EOS duration unit/direction identity differs')
    displayed = unit.SimplifyValue(target_raw)
    inverse = unit.ComplicateValue(displayed)
    if (not finite(displayed) or not finite(inverse) or displayed == target_raw or
            not math.isclose(inverse, target_raw, rel_tol=UNIT_REL_TOL, abs_tol=UNIT_ABS_TOL)):
        raise ValueError('Original Unit did not qualify a nonidentity numeric endpoint round trip')
    formatted = unit.PreformatValue(target_raw)
    if not isinstance(formatted, tuple) or len(formatted) != 2 or formatted[1] != 's':
        raise ValueError('Original EOS duration display label differs')
    unit_observation = dict(attribute_id=ATTRIBUTE_ID, unit_id=UNIT_ID, unit_name=unit.name,
        unit_label=formatted[1], higher_is_better=False, endpoint='maximum',
        raw_baseline=old[ATTRIBUTE_ID], raw_minimum=low, raw_maximum=high, raw_base=base_value,
        display_baseline=unit.SimplifyValue(old[ATTRIBUTE_ID]),
        display_minimum=unit.SimplifyValue(low), display_maximum=unit.SimplifyValue(high),
        display_target=displayed, inverse=inverse,
        inverse_exact=scalar_identity(inverse) == scalar_identity(target_raw),
        inverse_within_tolerance=True,
        roundtrip_tolerance=dict(relative=UNIT_REL_TOL, absolute=UNIT_ABS_TOL))
    duration.value = target_raw
    exact_scalar(duration.value, target_raw)
    target = capture('duration_only_target', endpoint='maximum', changed_attribute_id=ATTRIBUTE_ID)
    for row in target['attributes']:
        exact_scalar(row['value'], target_raw if row['attribute_id'] == ATTRIBUTE_ID else old[row['attribute_id']])
    for state in (baseline, target):
        cap = state['metrics']['capacitor_used']
        if cap['unit'] != 'GJ/s' or not finite(cap['value']) or cap['value'] <= 0:
            raise ValueError('Reference ACTIVE module has no finite positive capacitor use')
    if baseline['metrics']['capacitor_used'] == target['metrics']['capacitor_used']:
        raise ValueError('Original duration-only change did not change EOS capacitor use')
    wx_after = reference_state('after_target')

    imported = {}
    for name, loaded in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'utils', 'config', 'staticdata') and getattr(loaded, '__file__', None):
            path = Path(loaded.__file__).resolve()
            if not path.is_relative_to(source):
                raise ValueError('Reference import escaped pinned source: ' + name)
            imported[path.relative_to(source).as_posix()] = digest(path)
    reference.validate_source(source)
    inputs = {str(producer): producer_pin, str(helper_path): HELPER_SHA256,
              str(database): DATABASE_SHA256, str(unit_source): UNIT_SOURCE_SHA256}
    for observation in (wx_before, wx_after):
        for path, pin in observation['loaded_files'].items():
            if path in inputs and inputs[path] != pin:
                raise ValueError('Actual wx library input changed during qualification')
            inputs[path] = pin
    for name, pin in imported.items():
        path = str(source / name)
        if path in inputs and inputs[path] != pin:
            raise ValueError('Imported original source differs from its explicit pin')
        inputs[path] = pin
    if (barrier.attempts or network_attempts or any(digest(path) != pin for path, pin in inputs.items()) or
            any(name.split('.')[0] in FORBIDDEN_IMPORTS for name in sys.modules)):
        raise ValueError('Reference isolation/source/helper/producer/database preservation failed')
    return dict(ticket='C10', schema=1, case_id='module399-duration73',
        status='QUALIFIED_INDEPENDENT_REFERENCE_FIXTURE', source_commit=SOURCE_COMMIT,
        source_files=imported, input_sha256=inputs, database_sha256=DATABASE_SHA256,
        database_logical_sha256=DATABASE_LOGICAL_SHA256, helper_sha256=HELPER_SHA256,
        producer_sha256=producer_pin, dependencies=versions, runtime=runtime,
        python_version=sys.version, python_executable=sys.executable,
        platform=sys.platform, sqlite_version=sqlite3.sqlite_version,
        eos_settings=dict(configuration.settings), base_item_id=BASE_ITEM_ID,
        mutaplasmid_id=MUTAPLASMID_ID, resulting_item_id=RESULT_ITEM_ID,
        states=[baseline, target], unit_observation=unit_observation,
        initial_spec=dict(name=fit.name, ship='Rifter', skill_level=5, factor_reload=False,
            damage_pattern=pattern, target_profile=None, security=dict(system='HISEC', pilot=0.0),
            implants=[], boosters=[], projections=[], commands=[], environments=[], drones=[],
            modules=[dict(name=module.item.name, state='ACTIVE', mutation=dict(
                base_item_id=BASE_ITEM_ID, mutaplasmid_id=MUTAPLASMID_ID, attributes=baseline['attributes']))]),
        adapter_imported=False, gui_or_service_imported=False, wx_library_imported=True,
        wx_library=dict(before=wx_before, after=wx_after), reference_state_observations=state_observations,
        forbidden_import_attempts=barrier.attempts,
        network_attempts=network_attempts, inputs_preserved=True,
        omitted_raw_scalars_exact=True, candidate_acceptance=False, native_acceptance=False,
        limits=['One fixed module399/47778/47781 and duration73 endpoint only',
                'Private original-reference output; no old oracle replacement',
                'No candidate, Android, process-restart or parent-job-closure proof'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'helper', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    source, database, helper = (getattr(args, name).resolve(strict=True)
                                for name in ('source', 'database', 'helper'))
    output = args.output.resolve()
    producer = Path(__file__).resolve(strict=True)
    # The work-only copy lives in a dedicated scratch directory, not a source
    # checkout. A normal tools/android_reference copy still protects its tree.
    producer_root = (producer.parents[2] if producer.parent.name == 'android_reference'
                     and producer.parent.parent.name == 'tools' else producer.parent)
    protected_roots = (source, producer_root, helper.parents[2])
    if (output.exists() or any(output.is_relative_to(root) for root in protected_roots) or
            output in (database, helper, producer)):
        raise ValueError('Use a fresh private external JSON output; preserve all source/input files')
    value = export(source, database, helper)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
