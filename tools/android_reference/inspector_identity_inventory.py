"""Enumerate every original mode family for saved inspector identity validation."""
import argparse
import json
import importlib.metadata
from pathlib import Path
import sqlite3
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare, digest_file, logical_database_digest, validate_source


def inventory(source, database):
    source=source.resolve();database=database.resolve(strict=True);validate_source(source)
    compare(DEPENDENCIES,{name:importlib.metadata.version(name) for name in DEPENDENCIES})
    logical=logical_database_digest(database)
    compare('5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607',logical)
    configuration=bootstrap(source,database);configuration.gamedataCache=False
    import config
    config.pyfaPath=str(source)
    import eos.db
    from eos.saveddata.ship import Ship
    assert Path(sys.modules[Ship.__module__].__file__).resolve()==(source/'eos/saveddata/ship.py').resolve()
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        candidates=db.execute("SELECT t.typeID,t.typeName FROM invtypes t JOIN invgroups g ON g.groupID=t.groupID WHERE g.name='Tactical Destroyer' OR t.typeName='Anhinga' ORDER BY t.typeID").fetchall()
    families=[]
    for identity,name in candidates:
        original=Ship(eos.db.getItem(identity))
        choices=[item.ID for item in original.modeItems or ()]
        assert choices and len(choices)==len(set(choices))
        families.append(dict(id=identity,name=name,choices=choices))
    assert len(families)==len({row['name'] for row in families})
    return dict(sourceCommit=SOURCE_COMMIT,databaseLogicalSha256=logical,
                sourceFiles={'eos/saveddata/ship.py':digest_file(source/'eos/saveddata/ship.py')},modeFamilies=families)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=inventory(args.source,args.database)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Original mode families:',len(result['modeFamilies']))
