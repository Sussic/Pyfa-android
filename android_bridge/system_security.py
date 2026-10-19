"""Structure security choices adapted from original fitSystemSecurity commands.

GPL-3.0-or-later; Pyfa contributors, see LICENSE. EOS owns rig modifiers.
"""
CHOICES = (("HISEC", "High Security"), ("LOWSEC", "Low Security"),
           ("NULLSEC", "Null Security"), ("WSPACE", "W-Space"))


def validate(value):
    if type(value) is not str or value not in dict(CHOICES):
        raise ValueError("Choose a supported system security")


def live_name(value):
    from eos.const import FitSystemSecurity
    if type(value) not in (int, FitSystemSecurity):
        raise ValueError("Inherited or invalid system security is not supported by saved fits")
    return FitSystemSecurity(value).name


def details(engine, fit):
    engine._check_fit(fit)
    return dict(is_structure=fit.isStructure, system=live_name(fit.getSystemSecurity()),
                choices=[dict(id=value, label=label) for value, label in CHOICES]
                if fit.isStructure else [])


def change(engine, fit, value):
    engine._check_fit(fit)
    validate(value)
    if not fit.isStructure:
        raise ValueError("System security editing is available for structures")
    from eos.const import FitSystemSecurity
    selected = FitSystemSecurity[value]
    if fit.getSystemSecurity() == selected:
        return
    fit.systemSecurity = selected
    import eos.db
    eos.db.saveddata_session.flush()
    engine._recalculate(fit)
