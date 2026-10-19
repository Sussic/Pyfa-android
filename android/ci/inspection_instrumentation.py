"""Explicit inspector phase membership and fail-closed runner event validation."""
import re

CLASS = 'io.github.sussic.pyfa.InspectionTest'
UI_CLASS = 'io.github.sussic.pyfa.InspectionUiTest'
CANONICAL = (
    'repeatedModuleTargetsFollowReorderAndRejectRemovalOffline',
    'originalGuardDomainsCrossNativeWorkerOffline',
    'completeEquipmentProbesCrossNativeWorkerOffline',
    'everyUnitDefinitionMatchesOriginalFormattingOffline',
    'canonicalAttributesCrossNativeWorkerOffline',
    'completeBaseEffectsAndVariationsCrossNativeWorkerOffline',
    'originalComparisonSortSequencesUseNativeUiHelperOffline',
    'everyAssignedEffectCrossNativeWorkerOffline',
)
LINKED = ('everyOriginalLinkedInspectionStateAndHistoryReversalOffline',)
UI = (
    'projectedAndCommandSourceButtonsResolveOriginalFittedOwnersOffline',
    'selectedObjectRefreshRemovalReversalAndVariationNavigationOffline',
    'descriptionsAndTraitsMatchOriginalHtmlWindowText',
    'originalShipValuesSearchCopyAndRecreationOffline',
)
PHASES = {'canonical': (CLASS, CANONICAL), 'linked': (CLASS, LINKED),
          'ui': (UI_CLASS, UI)}
CONTEXT_METHODS = ('completeFittedModesCargoAndImplantsOffline',
                   'completeFittedBoosterShapesFirstQuarterOffline',
                   'completeFittedBoosterShapesSecondQuarterOffline',
                   'completeFittedBoosterShapesThirdQuarterOffline',
                   'completeFittedBoosterShapesFourthQuarterOffline')
PHASES.update({f'contexts{index}': (CLASS, (method,)) for index, method in enumerate(CONTEXT_METHODS)})
RESTORED_PHASES = {phase: (CLASS, ('canonicalAttributesCrossNativeWorkerOffline',))
                   for phase in ('canonical-restored1', 'canonical-restored2')}
CONTEXT_RESTORED_PHASES = {f'contexts{index}-restored{restart}': (CLASS, (method,))
                         for index, method in enumerate(CONTEXT_METHODS) for restart in (1, 2)}
ALL_PHASES = {**PHASES, **RESTORED_PHASES, **CONTEXT_RESTORED_PHASES}
TIMEOUT_SECONDS = 900


def selector(phase):
    classname, methods = ALL_PHASES[phase]
    return ','.join(classname + '#' + method for method in methods)


def validate(output, phase, selected=None):
    """Require exactly one start/pass pair per selected method, with no skips."""
    classname, methods = ALL_PHASES[phase] if selected is None else selected
    expected = {classname + '.' + method for method in methods}
    count = str(len(expected))
    assert not re.search(r'FAILURES!!!|INSTRUMENTATION_FAILED|shortMsg=|INSTRUMENTATION_ABORTED', output)
    label = 'test' if count == '1' else 'tests'
    assert re.findall(r'^OK \((\d+) ' + label + r'\)\s*$', output, re.M) == [count]
    assert re.findall(r'^INSTRUMENTATION_CODE: (-?\d+)\s*$', output, re.M) == ['-1']
    fields, started, passed = {}, {}, set()
    for line in output.splitlines():
        match = re.match(r'^INSTRUMENTATION_STATUS: ([\w]+)=(.*)$', line)
        if match:
            key, value = match.groups()
            assert key not in fields, ('duplicate event field', key)
            fields[key] = value
        match = re.match(r'^INSTRUMENTATION_STATUS_CODE: (-?\d+)\s*$', line)
        if not match:
            continue
        code = int(match.group(1))
        assert code in (0, 1), fields
        assert fields.get('id') == 'AndroidJUnitRunner' and fields.get('numtests') == count
        name = fields['class'] + '.' + fields['test']
        current = fields['current']
        assert name in expected
        if code == 1:
            assert name not in started and name not in passed
            assert current not in started.values()
            started[name] = current
        else:
            assert name in started and name not in passed and started[name] == current
            passed.add(name)
        fields = {}
    assert not fields, 'Incomplete runner event'
    assert passed == expected and set(started.values()) == {str(n) for n in range(1, len(expected) + 1)}
    return sorted(passed)
