"""No EOS imports: execute independent original adaptive/getter boundary AST."""
import ast
from abc import ABCMeta, abstractmethod
import hashlib
import json
import math
import os
from pathlib import Path
import unittest

SOURCE = Path(os.environ['PYFA_REFERENCE_SOURCE'])
PATH = SOURCE / 'graphs/data/base/getter.py'
namespace = dict(math=math, ABCMeta=ABCMeta, abstractmethod=abstractmethod)
nodes = [n for n in ast.parse(PATH.read_bytes()).body if isinstance(n, ast.ClassDef)]
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(PATH), 'exec'), namespace)


class Scalar(namespace['SmoothPointGetter']):
    _baseResolution = 50
    _extraDepth = 2
    def __init__(self, function):
        super().__init__(None); self.function = function; self.calls = []
    def _calculatePoint(self, x, miscParams, src, tgt, commonData):
        self.calls.append(x); return self.function(x)


def sample(function, span):
    scalar = Scalar(function)
    xs, ys = scalar.getRange(span, {}, None, None)
    return scalar, xs, ys


class OriginalAdaptiveTests(unittest.TestCase):
    def test_flat_fifty_intervals(self):
        obj, xs, ys = sample(lambda x: 0, [0.0, 100000.0])
        self.assertEqual(len(xs), 51); self.assertEqual(len(obj.calls), 51)
        self.assertEqual((xs[0], xs[-1]), (0, 100000))
    def test_nonflat_depth_two_ceiling(self):
        obj, xs, ys = sample(lambda x: x, [0.0, 100000.0])
        self.assertEqual(len(xs), 201); self.assertEqual(len(obj.calls), 201)
        self.assertEqual(xs, ys); self.assertEqual(xs, sorted(xs))
    def test_equal_singleton(self):
        obj, xs, ys = sample(lambda x: 4, [13500.0, 13500.0])
        self.assertEqual(xs, [13500.0]); self.assertEqual(ys, [4])
    def test_metre_subnormal_interval_underflows_step(self):
        obj, xs, ys = sample(lambda x: x, [0.0, math.ulp(0.0)])
        self.assertEqual(xs, [0.0])
    def test_near_equal_retains_duplicates(self):
        low = 1e15; high = math.nextafter(low, math.inf)
        obj, xs, ys = sample(lambda x: 0, [low, high])
        self.assertEqual(len(xs), 51); self.assertLess(len(set(xs)), len(xs))
        self.assertTrue(all(a <= b for a, b in zip(xs, xs[1:])))
    def test_refinement_preserves_source_evaluation_order(self):
        obj, xs, ys = sample(lambda x: x, [0.0, 100.0])
        self.assertEqual(obj.calls[:5], [0.0, 2.0, 1.0, 0.5, 1.5])
        self.assertEqual(xs[:5], [0.0, 0.5, 1.0, 1.5, 2.0])
    def test_large_midpoint_overflow_is_source_behavior(self):
        obj, xs, ys = sample(lambda x: x, [1e308, 1.01e308])
        self.assertTrue(any(not math.isfinite(x) for x in xs))
        # Candidate must reject the complete result; no clamp/dedup/source fix.
    def test_actual_null_time_prepare_returns_before_generation(self):
        path = SOURCE / 'graphs/data/fitRemoteReps/cache.py'
        tree = ast.parse(path.read_bytes())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TimeCache')
        node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'prepareRpsData')
        scope = {}; exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
        class Cache:
            def _generateInternalForm(self, **kwargs):
                raise AssertionError('forbidden time generation')
        self.assertTrue(scope['prepareRpsData'](Cache(), object(), True, None))
        with self.assertRaisesRegex(AssertionError, 'forbidden time generation'):
            scope['prepareRpsData'](Cache(), object(), True, 1)


if __name__ == '__main__':
    print('Original source:', PATH, hashlib.sha256(PATH.read_bytes()).hexdigest())
    unittest.main(verbosity=2)
