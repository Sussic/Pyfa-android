"""Execute unchanged original affector builders against a flat recording tree."""
import ast
from pathlib import Path
from types import SimpleNamespace


def load(source):
    from eos.const import Operator
    from eos.saveddata.mode import Mode
    from eos.saveddata.character import Skill
    from eos.saveddata.implant import Implant
    from eos.saveddata.booster import Booster
    from eos.saveddata.drone import Drone
    from eos.saveddata.fighter import Fighter
    from eos.saveddata.module import Module
    from eos.saveddata.ship import Ship
    from eos.saveddata.citadel import Citadel
    from eos.saveddata.fit import Fit
    path = Path(source) / 'gui/builtinItemStatsViews/itemAffectedBy.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    original = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    namespace = dict(Operator=Operator, Mode=Mode, Skill=Skill, Implant=Implant, Booster=Booster,
                     Drone=Drone, Fighter=Fighter, Module=Module, Ship=Ship, Citadel=Citadel, Fit=Fit,
                     BitmapLoader=SimpleNamespace(getBitmap=lambda *args: None))
    operator = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'formatOperator')
    exec(compile(ast.Module(body=[operator], type_ignores=[]), str(path), 'exec'), namespace)
    names = ('sortAttrDisplayName', 'buildAttributeView', 'buildModuleView')
    for method in original.body:
        if isinstance(method, ast.FunctionDef) and method.name in names:
            exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)

    class Recorder:
        def __init__(self):
            self.paths, self.rows = {0: []}, []

        def AppendItem(self, parent, text, *args):
            index = len(self.paths)
            path = self.paths[parent] + [text]
            self.paths[index] = path
            self.rows.append(dict(key=index, path=path, alternate=None))
            return index

        def SetItemData(self, key, data):
            if isinstance(data, str):
                next(row for row in self.rows if row['key'] == key)['alternate'] = data

    def observe(stuff, item, fit):
        if stuff is None: return dict(source=[], attribute=[])
        result = {}
        for kind, name in (('source', 'buildModuleView'), ('attribute', 'buildAttributeView')):
            recorder = Recorder()
            view = SimpleNamespace(stuff=stuff, item=item, activeFit=fit.ID, showRealNames=False,
                                   treeItems=[], affectedBy=recorder, imageList=SimpleNamespace(Add=lambda *args: 0),
                                   ORDER=[Fit, Ship, Citadel, Mode, Module, Drone, Fighter, Implant, Booster, Skill])
            view.sortAttrDisplayName = lambda name: namespace['sortAttrDisplayName'](view, name)
            namespace[name](view, 0)
            result[kind] = [dict(path=row['path'], alternate=row['alternate']) for row in recorder.rows]
        return result
    return observe
