"""Pinned original Unit-method witnesses, separate from the candidate adapter.

This isolates original scalar unit methods with object as the unused EqBase.
It is not a full EOS, database, wx, Android or fitting-parity qualification.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess

PIN='8b04f3b271e614b3e103853b44a7851a63d79d0e'
CASES=[
    {'name':None,'label':None,'raw':0.125,'minimum':0.0625,'maximum':0.25,'base':0.125},
    {'name':'Metres','label':'m','raw':1250.0,'minimum':1000.0,'maximum':1500.0,'base':1200.0},
    {'name':'Volume','label':'m3','raw':12.0,'minimum':8.0,'maximum':16.0,'base':10.0},
    {'name':'Absolute Percent','label':'%','raw':0.125,'minimum':0.0625,'maximum':0.25,'base':0.125},
    {'name':'Modifier Percent','label':'%','raw':1.125,'minimum':1.0625,'maximum':1.25,'base':1.125},
    {'name':'Inverse Absolute Percent','label':'%','raw':0.875,'minimum':0.75,'maximum':0.9375,'base':0.875},
    {'name':'Inversed Modifier Percent','label':'%','raw':0.875,'minimum':0.75,'maximum':0.9375,'base':0.875},
    {'name':'Milliseconds','label':'s','raw':1250.0,'minimum':1000.0,'maximum':1500.0,'base':1250.0},
    {'name':'Metres','label':'m','raw':-10.0,'minimum':-8.0,'maximum':-12.0,'base':-10.0},
    {'name':'Metres','label':'m','raw':1.25,'minimum':1.0,'maximum':2.0,'base':0.5},
    {'name':'Absolute Percent','label':'%','raw':0.0,'minimum':0.0,'maximum':0.0,'base':0.0},
]

def load_unit(reference):
    trust=['git','-c','safe.directory='+reference.resolve().as_posix()]
    commit=subprocess.check_output(trust+['rev-parse','HEAD'],cwd=reference,text=True).strip()
    if commit!=PIN: raise RuntimeError('Wrong independent reference commit')
    if subprocess.check_output(trust+['status','--porcelain=v1','--','eos/gamedata.py'],cwd=reference).strip():
        raise RuntimeError('Independent Unit source has uncommitted changes')
    path=reference/'eos/gamedata.py'
    raw=path.read_bytes();tree=ast.parse(raw.decode('utf-8-sig'))
    node=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='Unit')
    namespace={'EqBase':object}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),namespace)
    return namespace['Unit'],{'commit':commit,'source':str(path),
        'source_sha256':hashlib.sha256(raw).hexdigest(),
        'unit_ast_sha256':hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),
        'qualification':'Original scalar Unit methods with unused EqBase substituted by object; no full EOS/wx/database proof'}

def unit_for(cls,name,label):
    if name is None: return None
    value=cls();value.name=name;value.displayName=label;return value

def observe(cls,case):
    unit=unit_for(cls,case['name'],case['label'])
    simplify=(lambda value:value) if unit is None else unit.SimplifyValue
    complicate=(lambda value:value) if unit is None else unit.ComplicateValue
    low,high=sorted([case['minimum'],case['maximum']])
    anchor=max(low,min(high,case['base']))
    raw=[case['raw'],low,high,anchor]
    display=[simplify(value) for value in raw]
    label=None if unit is None else unit.PreformatValue(case['raw'])[1]
    return {'inputs':case,'raw':raw,'display':display,
            'roundtrip':[complicate(value) for value in display],
            'display_unit':label,'endpoint_order_reversed':display[1]>display[2]}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();cls,provenance=load_unit(args.reference)
    result={'reference':provenance,'observations':[observe(cls,case) for case in CASES]}
    with args.output.open('x',encoding='utf-8') as stream: json.dump(result,stream,indent=2)
