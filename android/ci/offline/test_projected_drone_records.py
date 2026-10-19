"""Pure projected-input validation, independent of numerical admission."""
import unittest
from android_bridge.projected_drone_records import validate


class ProjectedDroneRecordValidation(unittest.TestCase):
    def test_exact_schema_quantities_and_ranges(self):
        row = dict(name='Light Armor Maintenance Bot I', amount=2**31-1,
                   active=0, range_m=None)
        validate([])
        validate([row])  # Inactive quantity is valid input, not evaluation admission.
        for field, values in {
            'amount': (True, 0, -1, 2**31, 1.5),
            'active': (True, -1, 2**31, 1.5),
            'range_m': (True, -1, float('inf'), float('nan'), 2**53+1, 10**400),
            'name': ('', 'x'*513, None),
        }.items():
            for value in values:
                with self.subTest(field=field, value=str(value)), self.assertRaises(ValueError):
                    validate([{**row, field: value}])
        for invalid in (None, {}, [row, row], [{**row, 'mutation': {}}],
                        [{k:v for k,v in row.items() if k != 'range_m'}]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate(invalid)
        for value in (0, -0.0, 63.7, 5e-324, 2**53, 2**53+2):
            validate([{**row, 'range_m': value}])


if __name__ == '__main__':
    unittest.main()
