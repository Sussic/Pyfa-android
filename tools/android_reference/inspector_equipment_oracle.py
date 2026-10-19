"""Run unchanged pinned equipment methods with explicit desktop lookup bindings."""
import ast
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import eos.config
    import eos.db
    from eos.saveddata.mode import Mode
    from eos.utils.float import floatUnerr
    from eos.utils.spoolSupport import SpoolType, SpoolOptions
    from gui.utils.numberFormatter import formatAmount, roundToPrec
    from gui.utils.listFormatter import formatList
    from service.market import Market
    namespace = dict(eos=eos, Mode=Mode, floatUnerr=floatUnerr, SpoolType=SpoolType,
                     SpoolOptions=SpoolOptions, formatAmount=formatAmount, roundToPrec=roundToPrec,
                     formatList=formatList, Market=Market)
    methods = {}
    for filename, wanted in (('misc.py', ('__getData',)), ('maxRange.py', ('getText', 'getToolTip')),
                             ('capacitorUse.py', ('getText', 'getToolTip')),
                             ('attributeDisplay.py', ('getText',)), ('propertyDisplay.py', ('getText',))):
        path = Path(source) / 'gui/builtinViewColumns' / filename
        tree = ast.parse(path.read_text(encoding='utf-8'))
        if filename == 'capacitorUse.py':
            assignment = next(node for node in tree.body if isinstance(node, ast.Assign) and
                              any(isinstance(target, ast.Name) and target.id == 'regenGroups' for target in node.targets))
            exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(path), 'exec'), namespace)
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
        for method in cls.body:
            if isinstance(method, ast.FunctionDef) and method.name in wanted:
                exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
                methods[filename + ':' + method.name] = namespace[method.name]

    def observe(stuff, fit, effective=False):
        if stuff is None or type(stuff).__name__ not in ('Module', 'Drone', 'Fighter', 'Booster', 'Mode'):
            return None
        # The original UI service supplies the currently selected fit. Bind
        # that lookup only; every EOS and presentation method runs unchanged.
        namespace['Fit'] = SimpleNamespace(getInstance=lambda: SimpleNamespace(getFit=lambda identity: fit))
        view = SimpleNamespace(fittingView=SimpleNamespace(getActiveFit=lambda: fit.ID),
                               mainFrame=SimpleNamespace(statsPane=SimpleNamespace(nameViewMap={
                                   'resistancesViewFull': SimpleNamespace(showEffective=effective)})))
        misc = methods['misc.py:__getData'](view, stuff)
        result = dict(misc=None if misc is None else dict(display=misc[0], detail=misc[1]),
                      range=None, capacitor=None, effective=effective)
        if hasattr(stuff, 'falloff'):
            result['range'] = dict(display=methods['maxRange.py:getText'](view, stuff),
                                   detail=methods['maxRange.py:getToolTip'](view, stuff))
        if hasattr(stuff, 'capUse'):
            result['capacitor'] = dict(display=methods['capacitorUse.py:getText'](view, stuff),
                                       detail=methods['capacitorUse.py:getToolTip'](view, stuff))
        return result

    observe.methods = methods
    return observe
