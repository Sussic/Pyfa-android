"""Protect the complete original C03.2 presentation paths during isolation."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PINNED = ROOT / 'build/reference-upstream'


def method(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    methods = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(methods) != 1:
        raise AssertionError(f'Expected one {name}: {path}')
    return methods[0]


class PresentationSourceTests(unittest.TestCase):
    def test_all_affector_tree_and_operator_bodies_are_original(self):
        for name in ('formatOperator', 'sortAttrDisplayName', 'buildAttributeView', 'buildModuleView'):
            with self.subTest(method=name):
                self.assertEqual(ast.dump(method(PINNED / 'gui/builtinItemStatsViews/itemAffectedBy.py', name)),
                                 ast.dump(method(ROOT / 'android_bridge/inspection_affectors.py', name)))

    def test_every_equipment_method_preserves_original_ast(self):
        for file, mapping in (
            ('misc.py', {'__getData': 'misc'}),
            ('maxRange.py', {'getText': 'range_text', 'getToolTip': 'range_tooltip'}),
            ('capacitorUse.py', {'getText': 'capacitor_text', 'getToolTip': 'capacitor_tooltip'}),
            ('attributeDisplay.py', {'getText': 'attribute_text'}),
            ('propertyDisplay.py', {'getText': 'property_text'}),
        ):
            for original_name, mobile_name in mapping.items():
                with self.subTest(file=file, method=mobile_name):
                    expected = method(PINNED / 'gui/builtinViewColumns' / file, original_name)
                    expected.name = mobile_name
                    original = ast.unparse(expected)
                    original = original.replace('Fit.getInstance().getFit(self.fittingView.getActiveFit())', 'self.fit')
                    original = original.replace('Market.getInstance().getItem(typeID)', 'eos.db.getItem(int(typeID))')
                    expected = ast.parse(original).body[0]
                    actual = method(ROOT / 'android_bridge/inspection_equipment.py', mobile_name)
                    self.assertEqual(ast.dump(expected), ast.dump(actual))

    def test_comparison_preserves_original_ast_and_service_numeric_id_coercion(self):
        expected = method(PINNED / 'gui/builtinItemStatsViews/itemCompare.py', 'TranslateValueUnit')
        expected.decorator_list = []
        original = ast.unparse(expected)
        original = original.replace('Market.getInstance().getItem(value)', 'eos.db.getItem(int(value))')
        original = original.replace('Market.getInstance().getGroup(value)', 'eos.db.getGroup(int(value))')
        original = original.replace('Attribute.getInstance().getAttributeInfo(value)', 'eos.db.getAttributeInfo(int(value), eager="unit")')
        self.assertEqual(ast.dump(ast.parse(original).body[0]),
                         ast.dump(method(ROOT / 'android_bridge/inspection_compare.py', 'TranslateValueUnit')))

    def test_full_grouping_body_is_original(self):
        original = ast.parse((PINNED / 'gui/builtinItemStatsViews/attributeGrouping.py').read_text(encoding='utf-8'))
        actual = ast.parse((ROOT / 'android_bridge/inspection_groups.py').read_text(encoding='utf-8'))
        # Omit only the source service import and the isolated module's
        # provenance/local enum declaration; all grouping statements remain.
        original.body = original.body[1:]
        actual.body = actual.body[3:]
        self.assertEqual(ast.dump(original), ast.dump(actual))


if __name__ == '__main__':
    unittest.main()
