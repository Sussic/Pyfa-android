"""Explicit inspector phase order and retained device artifact requirements."""
from inspection_instrumentation import CLASS, ALL_PHASES

IDENTITY_PHASES = {f'identity-{phase}': (CLASS, ('repeatedModuleTargetsFollowReorderAndRejectRemovalOffline',))
                   for phase in ('prepare', 'restored1', 'restored2')}
PHASES = ('canonical', 'canonical-restored1', 'canonical-restored2',
          *IDENTITY_PHASES,
          *(phase for part in range(5) for phase in (f'contexts{part}', f'contexts{part}-restored1', f'contexts{part}-restored2')),
          'linked', 'ui')
STARTS = {'canonical', 'identity-prepare', *(f'contexts{part}' for part in range(5)), 'linked', 'ui'}
SCREENSHOTS = tuple(sorted(
    [f'pyfa-c032-ui-{name}.png' for name in ('identity', 'moved', 'removed', 'restored', 'variation',
                                           'ship', 'raw-search-copy', 'recreated', 'affectors', 'equipment', 'charge')] +
    [f'pyfa-c032-ui-{kind}-{mode}-{view}.png' for kind in ('projection', 'command')
     for mode in ('source', 'attribute') for view in ('owner', 'fitted-source')]))


def methods(phase):
    return (IDENTITY_PHASES if phase in IDENTITY_PHASES else ALL_PHASES)[phase]


def selector(phase):
    owner, names = methods(phase)
    return ','.join(owner + '#' + name for name in names)


def arguments(phase):
    if phase in IDENTITY_PHASES: return ('c032_identity_phase', phase.removeprefix('identity-'))
    return ('c032_phase', phase)


def artifacts(phase):
    assert phase in PHASES
    if phase.startswith('canonical'):
        return ('files/c032-canonical-observations-state.json', 'files/c032-canonical-observations.jsonl')
    if phase.startswith('contexts'):
        stem = phase.split('-restored')[0]
        return (f'files/c032-{stem}-state.json', f'files/c032-{stem}-observations.jsonl')
    if phase.startswith('identity-'):
        return (f'/sdcard/Download/pyfa-c032-{phase}.json',)
    if phase == 'linked': return tuple(f'files/c032-linked-{kind}.json' for kind in ('projection', 'command'))
    return tuple('/sdcard/Download/' + name for name in SCREENSHOTS)


def previous(phase):
    assert phase in PHASES
    if phase in STARTS: return None
    index = PHASES.index(phase)
    return PHASES[index - 1]
