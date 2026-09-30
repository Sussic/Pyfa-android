"""Exact plain-text notes using EOS storage and the pinned pane availability."""


def validate(text):
    if type(text) is not str:
        raise ValueError('Notes must be text')
    # SQLite and the Android transport require valid Unicode. Never trim,
    # normalize, truncate or replace characters to make an invalid save succeed.
    text.encode('utf-8', errors='strict')


def change(engine, fit, text):
    engine._check_fit(fit)
    validate(text)
    if fit.isStructure:
        raise ValueError('Notes editing is unavailable for structures')
    fit.notes = text


def details(engine, fit):
    engine._check_fit(fit)
    text = fit.notes or ''
    return {'text': text, 'characters': len(text), 'editable': not fit.isStructure}
