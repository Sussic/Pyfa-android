"""Guard the oracle against false passes and physical SQLite layout differences."""

import importlib.util
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest


spec = importlib.util.spec_from_file_location(
    "reference", Path(__file__).resolve().parents[1] / "reference.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)


class ComparisonTests(unittest.TestCase):
    def test_allows_only_small_float_noise(self):
        reference.compare({"range": 80000.0}, {"range": 80000.0000001})
        with self.assertRaisesRegex(ValueError, "range"):
            reference.compare({"range": 80000.0}, {"range": 80001.0})

    def test_missing_and_extra_statistics_fail(self):
        for actual in ({}, {"range": 80000.0, "fake": 0}):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                reference.compare({"range": 80000.0}, actual)

    def test_booleans_and_integer_counts_are_exact(self):
        for expected, actual in ((True, 1), (5, 5.0), (5, 6)):
            with self.subTest(expected=expected, actual=actual), self.assertRaises(ValueError):
                reference.compare(expected, actual)

    def test_nonfinite_results_cannot_pass(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                reference.compare(value, value)

    def test_unit_and_input_changes_fail(self):
        for actual in ({"value": 80000.0, "unit": "km"}, {"value": 80.0, "unit": "m"}):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                reference.compare({"value": 80000.0, "unit": "m"}, actual)

    def test_sequence_length_changes_fail(self):
        with self.assertRaises(ValueError):
            reference.compare(["gun", "gun"], ["gun"])


class DatabaseProvenanceTests(unittest.TestCase):
    def test_same_rows_ignore_insertion_order_but_detect_modified_data(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = [Path(folder) / (name + ".db") for name in ("first", "second")]
            for path, rows in zip(paths, ([(1, "a"), (2, "b")], [(2, "b"), (1, "a")])):
                with closing(sqlite3.connect(path)) as db, db:
                    db.execute("CREATE TABLE items (id INTEGER, name TEXT)")
                    db.executemany("INSERT INTO items VALUES (?, ?)", rows)
            first, second = paths
            self.assertNotEqual(reference.digest_file(first), reference.digest_file(second))
            self.assertEqual(reference.logical_database_digest(first),
                             reference.logical_database_digest(second))
            before = reference.digest_file(second)
            reference.logical_database_digest(second)
            self.assertEqual(before, reference.digest_file(second))
            with closing(sqlite3.connect(second)) as db, db:
                db.execute("UPDATE items SET name = 'changed' WHERE id = 2")
            self.assertNotEqual(reference.logical_database_digest(first),
                                reference.logical_database_digest(second))

    def test_missing_database_is_not_silently_created(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "absent.db"
            with self.assertRaises(sqlite3.OperationalError):
                reference.logical_database_digest(path)
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
