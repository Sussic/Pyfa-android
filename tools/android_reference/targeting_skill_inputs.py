"""Independent original EOS skill-input witness for C03.1 summary verification.

This companion is a host-side expected-input oracle, not Android test data.
The original targeting fixture, packaged bytes and reported hashes stay unchanged.
"""
import argparse,hashlib,importlib.metadata,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.android_reference.reference import SOURCE_COMMIT,DEPENDENCIES,bootstrap,compare,digest_file,logical_database_digest,validate_source


def export(source,database):
    configuration=bootstrap(source,database);configuration.gamedataCache=False
    import eos.db
    from eos.saveddata.character import Character
    fixture_path=ROOT/'tools/android_reference/fixtures/targeting.json'
    raw=fixture_path.read_bytes();fixture=json.loads(raw)
    compare(fixture['eos_settings'],dict(configuration.settings));assert configuration.settings['strictSkillLevels'] is True
    rows=[]
    for index,case in enumerate(fixture['cases']):
        character=Character('Independent targeting skill inputs',defaultLevel=case['spec']['skill_level'])
        for edit in case['edits']:
            if edit['operation']=='set_skill_level':
                args=edit['args'];character.getSkill(eos.db.getItem(args['skill'])).setLevel(args['level'])
        skills={skill.item.name:skill.activeLevel for skill in character.skills if skill.activeLevel!=case['spec']['skill_level']}
        rows.append(dict(case=index,spec=case['spec'],edits=case['edits'],skills=skills))
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name,module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos','service','gui','config') and getattr(module,'__file__',None):assert Path(module.__file__).resolve().is_relative_to(source),name
    return dict(task='C03.1',source_commit=SOURCE_COMMIT,eos_settings=dict(configuration.settings),
        database_logical_sha256=logical_database_digest(database),
        targeting_fixture_normalized_sha256=hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest(),
        character_source_sha256=hashlib.sha256((source/'eos/saveddata/character.py').read_bytes().replace(b'\r\n',b'\n')).hexdigest(),cases=rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--check',type=Path);parser.add_argument('--worker',action='store_true');args=parser.parse_args()
    args.source=args.source.resolve();args.database=args.database.resolve(strict=True);args.output=args.output.resolve()
    validate_source(args.source);compare(DEPENDENCIES,{name:importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source,args.database),indent=2,allow_nan=False)+'\n',encoding='utf-8');return
    assert not args.output.is_relative_to(ROOT);args.output.mkdir(parents=True,exist_ok=False)
    before=digest_file(args.database)
    for name in ('targeting-skill-inputs','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),'--database',str(args.database),
                '--output',str(args.output/(name+'.json')),'--worker'],cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
    actual=json.loads((args.output/'targeting-skill-inputs.json').read_text(encoding='utf-8'));compare(actual,json.loads((args.output/'repeat.json').read_text(encoding='utf-8')))
    if args.check:compare(json.loads(args.check.read_text(encoding='utf-8')),actual)
    compare(before,digest_file(args.database));validate_source(args.source)
    receipt=dict(task='C03.1',host_only=True,source_commit=SOURCE_COMMIT,fresh_process_repeat=True,game_database_unchanged=True,database_sha256=before,
        cases=len(actual['cases']),witness_sha256=digest_file(args.output/'targeting-skill-inputs.json'))
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt))


if __name__=='__main__':main()
