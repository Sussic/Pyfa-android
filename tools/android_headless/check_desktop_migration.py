#!/usr/bin/env python3
"""Exercise the real desktop migration backup after deferring its config import."""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    from android_bridge import HeadlessEngine
    HeadlessEngine(args.database)
    from eos.db import migration
    from sqlalchemy import create_engine
    # Genuine desktop configuration/wx, never a stub. No paths are initialized
    # with defPaths(); only this disposable migration database can be touched.
    import config
    with tempfile.TemporaryDirectory(prefix="pyfa-a03-migration-") as directory:
        saved = Path(directory) / "synthetic.db"
        config.savePath, config.saveDB = directory, str(saved)
        with closing(sqlite3.connect(saved)) as connection:
            connection.execute("CREATE TABLE targetResists (ID INTEGER PRIMARY KEY, name TEXT)")
            connection.execute("INSERT INTO targetResists VALUES (1, 'Synthetic target')")
            connection.execute("PRAGMA user_version=48")
            connection.commit()
        before = saved.read_bytes()
        engine = create_engine("sqlite:///" + saved.as_posix())
        try:
            migration.update(engine)
            assert migration.getVersion(engine) == migration.getAppVersion() == 49
            assert engine.execute("SELECT ID, name, hp FROM targetResists").fetchall() == [(1, "Synthetic target", None)]
            backups = list(Path(directory).glob("saveddata_migration_48-49_*.db"))
            assert len(backups) == 1 and backups[0].read_bytes() == before
            migration.update(engine)
            assert list(Path(directory).glob("saveddata_migration_*.db")) == backups
        finally:
            engine.dispose()
    print('{"result":"PASS","desktop_migration":"48-to-49","backup_preserved":true,"repeat_noop":true}')


if __name__ == "__main__":
    main()
