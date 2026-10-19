"""Original pinned affector grouping, counts, ordering and presentation.

Copyright (C) Pyfa contributors. GPL-3.0-or-later; see LICENSE.
The original formatOperator and both tree-builder bodies remain unchanged.
Only desktop tree/image bindings are replaced by recording value objects.
"""
from types import SimpleNamespace
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
BitmapLoader = SimpleNamespace(getBitmap=lambda *args: None)

def formatOperator(operator, stackingGroup, preResAmount, postResAmount):
    opMap = {Operator.PREASSIGN: '=', Operator.PREINCREASE: '+', Operator.MULTIPLY: '*', Operator.POSTINCREASE: '+', Operator.FORCE: '≣'}
    prefix = ''
    if stackingGroup is not None:
        prefix += 's'
    if preResAmount != postResAmount:
        prefix += 'r'
    return '{}{}'.format(prefix, opMap[operator])

class AffectorViews:
    ORDER = [Fit, Ship, Citadel, Mode, Module, Drone, Fighter, Implant, Booster, Skill]

    def sortAttrDisplayName(self, attr):
        info = self.stuff.item.attributes.get(attr)
        if info and info.displayName:
            return info.displayName
        return attr

    def buildAttributeView(self, root):
        """
        We first build a usable dictionary of items. The key is either a fit
        if the afflictions stem from a projected fit, or self.stuff if they
        are local afflictions (everything else, even gang boosts at this time)
        The value of this is yet another dictionary in the following format:

        "attribute name": {
              "Module Name": [
                   class of affliction,
                   affliction item (required due to GH issue #335)
                   modifier type
                   amount of modification
                   whether this affliction was projected
              ]
        }
        """
        attributes = self.stuff.itemModifiedAttributes if self.item == self.stuff.item else self.stuff.chargeModifiedAttributes
        container = {}
        for attrName in attributes.iterAfflictions():
            if attributes[attrName] == attributes.getOriginal(attrName, 0):
                continue
            for fit, afflictors in attributes.getAfflictions(attrName).items():
                for afflictor, operator, stackingGroup, preResAmount, postResAmount, used in afflictors:
                    if not used or afflictor.item is None:
                        continue
                    if fit.ID != self.activeFit:
                        if fit not in container:
                            container[fit] = {}
                        items = container[fit]
                    else:
                        if self.stuff not in container:
                            container[self.stuff] = {}
                        items = container[self.stuff]
                    if attrName not in items:
                        items[attrName] = []
                    if afflictor == self.stuff and getattr(afflictor, 'charge', None):
                        item = afflictor.charge
                    else:
                        item = afflictor.item
                    items[attrName].append((type(afflictor), afflictor, item, formatOperator(operator, stackingGroup, preResAmount, postResAmount), postResAmount, getattr(afflictor, 'projected', False)))
        rootOrder = list(container.keys())
        rootOrder.sort(key=lambda x: self.ORDER.index(type(x)))
        for thing in rootOrder:
            if thing == self.stuff:
                parent = root
            else:
                icon = self.imageList.Add(BitmapLoader.getBitmap('ship_small', 'gui'))
                child = self.affectedBy.AppendItem(root, '{} ({})'.format(thing.name, thing.ship.item.name), icon)
                parent = child
            attributes = container[thing]
            attrOrder = sorted(list(attributes.keys()), key=self.sortAttrDisplayName)
            for attrName in attrOrder:
                attrInfo = self.stuff.item.attributes.get(attrName)
                displayName = attrInfo.displayName if attrInfo and attrInfo.displayName else attrName
                if attrInfo:
                    if attrInfo.iconID is not None:
                        iconFile = attrInfo.iconID
                        icon = BitmapLoader.getBitmap(iconFile, 'icons')
                        if icon is None:
                            icon = BitmapLoader.getBitmap('transparent16x16', 'gui')
                        attrIcon = self.imageList.Add(icon)
                    else:
                        attrIcon = self.imageList.Add(BitmapLoader.getBitmap('0', 'icons'))
                else:
                    attrIcon = self.imageList.Add(BitmapLoader.getBitmap('0', 'icons'))
                if self.showRealNames:
                    display = attrName
                    saved = displayName
                else:
                    display = displayName
                    saved = attrName
                child = self.affectedBy.AppendItem(parent, display, attrIcon)
                self.affectedBy.SetItemData(child, saved)
                self.treeItems.append(child)
                items = attributes[attrName]
                items.sort(key=lambda x: self.ORDER.index(x[0]))
                for itemInfo in items:
                    afflictorType, afflictor, item, attrModifier, attrAmount, projected = itemInfo
                    if afflictorType == Ship:
                        itemIcon = self.imageList.Add(BitmapLoader.getBitmap('ship_small', 'gui'))
                    elif item.iconID:
                        bitmap = BitmapLoader.getBitmap(item.iconID, 'icons')
                        itemIcon = self.imageList.Add(bitmap) if bitmap else -1
                    else:
                        itemIcon = -1
                    displayStr = item.name
                    if projected:
                        displayStr += ' (projected)'
                    penalized = ''
                    if '*' in attrModifier:
                        if 's' in attrModifier:
                            penalized += '(penalized)'
                        if 'r' in attrModifier:
                            penalized += '(resisted)'
                        attrModifier = '*'
                    if attrModifier == '+' and attrAmount < 0:
                        attrModifier = '-'
                        attrAmount = -attrAmount
                    display = '%s %s %.2f %s' % (displayStr, attrModifier, attrAmount, penalized)
                    treeItem = self.affectedBy.AppendItem(child, display, itemIcon)
                    self.affectedBy.SetItemData(treeItem, afflictor)

    def buildModuleView(self, root):
        """
        We first build a usable dictionary of items. The key is either a fit
        if the afflictions stem from a projected fit, or self.stuff if they
        are local afflictions (everything else, even gang boosts at this time)
        The value of this is yet another dictionary in the following format:

        "Module Name": [
            class of affliction,
            set of afflictors (such as 2 of the same module),
            info on affliction (attribute name, modifier, and modification amount),
            item that will be used to determine icon (required due to GH issue #335)
            whether this affliction is actually used (unlearned skills are not used)
        ]
        """
        attributes = self.stuff.itemModifiedAttributes if self.item == self.stuff.item else self.stuff.chargeModifiedAttributes
        container = {}
        for attrName in attributes.iterAfflictions():
            if attributes[attrName] == attributes.getOriginal(attrName, 0):
                continue
            for fit, afflictors in attributes.getAfflictions(attrName).items():
                for afflictor, operator, stackingGroup, preResAmount, postResAmount, used in afflictors:
                    if not used or getattr(afflictor, 'item', None) is None:
                        continue
                    if fit.ID != self.activeFit:
                        if fit not in container:
                            container[fit] = {}
                        items = container[fit]
                    else:
                        if self.stuff not in container:
                            container[self.stuff] = {}
                        items = container[self.stuff]
                    if afflictor == self.stuff and getattr(afflictor, 'charge', None):
                        item = afflictor.charge
                    else:
                        item = afflictor.item
                    if item.name not in items:
                        items[item.name] = [type(afflictor), set(), [], item, getattr(afflictor, 'projected', False)]
                    info = items[item.name]
                    info[1].add(afflictor)
                    operatorStr = formatOperator(operator, stackingGroup, preResAmount, postResAmount)
                    if len(info[1]) > 1 and (attrName, operatorStr, postResAmount) in info[2]:
                        continue
                    info[2].append((attrName, operatorStr, postResAmount))
        rootOrder = list(container.keys())
        rootOrder.sort(key=lambda x: self.ORDER.index(type(x)))
        for thing in rootOrder:
            if thing == self.stuff:
                parent = root
            else:
                icon = self.imageList.Add(BitmapLoader.getBitmap('ship_small', 'gui'))
                child = self.affectedBy.AppendItem(root, '{} ({})'.format(thing.name, thing.ship.item.name), icon)
                parent = child
            items = container[thing]
            order = list(items.keys())
            order.sort(key=lambda x: (self.ORDER.index(items[x][0]), x))
            for itemName in order:
                info = items[itemName]
                afflictorType, afflictors, attrData, item, projected = info
                counter = len(afflictors)
                if afflictorType == Ship:
                    itemIcon = self.imageList.Add(BitmapLoader.getBitmap('ship_small', 'gui'))
                elif item.iconID:
                    bitmap = BitmapLoader.getBitmap(item.iconID, 'icons')
                    itemIcon = self.imageList.Add(bitmap) if bitmap else -1
                else:
                    itemIcon = -1
                displayStr = itemName
                if counter > 1:
                    displayStr += ' x {}'.format(counter)
                if projected:
                    displayStr += ' (projected)'
                child = self.affectedBy.AppendItem(parent, displayStr, itemIcon)
                self.affectedBy.SetItemData(child, afflictors.pop())
                if counter > 0:
                    attributes = []
                    for attrName, attrModifier, attrAmount in attrData:
                        attrInfo = self.stuff.item.attributes.get(attrName)
                        displayName = attrInfo.displayName if attrInfo else ''
                        if attrInfo:
                            if attrInfo.iconID is not None:
                                iconFile = attrInfo.iconID
                                icon = BitmapLoader.getBitmap(iconFile, 'icons')
                                if icon is None:
                                    icon = BitmapLoader.getBitmap('transparent16x16', 'gui')
                                attrIcon = self.imageList.Add(icon)
                            else:
                                attrIcon = self.imageList.Add(BitmapLoader.getBitmap('0', 'icons'))
                        else:
                            attrIcon = self.imageList.Add(BitmapLoader.getBitmap('0', 'icons'))
                        penalized = ''
                        if '*' in attrModifier:
                            if 's' in attrModifier:
                                penalized += '(penalized)'
                            if 'r' in attrModifier:
                                penalized += '(resisted)'
                            attrModifier = '*'
                        if attrModifier == '+' and attrAmount < 0:
                            attrModifier = '-'
                            attrAmount = -attrAmount
                        attributes.append((attrName, displayName if displayName else attrName, attrModifier, attrAmount, penalized, attrIcon))
                    attrSorted = sorted(attributes, key=lambda attribName: attribName[0])
                    for attr in attrSorted:
                        attrName, displayName, attrModifier, attrAmount, penalized, attrIcon = attr
                        if self.showRealNames:
                            display = '%s %s %.2f %s' % (attrName, attrModifier, attrAmount, penalized)
                            saved = '%s %s %.2f %s' % (displayName if displayName else attrName, attrModifier, attrAmount, penalized)
                        else:
                            display = '%s %s %.2f %s' % (displayName if displayName else attrName, attrModifier, attrAmount, penalized)
                            saved = '%s %s %.2f %s' % (attrName, attrModifier, attrAmount, penalized)
                        treeitem = self.affectedBy.AppendItem(child, display, attrIcon)
                        self.affectedBy.SetItemData(treeitem, saved)
                        self.treeItems.append(treeitem)

class _Tree:
    def __init__(self, links):
        self.links = links
        self.nodes = {0: dict(children=[])}

    def AppendItem(self, parent, label, *args):
        key = len(self.nodes)
        node = dict(label=label, alternate=None, sources=[], children=[])
        self.nodes[key] = node
        self.nodes[parent]['children'].append(node)
        return key

    def SetItemData(self, key, data):
        if isinstance(data, str):
            self.nodes[key]['alternate'] = data
        elif data is not None:
            self.nodes[key]['sources'] = self.links.get(id(data), [])


def views(stuff, item, fit, source_resolver=None):
    if stuff is None:
        return dict(source=[], attribute=[])
    from .inspection import _source_target
    values = stuff.itemModifiedAttributes if item == stuff.item else stuff.chargeModifiedAttributes
    links = {}
    for name in values.iterAfflictions():
        for source_fit, entries in values.getAfflictions(name).items():
            for source, operator, stacking, before, after, used in entries:
                source_item = getattr(source, 'item', None)
                if source is stuff and getattr(source, 'charge', None) is not None:
                    source_item = source.charge
                if source_item is None:
                    continue
                source_key, source_target = (source_resolver(source_fit, source, source_item) if source_resolver is not None
                                            else (None, _source_target(source_fit, source, source_item)))
                link = dict(source_fit_id=source_fit.ID, source_fit_key=source_key,
                            source_fit_name=source_fit.name, item_id=source_item.ID,
                            source_target=source_target)
                candidates = links.setdefault(id(source), [])
                if link not in candidates:
                    candidates.append(link)
    result = {}
    for name, method in (('source', 'buildModuleView'), ('attribute', 'buildAttributeView')):
        view = AffectorViews()
        view.stuff = stuff; view.item = item; view.activeFit = fit.ID
        view.showRealNames = False; view.treeItems = []
        view.imageList = SimpleNamespace(Add=lambda *args: 0)
        view.affectedBy = _Tree(links)
        getattr(view, method)(0)
        result[name] = view.affectedBy.nodes[0]['children']
    return result
