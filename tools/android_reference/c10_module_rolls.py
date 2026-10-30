"""Unexecuted C10 reference producer for one existing rolled local module.

Run only as a separately admitted reference worker. This never imports the
Android adapter, reads its observations, or updates an existing expected file.
No expected numeric result exists until authentic pinned EOS has produced it.
"""
import argparse
import hashlib
import importlib.abc
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import sys


DATABASE_SHA256 = 'e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065'
DATABASE_LOGICAL_SHA256 = '5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607'
HELPER_SHA256 = '292b550ddb4552d74c87116ba82d12d828584f0a175913027cc17d2297f4ec20'
BASE_ITEM_ID = 438  # Existing equipment fixture: 1MN Afterburner II.


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class NoAdapter(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] == 'android_bridge':
            raise ImportError('C10 reference must not import the adapter')


def export(source, database, helper_path):
    """Derive both roll sets and observations exclusively from original EOS."""
    if sys.version_info[:2] != (3, 11):
        raise ValueError('Use the existing Python 3.11 reference environment')
    if any(name.split('.')[0] in ('android_bridge', 'eos', 'utils', 'config')
           for name in sys.modules):
        raise ValueError('Reference generation requires a fresh process')
    sys.meta_path.insert(0, NoAdapter())
    if digest(database) != DATABASE_SHA256 or digest(helper_path) != HELPER_SHA256:
        raise ValueError('Frozen reference database/helper identity differs')
    spec = importlib.util.spec_from_file_location('_c10_pinned_reference_helper', helper_path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    versions = {name: importlib.metadata.version(name) for name in reference.DEPENDENCIES}
    if versions != reference.DEPENDENCIES:
        raise ValueError('Use the established pinned desktop reference environment')
    # Existing reference validation requires clean desktop commit 8b04f3b...;
    # the dirty product checkout cannot substitute for that source.
    reference.validate_source(source)
    network_attempts = []

    def no_network(event, arguments):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.bind'):
            network_attempts.append(event)
            raise RuntimeError('C10 reference calculation is offline')
    sys.addaudithook(no_network)

    uri = database.as_uri() + '?mode=ro'
    connection = sqlite3.connect(uri, uri=True)
    try:
        # Select for one fixed base item; the database query plan is unverified.
        pair = connection.execute(
            'SELECT m.typeID,m.resultingTypeID FROM mutaplasmidItems AS a '
            'JOIN mutaplasmids AS m ON m.typeID=a.typeID '
            'WHERE a.applicableTypeID=? ORDER BY m.typeID,m.resultingTypeID LIMIT 1',
            (BASE_ITEM_ID,)).fetchone()
    finally:
        connection.close()
    if pair is None:
        raise ValueError('Pinned database has no compatible mutaplasmid for base 438')
    configuration = reference.bootstrap(source, database)
    configuration.gamedata_connectionstring = lambda: sqlite3.connect(uri, uri=True)
    configuration.gamedataCache = False
    import eos.db
    from eos.const import FittingModuleState, FitSystemSecurity, ImplantLocation
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship

    base = eos.db.getItem(BASE_ITEM_ID)
    mutaplasmid = eos.db.getDynamicItem(pair[0])
    if (base is None or base.name != '1MN Afterburner II' or mutaplasmid is None or
            mutaplasmid.resultingItem.ID != pair[1]):
        raise ValueError('Reference module identities do not resolve exactly')
    pattern = dict(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
    fit = Fit(Ship(eos.db.getItem('Rifter')), name='C10 existing rolled afterburner')
    fit.character = Character('Independent synthetic all-V', defaultLevel=5)
    fit.damagePattern = DamagePattern(**pattern)
    fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
    fit.systemSecurity, fit.pilotSecurity, fit.ignoreRestrictions = FitSystemSecurity.HISEC, 0.0, False
    module = Module(mutaplasmid.resultingItem, baseItem=base, mutaplasmid=mutaplasmid)
    if not module.mutators or not module.isValidState(FittingModuleState.ACTIVE):
        raise ValueError('Selected authentic module cannot exercise active exact rolls')
    module.state, module.owner = FittingModuleState.ACTIVE, fit
    fit.modules.append(module)
    eos.db.saveddata_session.add(fit)
    eos.db.saveddata_session.flush()
    states = []
    for fraction in (0.25, 0.75):
        rolls = []
        for key, mutator in sorted(module.mutators.items()):
            requested = mutator.minValue + (mutator.maxValue - mutator.minValue) * fraction
            if not math.isfinite(requested):
                raise ValueError('Reference roll is not finite')
            mutator.value = requested
            if mutator.value != requested:
                raise ValueError('Original EOS changed an intended exact roll')
            rolls.append(dict(attribute_id=key, value=mutator.value))
        eos.db.saveddata_session.flush()
        fit.clear()
        fit.calculateModifiedAttributes()
        if not fit.fits:
            raise ValueError('Reference mutated module does not fit the selected hull')
        states.append(dict(fraction=fraction, attributes=rolls,
                           metrics=reference.snapshot(fit)))
    if (states[0]['attributes'] == states[1]['attributes'] or
            states[0]['metrics']['max_velocity'] == states[1]['metrics']['max_velocity']):
        raise ValueError('Reference case does not exercise a changed calculation')
    imported = {}
    for name, loaded in list(sys.modules.items()):
        if name.split('.')[0] in ('eos', 'utils') and getattr(loaded, '__file__', None):
            path = Path(loaded.__file__).resolve()
            if not path.is_relative_to(source):
                raise ValueError('Reference import escaped pinned source: ' + name)
            imported[path.relative_to(source).as_posix()] = digest(path)
    if network_attempts or digest(database) != DATABASE_SHA256:
        raise ValueError('Reference isolation/database preservation failed')
    return dict(ticket='C10',schema=1,source_commit=reference.SOURCE_COMMIT,
        source_files=imported,database_sha256=DATABASE_SHA256,
        database_logical_sha256=DATABASE_LOGICAL_SHA256,helper_sha256=HELPER_SHA256,
        producer_sha256=digest(Path(__file__)),dependencies=versions,
        python_version=sys.version,python_executable=sys.executable,
        platform=sys.platform,sqlite_version=sqlite3.sqlite_version,
        eos_settings=dict(configuration.settings),base_item_id=BASE_ITEM_ID,
        mutaplasmid_id=pair[0],resulting_item_id=pair[1],states=states,
        initial_spec=dict(name=fit.name,ship='Rifter',skill_level=5,factor_reload=False,
            damage_pattern=pattern,target_profile=None,security=dict(system='HISEC',pilot=0.0),
            implants=[],boosters=[],projections=[],commands=[],environments=[],drones=[],
            modules=[dict(name=module.item.name,state='ACTIVE',mutation=dict(
                base_item_id=BASE_ITEM_ID,mutaplasmid_id=pair[0],attributes=states[0]['attributes']))]),
        adapter_imported=False,network_attempts=network_attempts,native_acceptance=False,
        limits=['One module/base/mutaplasmid pair only','No Android or process-restart proof',
                'Independent oracle generation alone is not candidate acceptance'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'database', 'helper', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    source, database, helper = (getattr(args, name).resolve(strict=True)
                                for name in ('source', 'database', 'helper'))
    output = args.output.resolve()
    protected_roots = (source, Path(__file__).resolve().parents[2], helper.parents[2])
    if (output.exists() or any(output.is_relative_to(root) for root in protected_roots)
            or output == database or output == helper):
        raise ValueError('Use a fresh external JSON output; preserve all source/input files')
    value = export(source, database, helper)
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
