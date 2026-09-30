"""Unchanged pinned notes service/pane methods with inert control/event ports.

This exercises original save routing and timer requests, not wx rendering or
native TextCtrl newline conversion. EOS, its SQLite commit and copy are real.
"""
import ast
import hashlib
import math
from pathlib import Path
from types import SimpleNamespace


def load(source):
    import wx
    import wx.lib.newevent
    from eos.utils.round import roundToPrec
    from tools.android_reference.module_oracle import load as module_load
    oracle = module_load(source)
    files = oracle['source_files']

    def nodes(relative):
        path = Path(source) / relative
        raw = path.read_bytes()
        files[relative] = hashlib.sha256(raw).hexdigest()
        return path, ast.parse(raw, filename=str(path)).body

    path, definitions = nodes('gui/utils/numberFormatter.py')
    scope = dict(math=math, roundToPrec=roundToPrec)
    selected = [node for node in definitions if isinstance(node, ast.FunctionDef) and node.name == 'formatAmount']
    assert len(selected) == 1
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), scope)
    path, definitions = nodes('gui/builtinAdditionPanes/notesView.py')
    pane = next(node for node in definitions if isinstance(node, ast.ClassDef) and node.name == 'NotesView')
    names = {'fitChanged', 'onText', 'delayedSave', 'getTabExtraText'}
    selected = [node for node in pane.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in selected} == names
    scope.update(wx=wx, Fit=type(oracle['service']),
                 GE=SimpleNamespace(FitNotesChanged=wx.lib.newevent.NewEvent()[0]))
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(path), 'exec'), scope)

    class TextPort:
        value = ''
        def GetValue(self): return self.value
        def ChangeValue(self, value): self.value = value

    class TimerPort:
        pending = None
        def Stop(self): self.pending = None
        def Start(self, milliseconds, one_shot): self.pending = [milliseconds, one_shot]

    class PagePort:
        disabled = True
        def DisablePage(self, pane, value): self.disabled = bool(value)

    frame = wx.EvtHandler()
    active = {'id': None}
    frame.getActiveFit = lambda: active['id']
    page = PagePort()
    view = SimpleNamespace(lastFitId=None, mainFrame=frame, editNotes=TextPort(),
        changeTimer=TimerPort(), Parent=SimpleNamespace(Parent=page))
    event = SimpleNamespace(Skip=lambda: None, fitIDs=[])

    def select(fit):
        active['id'] = fit.ID if fit else None
        event.fitIDs = [active['id']]
        scope['fitChanged'](view, event)

    def type_text(value):
        view.editNotes.value = value
        scope['onText'](view, event)

    def save():
        # A one-shot timer is no longer pending when its callback fires.
        view.changeTimer.pending = None
        scope['delayedSave'](view, event)

    return dict(oracle, select=select, type_text=type_text, save=save, view=view,
        page=page, label=lambda: scope['getTabExtraText'](view), receiver=frame)
