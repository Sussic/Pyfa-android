"""Record executed original equipment returns without modifying method bodies."""
import ast
from functools import cache
from pathlib import Path
import sys


@cache
def return_lines(method):
    tree = ast.parse(Path(method.__code__.co_filename).read_text(encoding='utf-8'))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                    and node.name == method.__name__)
    return sorted(node.lineno for node in ast.walk(function) if isinstance(node, ast.Return))


def observe_returns(call, methods):
    codes = {method.__code__: (name, return_lines(method)) for name, method in methods.items()}
    seen, last_line = set(), {}

    def trace(frame, event, arg):
        if frame.f_code in codes:
            if event == 'line': last_line[id(frame)] = frame.f_lineno
            elif event == 'return':
                name, returns = codes[frame.f_code]
                line = last_line.pop(id(frame), None)
                if line in returns: seen.add(name + ':' + str(returns.index(line)))
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        value = call()
    finally:
        sys.settrace(previous)
    return dict(value=value, returns=sorted(seen))


def original_factory(source):
    from tools.android_reference.inspector_equipment_oracle import load
    observe = load(source)
    return lambda stuff, item, fit: [observe_returns(lambda: observe(stuff, fit, effective), observe.methods)
                                    for effective in (False, True)]


def android_observe(stuff, item, fit):
    from android_bridge.inspection import equipment
    from android_bridge.inspection_equipment import EquipmentColumns
    methods = {name: getattr(EquipmentColumns, method) for name, method in (
        ('misc.py:__getData', 'misc'), ('maxRange.py:getText', 'range_text'),
        ('maxRange.py:getToolTip', 'range_tooltip'), ('capacitorUse.py:getText', 'capacitor_text'),
        ('capacitorUse.py:getToolTip', 'capacitor_tooltip'), ('attributeDisplay.py:getText', 'attribute_text'),
        ('propertyDisplay.py:getText', 'property_text'))}
    return [observe_returns(lambda: equipment(stuff, fit, effective), methods) for effective in (False, True)]
