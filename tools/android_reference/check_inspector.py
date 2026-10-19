#!/usr/bin/env python3
"""Retained local inspector reference regeneration/repeat and separate host checks."""
import argparse
import hashlib
import gzip
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.android_reference.reference import DEPENDENCIES, SOURCE_COMMIT, compare, logical_database_digest, validate_source

FAMILIES = ('inventory', 'attributes', 'metadata', 'units', 'affectors', 'properties',
            'projection', 'command', 'equipment_paths', 'equipment_probes', 'guard_domains', 'effect_catalog', 'identities', 'sorting', 'text', 'contexts', 'affector_metadata', 'context_metadata')
REFERENCE_ONLY = ('inventory', 'sorting', 'text', 'contexts')


def fixture_bytes(path):
    content = path.read_bytes()
    return gzip.decompress(content) if path.suffix == '.gz' else content


def command(family, action, database, fixture, source=None):
    if family in REFERENCE_ONLY and action != 'export': raise ValueError('This family requires native comparison, not a host substitute')
    script = 'inspector_links' if family in ('projection', 'command') else 'inspector_' + family
    args = [sys.executable, '-I', str(ROOT / f'tools/android_reference/{script}.py')]
    if family == 'inventory':
        if action != 'export': raise ValueError('Inventory is an independent enumeration, not an implementation verifier')
        args += ['--output', str(fixture)]
        args += ['--identity-check', str(ROOT / 'tools/android_reference/fixtures/inspector-mode-identities.json')]
    else: args += [action, '--fixture', str(fixture)]
    args += ['--database', str(database)]
    if source is not None: args += ['--source', str(source)]
    if family in ('projection', 'command'): args += ['--kind', family]
    return args


def run(args):
    if sys.version_info[:2] != (3, 11): raise ValueError('Use installed pinned Python3.11')
    expected_path = ROOT / f'tools/android_reference/fixtures/inspector-{args.family.replace("_", "-")}.json'
    if args.family in ('contexts', 'affector_metadata'): expected_path = expected_path.with_suffix('.json.gz')
    expected = json.loads(fixture_bytes(expected_path))
    compare(SOURCE_COMMIT, expected.get('sourceCommit', expected.get('source_commit')))
    compare(logical_database_digest(args.database), expected['databaseLogicalSha256'])
    args.output.mkdir(parents=True, exist_ok=False)
    database_bytes = hashlib.sha256(args.database.read_bytes()).hexdigest()
    if args.kind == 'reference':
        if args.source is None: raise ValueError('Reference checks require the independent source')
        validate_source(args.source)
        compare(DEPENDENCIES, {name: importlib.metadata.version(name) for name in DEPENDENCIES})
        for name in ('fixture', 'repeat'):
            output = args.output / (name + ('.json.gz' if args.family in ('contexts', 'affector_metadata') else '.json'))
            with (args.output / (name + '.log')).open('wb') as log:
                subprocess.run(command(args.family, 'export', args.database, output, args.source),
                               cwd=args.source, stdout=log, stderr=subprocess.STDOUT, check=True)
            compare(expected, json.loads(fixture_bytes(output)), args.family + '.' + name)
    else:
        if args.family in REFERENCE_ONLY: raise ValueError('No fabricated headless implementation gate')
        with (args.output / 'verify.log').open('wb') as log:
            subprocess.run(command(args.family, 'verify', args.database, expected_path), cwd=ROOT,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
    compare(database_bytes, hashlib.sha256(args.database.read_bytes()).hexdigest(), 'unchanged_database_bytes')
    result = dict(schema=1, family=args.family, kind=args.kind, source_commit=SOURCE_COMMIT,
                  database_logical_sha256=expected['databaseLogicalSha256'], database_sha256=database_bytes,
                  expected_fixture_sha256=hashlib.sha256(fixture_bytes(expected_path).replace(b'\r\n', b'\n')).hexdigest(),
                  fresh_reference_repeat=args.kind == 'reference', implementation_comparison=args.kind == 'headless')
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'PASS inspector {args.kind}:{args.family}; retained outputs/logs at {args.output}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', required=True, choices=('reference', 'headless'))
    parser.add_argument('--family', required=True, choices=FAMILIES)
    parser.add_argument('--database', required=True, type=Path); parser.add_argument('--source', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(); args.database = args.database.resolve(); args.output = args.output.resolve()
    if args.source is not None: args.source = args.source.resolve()
    run(args)


if __name__ == '__main__': main()
