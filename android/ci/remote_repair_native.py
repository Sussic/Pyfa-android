"""Opt-in G05.2 phase under the existing native_suite owner and outer r12 guard.

No standalone execution, provisioning, resource admission or runtime manager.
Three class calls remain subject to the owner's unchanged 1,200-second deadline.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from types import MappingProxyType

PHASE = 'remote_repair_graph'
PREFIX = 'io.github.sussic.pyfa.'
PACKAGE = PREFIX + 'dev'
SOURCE_DIR = Path(__file__).resolve().parents[1] / 'app/src/androidTest/java/io/github/sussic/pyfa'
METHODS = MappingProxyType({
    'OfflineRemoteRepairContractTest': (
        'requestDefaultsFixedUnitsNullTimeAndSourceRatesAreDistinctAndFrozen',
        'allFourOriginalShapesAndDecreasingOrNonmonotoneRatesAreAccepted',
        'singletonRepeatedRoundedBasesAndEndpointDriftArePreserved',
        'signedZeroEqualityDoesNotInventRefinement',
        'missingMidpointsForeignCoordinatesAndWrongYPredicatesFailCompletely',
        'finiteBaseCurveAllowsUnusedOverflowButInfinityNeverMatchesAnOptionalCoordinate',
        'strictIdentityOrderSchemaAssumptionEchoAndTotalsRejectCorruption',
        'failuresHaveNoPartialSeriesAndUnknownCodesAreProtocolFailures',
        'finiteMetreNormalizationAndBoundedRequestValidationHaveNoInventedDistanceCeiling',
        'selectedTimeUsesV2AndPreservesRequestedTimeAndCurrentSourceRates',
        'selectedTimeStrictEchoKeysTypesAndVersionCannotAcceptAStaleCurrentResult',
        'selectedTimeRetainsAll201SamplesFitOrderAndWholeRequestFailures',
        'amountRequiresFiniteExplicitTimeAndPreservesUnitsClampsAndSourceRates',
        'amountRejectsRateEchoWrongUnitsNullBooleanTimeAndRelaxedDistanceShapes',
        'amountKeepsAdaptiveCoordinatesOrderAndCompleteFailureEnvelopes',
        'bothTimeOrdinatesPreserveClampedRequestsNullZeroAndSourceRates',
        'timeOriginalOvershootsDuplicatesAndOnePointWindowsAreNotDistanceGrids',
        'timeStrictEchoTypesModeOrderAndMalformedStepRunsFailClosed',
        'timeCeilingsCoverWholeRequestAndRawTextBeforeParsing',
        'timeRequestRejectsWrongSecondaryInputsAndKeepsNegativeOrderedEndpoints',
        'genericLargeIntegerChangesSurviveJsonAndGraphDoublePrecisionLoss',
        'boundedGenericIntegerParserKeepsStrictGrammarAndIdentityIntegerTypes',
    ),
    'OfflineRemoteRepairModelTest': (
        'cancelRepeatedPlotAndLeaveKeepOneWorkerUntilItsActualCompletion',
        'everyGraphInputInvalidatesPendingAndCompletedSamplesButKeepsDrafts',
        'revisionContextDeletionAndUnavailableCallbacksCannotPublishStaleResults',
        'synchronizationRetainsCanceledGateSelectionsAndDraftsAcrossSourceEditAndDeletion',
        'failureAndSynchronousLaunchFailureReleaseOnlyTheirOwnCompletedGate',
        'clearingViewModelCancelsWithoutPublishingALateCallback',
        'duplicateNamesRemainReachableByPageWhileSearchAndEmptySelectionAreRetained',
        'invalidDraftsNeverQueueWorkAndCanBeCorrectedWithoutLosingSelection',
        'selectedTimeDraftEditsCancelBackAndLateCompletionKeepActualWorkerOwnership',
        'invalidSelectedTimesNeverCoerceToZeroOrLoseDraftAndSelection',
        'amountBlankAndInvalidDraftsNeverLaunchAndExplicitZeroDoes',
        'ordinateSwitchAndSwitchBackInvalidateCallbacksWithoutReleasingWorkerOrDrafts',
        'axisSwitchRetainsIndependentDraftsAndOwnsBusyWorkerAcrossAllModes',
        'timeAxisIgnoresRetainedInvalidSecondaryTimeButRejectsInvalidDistanceAndRange',
        'timePlotBoundsRetainTerminalBackwardsAndInitialOnlyOvershootOrder',
    ),
    'OfflineRemoteRepairUiTest': (
        'actualSourceStateEditReturnUndoRecreationAndReadOnlyComparisonUseCurrentRevisions',
        'ancillaryControlChangesAppliedCurveWithoutRelabelingSourceLayerRates',
        'selectedTimeLabelsClampingSourceRatesAndDraftsSurviveBackAndRecreation',
        'amountControlRequiresTimeLabelsHpAndRetainsModeDraftSelectionAcrossNavigation',
        'timeAxisBothOrdinatesRetainIndependentDraftsAndRenderOriginalOrderAcrossRecreation',
    ),
})


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selectors(cls):
    return tuple(PREFIX + cls + '#' + method for method in METHODS[cls])


def instrumentation_args(cls):
    return ('shell', 'am', 'instrument', '-w', '-r', '-e', 'class',
            ','.join(selectors(cls)), '-e', 'offline_features_phase', PHASE,
            PACKAGE + '.test/' + PREFIX + 'DiagnosticTestRunner')


def source_bindings():
    """Bind current source bytes; exact candidate provenance belongs to the owner."""
    bindings = {}
    for cls, expected in METHODS.items():
        path = SOURCE_DIR / (cls + '.kt')
        require(path.is_file(), 'G05.2 test source missing: ' + cls)
        raw = path.read_bytes()
        source = raw.decode('utf-8')
        require(re.search(r'^package io\.github\.sussic\.pyfa\s*$', source, re.M),
                'Wrong G05.2 source package: ' + cls)
        require(re.search(r'^class ' + re.escape(cls) + r'\s*\{', source, re.M),
                'Wrong G05.2 source class: ' + cls)
        actual = re.findall(r'^\s*@Test\s+fun\s+(\w+)\s*\(', source, re.M)
        require(len(actual) == len(expected) and set(actual) == set(expected),
                'G05.2 test source inventory differs: ' + cls)
        key = 'android/app/src/androidTest/java/io/github/sussic/pyfa/' + path.name
        bindings[key] = hashlib.sha256(raw).hexdigest()
    return bindings


def helpers():
    spec = importlib.util.spec_from_file_location(
        'remote_repair_helpers', Path(__file__).with_name('check-drones.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_output(cls, output):
    require(__debug__, 'Python optimization disables required instrumentation assertions')
    helpers().passed(output, set(selectors(cls)))
    require(len(re.findall(r'^OK \(\d+ tests?\)\s*$', output, re.M)) == 1,
            'Duplicate instrumentation completion')


def run(command, evidence, expected_avd, apks, install):
    """Use caller-owned serial transport and APK setup; never claim a full pass."""
    require(__debug__, 'Python optimization disables required instrumentation assertions')
    require(isinstance(expected_avd, str) and
            re.fullmatch(r'pyfa-local-[A-Za-z0-9-]+-c04', expected_avd),
            'Owned C04 profile required')
    evidence = Path(evidence)
    require(not evidence.exists(), 'Retain existing phase evidence; use a fresh run')
    sources = source_bindings()
    require(len(apks) == 2 and all(Path(p).is_file() for p in apks),
            'Source-bound APK setup missing')
    hashes = {package: hashlib.sha256(Path(apk).read_bytes()).hexdigest()
              for package, apk in zip((PACKAGE, PACKAGE + '.test'), apks)}
    evidence.mkdir(parents=True)
    require(command('identity-avd', 'emu', 'avd', 'name').splitlines()[0] == expected_avd,
            'Wrong owned AVD')
    for label, prop, expected in (('qemu', 'ro.kernel.qemu', '1'),
                                  ('api', 'ro.build.version.sdk', '36'),
                                  ('abi', 'ro.product.cpu.abi', 'x86_64')):
        require(command('identity-' + label, 'shell', 'getprop', prop).strip() == expected,
                'Wrong emulator ' + label)
    for package in hashes:
        require('package:' + package not in command(
            'prior-' + package, 'shell', 'pm', 'list', 'packages', package).splitlines(),
            'Refusing existing installation; preserve its app data')
    offline = helpers().require_offline(command)
    install()
    for package, expected in hashes.items():
        paths = command('installed-' + package, 'shell', 'pm', 'path', package).splitlines()
        require(len(paths) == 1 and
                re.fullmatch(r'package:/data/app/[A-Za-z0-9_./=+~-]+\.apk', paths[0]),
                'Unexpected APK path')
        actual = command('apk-hash-' + package, 'shell', 'sha256sum', paths[0][8:]).split()
        require(len(actual) == 2 and actual[0] == expected,
                'Installed APK differs from built input')
        require(command('internet-' + package, 'shell', 'cmd', 'package',
                        'check-permission', 'android.permission.INTERNET',
                        package, '0').strip() == 'denied', 'INTERNET not confirmed denied')
    phases = []
    for cls in METHODS:
        output = command(cls, *instrumentation_args(cls), timeout=900)
        validate_output(cls, output)
        log = evidence / (cls + '.log')
        require(log.is_file(), 'Retained instrumentation log missing: ' + cls)
        raw = log.read_bytes()
        require(raw.decode('utf-8', errors='replace') == output,
                'Retained instrumentation log differs from validated output: ' + cls)
        phases.append({'class': cls, 'methods': list(selectors(cls)),
                       'output_log': log.name, 'output_sha256': hashlib.sha256(raw).hexdigest()})
    require(source_bindings() == sources, 'G05.2 test sources changed during phase')
    result = {'phase': PHASE, 'native_executions': 42, 'phases': phases,
              'test_source_sha256': sources, 'apk_sha256': hashes, 'offline': offline,
              'development_only': True, 'full_delivery': False,
              'restart_qualified': False, 'screenshots_reviewed': False,
              'other_cloud_native_gates_complete': False}
    (evidence / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
