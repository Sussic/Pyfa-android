"""B09.1 independent module undo/redo through pinned GUI commands and wx processors."""
import argparse
from copy import deepcopy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import (SOURCE_COMMIT, DEPENDENCIES, bootstrap, compare,
    digest_file, logical_database_digest, snapshot, validate_source)


def export(source, database):
    configuration = bootstrap(source, database)
    configuration.gamedataCache = False
    import config
    config.pyfaPath = str(source)
    import eos.db
    from eos.const import FitSystemSecurity, ImplantLocation, FittingModuleState, FittingSlot
    from eos.saveddata.character import Character
    from eos.saveddata.damagePattern import DamagePattern
    from eos.saveddata.fit import Fit
    from eos.saveddata.ship import Ship
    from service.market import Market
    from tools.android_reference.history_oracle import load
    oracle = load(source)
    service, market, commands = oracle['service'], Market.getInstance(), oracle['history_commands']
    base = json.loads((ROOT / 'tools/android_reference/vexor.json').read_text())
    base.pop('edit'); base['drones'] = []
    base['modules'] = [dict(name='Dual 150mm Railgun II', state=state, charge=charge)
        for state, charge in [('OVERHEATED', 'Spike M'), ('ACTIVE', 'Antimatter Charge M')]]
    item = lambda name: eos.db.getItem(name).ID

    def make_fit(name, spec=None):
        spec = deepcopy(base if spec is None else spec)
        fit = Fit(Ship(eos.db.getItem(spec['ship'])), name=name)
        fit.character = Character('Independent all V', defaultLevel=5)
        fit.damagePattern = DamagePattern(emAmount=25, thermalAmount=25, kineticAmount=25, explosiveAmount=25)
        fit.factorReload, fit.targetProfile, fit.implantLocation = False, None, ImplantLocation.FIT
        fit.systemSecurity, fit.pilotSecurity = FitSystemSecurity.HISEC, 0.0
        fit.ignoreRestrictions = spec.get('ignore_restrictions', False)
        for row in spec['modules']:
            fit.modules.append(oracle['ModuleInfo'](item(row['name']), state=FittingModuleState[row['state']],
                chargeID=item(row['charge']) if row.get('charge') else None).toModule())
        eos.db.saveddata_session.add(fit); eos.db.saveddata_session.flush()
        service.getFit(fit.ID); service.fill(fit.ID)
        return fit

    def spec_for(fit):
        result = deepcopy(base)
        result.update(name=fit.name, ship=fit.ship.item.name, ignore_restrictions=fit.ignoreRestrictions,
            modules=[{'empty_slot': FittingSlot(m.slot).name} if m.isEmpty else
                {'name': m.item.name, 'state': FittingModuleState(m.state).name,
                 'charge': m.charge.name if m.charge else None} for m in fit.modules])
        return result

    def history(fit):
        processor = service.getCommandProcessor(fit.ID)
        rows = list(processor.Commands)
        current = processor.GetCurrentCommand()
        cursor = rows.index(current) + 1 if current is not None else 0
        return {'undo_count': cursor, 'redo_count': len(rows)-cursor,
                'can_undo': processor.CanUndo(), 'can_redo': processor.CanRedo()}

    def stats(fit):
        if not fit.calculated: fit.calculateModifiedAttributes()
        result = snapshot(fit)
        result['scan_resolution'] = {'value': fit.ship.getModifiedItemAttr('scanResolution'), 'unit': 'mm'}
        return result

    def report(fit, recipients=()):
        return {'stats': stats(fit), 'modules': [dict(index=i, name=m.item.name,
            state=FittingModuleState(m.state).name, charge=m.charge.name if m.charge else None)
            for i,m in enumerate(fit.modules) if not m.isEmpty],
            'ignore_restrictions': fit.ignoreRestrictions, 'history': history(fit),
            'recent': list(market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules']),
            'recipients': [stats(target) for target in recipients]}

    definitions = [
        ('single-charge', 'set_module_charge', dict(position=0, charge_id=item('Iron Charge M')), 'charges', lambda f: (f.ID,[0],item('Iron Charge M'))),
        ('bulk-charge', 'set_bulk_charges', dict(main_position=0,module_indices=[0,1],scope='SELECTED',charge_id=item('Iron Charge M')), 'charges', lambda f:(f.ID,[0,1],item('Iron Charge M'))),
        ('legacy-charges', 'set_charges', dict(module_indices=[0,1],charge='Iron Charge M'), 'charges', lambda f:(f.ID,[0,1],item('Iron Charge M'))),
        ('bulk-states', 'set_bulk_states', dict(main_position=0,module_indices=[0,1],scope='SELECTED',click='ctrl'), 'states', lambda f:(f.ID,0,[0,1],'ctrl')),
        ('single-state', 'set_module_states', dict(module_indices=[0],state='OFFLINE'), 'states', lambda f:(f.ID,0,[0],'ctrl')),
        ('add', 'add_module', dict(item_id=item('Damage Control II')), 'add', lambda f:(f.ID,item('Damage Control II'))),
        ('replace', 'replace_module', dict(position=0,item_id=item('200mm Railgun II')), 'replace', lambda f:(f.ID,item('200mm Railgun II'),[0])),
        ('remove', 'remove_module', dict(position=0), 'remove', lambda f:(f.ID,[0])),
        ('bulk-remove', 'remove_bulk_modules', dict(main_position=0,module_indices=[0,1],scope='SELECTED'), 'remove', lambda f:(f.ID,[0,1])),
        ('variation', 'change_variation', dict(context='module',position=0,item_id=item('Dual 150mm Railgun I')), 'variation', lambda f:(f.ID,[0],item('Dual 150mm Railgun I'))),
        ('bulk-variation', 'change_bulk_variations', dict(main_position=0,module_indices=[0,1],scope='SELECTED',item_id=item('Dual 150mm Railgun I')), 'variation', lambda f:(f.ID,[0,1],item('Dual 150mm Railgun I'))),
        ('swap', 'swap_modules', dict(from_position=0,to_position=1), 'swap', lambda f:(f.ID,0,1)),
        ('fill-item', 'fill_modules_item', dict(item_id=item('Dual 150mm Railgun II')), 'fill_item', lambda f:(f.ID,item('Dual 150mm Railgun II'))),
        ('fill-clone', 'fill_modules_clone', dict(position=0), 'fill_clone', lambda f:(f.ID,0)),
        ('clone-selected', 'clone_selected_modules', dict(module_indices=[0,1]), 'clone_selected', lambda f:(f,[0,1])),
        ('clone-at', 'clone_module_at', dict(source_position=0), 'clone', None),
        ('restrictions', 'set_fit_restrictions', dict(ignore=True), 'restrictions', lambda f:(f.ID,)),
    ]
    cases = []
    for name, operation, arguments, kind, parameters in definitions:
        fit = make_fit('History ' + name)
        processor = service.getCommandProcessor(fit.ID)
        market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules'] = []
        args = dict(arguments)
        if kind == 'clone':
            destination = next(i for i,m in enumerate(fit.modules) if m.isEmpty and m.slot==fit.modules[0].slot)
            args['destination_position'] = destination
            values = (fit.ID,0,destination)
        else: values = parameters(fit)
        steps = [{'action':'initial','accepted':True,'result':report(fit)}]
        initial = spec_for(fit)
        command = commands[kind](*values)
        for action in ('do','undo','redo','undo','redo'):
            accepted = processor.Submit(command) if action=='do' else getattr(processor, action.title())()
            service.recalc(fit)
            steps.append({'action':action,'accepted':accepted,'result':report(fit)})
            assert accepted, (name, action)
        cases.append({'name':name,'spec':initial,'operation':operation,'arguments':args,'steps':steps})

    # Source reversals must recalculate every linked recipient without touching its inputs.
    projected = deepcopy(base); projected['ship']='Celestis'
    projected['modules']=[dict(name='Remote Sensor Dampener II',state='ACTIVE',charge='Scan Resolution Dampening Script')]*2
    source_fit=make_fit('History projected source',projected)
    recipients=[make_fit('History recipient '+str(i),{**base,'modules':[]}) for i in range(2)]
    for target in recipients:
        target.projectedFitDict[source_fit.ID]=source_fit
        eos.db.saveddata_session.flush(); eos.db.saveddata_session.refresh(source_fit)
        edge=source_fit.getProjectionInfo(target.ID)
        edge.projectionRange,edge.active,edge.amount=0.0,True,1
    service.recalc(source_fit)
    processor=service.getCommandProcessor(source_fit.ID)
    market.serviceMarketRecentlyUsedModules['pyfaMarketRecentlyUsedModules']=[]
    initial=spec_for(source_fit)
    steps=[{'action':'initial','accepted':True,'result':report(source_fit,recipients)}]
    command=commands['states'](source_fit.ID,0,[0,1],'ctrl')
    for action in ('do','undo','redo','undo','redo'):
        accepted=processor.Submit(command) if action=='do' else getattr(processor,action.title())()
        service.recalc(source_fit)
        steps.append({'action':action,'accepted':accepted,'result':report(source_fit,recipients)})
        assert accepted
    cases.append({'name':'projected-states','spec':initial,'recipients':[spec_for(f) for f in recipients],
        'operation':'set_bulk_states','arguments':dict(main_position=0,module_indices=[0,1],scope='SELECTED',click='ctrl'),'steps':steps})

    fit, other = make_fit('History branching'), make_fit('History isolated')
    processor=service.getCommandProcessor(fit.ID)
    branching=[]
    for action, value in [('submit','Iron Charge M'),('undo',None),('noop','Spike M'),
                          ('failed','Damage Control II'),('redo',None),('undo',None),
                          ('submit','Antimatter Charge M'),('redo',None)]:
        if action in ('submit','noop','failed'):
            accepted=processor.Submit(commands['charges'](fit.ID,[0],item(value)))
        else: accepted=getattr(processor,action.title())()
        branching.append({'action':action,'charge':value,'accepted':accepted,'history':history(fit),
                          'other_history':history(other),'text':fit.modules[0].charge.name})
    service.editNotes(fit.ID,'Notes are outside command history — 保持')
    processor.Undo()
    note_preserved=fit.notes
    limited=make_fit('History limit'); limit_processor=service.getCommandProcessor(limited.ID)
    for index in range(101):
        assert limit_processor.Submit(commands['charges'](limited.ID,[0],item('Iron Charge M' if index%2==0 else 'Antimatter Charge M')))
    limit_before=history(limited); undos=0
    while limit_processor.CanUndo():
        assert limit_processor.Undo(); undos+=1
    limit={'before':limit_before,'after':history(limited),'undone':undos,'remaining_charge':limited.modules[0].charge.name}
    assert not any(name.startswith('android_bridge') for name in sys.modules)
    for name,module in list(sys.modules.items()):
        if name.split('.')[0] in ('eos','service','config') and getattr(module,'__file__',None):
            assert Path(module.__file__).resolve().is_relative_to(source),name
    return {'source_commit':SOURCE_COMMIT,'source_files':oracle['source_files'],
        'database_logical_sha256':logical_database_digest(database),'eos_settings':dict(configuration.settings),
        'cases':cases,'branching':branching,'notes_after_undo':note_preserved,'limit':limit,
        'boundary':'Unchanged original GUI/calc Do and Undo, real per-fit wx processors. Selected clone groups original clone commands as one Android user action. Empty spare slots are compared through occupied positions and EOS resources.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','database','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--check',type=Path); parser.add_argument('--worker',action='store_true')
    args=parser.parse_args()
    args.source,args.database,args.output=args.source.resolve(),args.database.resolve(strict=True),args.output.resolve()
    validate_source(args.source)
    compare(DEPENDENCIES,{name:importlib.metadata.version(name) for name in DEPENDENCIES})
    if args.worker:
        args.output.write_text(json.dumps(export(args.source,args.database),indent=2,allow_nan=False)+'\n',encoding='utf-8')
        return
    if args.output.is_relative_to(ROOT): raise ValueError('Use fresh output outside checkout')
    baseline=json.loads((ROOT/'tools/android_reference/fixtures/vexor.json').read_text())
    compare(baseline['database_logical_sha256'],logical_database_digest(args.database))
    before=digest_file(args.database); args.output.mkdir(parents=True,exist_ok=False)
    for name in ('history','repeat'):
        with (args.output/(name+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--source',str(args.source),
                '--database',str(args.database),'--output',str(args.output/(name+'.json')),'--worker'],
                cwd=args.source,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
    actual=json.loads((args.output/'history.json').read_text())
    compare(actual,json.loads((args.output/'repeat.json').read_text()))
    if args.check: compare(json.loads(args.check.read_text()),actual)
    compare(before,digest_file(args.database));validate_source(args.source)
    receipt={'task':'B09.1','source_commit':SOURCE_COMMIT,'database_sha256':before,
        'database_logical_sha256':baseline['database_logical_sha256'],'fresh_process_repeat':True,
        'cases':len(actual['cases']),'states':sum(len(c['steps']) for c in actual['cases']),
        'reference_sha256':digest_file(args.output/'history.json'),'game_database_unchanged':True}
    (args.output/'evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))


if __name__=='__main__': main()

