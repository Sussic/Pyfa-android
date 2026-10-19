"""Pinned itemCompare.py formatting; GPL-3.0-or-later, see LICENSE.
Only desktop metadata service lookups are replaced by EOS DB lookups.
"""
import eos.db
from .number_format import formatAmount

def TranslateValueUnit(value, unitName, unitDisplayName):

    def itemIDCallback():
        item = eos.db.getItem(int(value))
        return '%s (%d)' % (item.name, value) if item is not None else str(value)

    def groupIDCallback():
        group = eos.db.getGroup(int(value))
        return '%s (%d)' % (group.name, value) if group is not None else str(value)

    def attributeIDCallback():
        attribute = eos.db.getAttributeInfo(int(value), eager="unit")
        return '%s (%d)' % (attribute.name.capitalize(), value)
    trans = {'Inverse Absolute Percent': (lambda: (1 - value) * 100, unitName), 'Inversed Modifier Percent': (lambda: (1 - value) * 100, unitName), 'Modifier Percent': (lambda: ('%+.2f' if (value - 1) * 100 % 1 else '%+d') % ((value - 1) * 100), unitName), 'Volume': (lambda: value, 'm³'), 'Sizeclass': (lambda: value, ''), 'Absolute Percent': (lambda: value * 100, unitName), 'Milliseconds': (lambda: value / 1000.0, unitName), 'typeID': (itemIDCallback, ''), 'groupID': (groupIDCallback, ''), 'attributeID': (attributeIDCallback, '')}
    override = trans.get(unitDisplayName)
    if override is not None:
        v = override[0]()
        if isinstance(v, str):
            fvalue = v
        elif isinstance(v, (int, float)):
            fvalue = formatAmount(v, 3, 0, 0)
        else:
            fvalue = v
        return '%s %s' % (fvalue, override[1])
    else:
        return '%s %s' % (formatAmount(value, 3, 0), unitName)
