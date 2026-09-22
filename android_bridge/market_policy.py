# ===============================================================================
# Copyright (C) 2010 Diego Duclos
#
# This file is part of pyfa.
#
# pyfa is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyfa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyfa.  If not, see <http://www.gnu.org/licenses/>.
# ===============================================================================

"""Display policy adapted from pinned service/market.py (8b04f3b2).

Only pure catalogue/search policies are retained; no desktop services, threads,
settings or fitting calculations. Full output is independently compared with
the unmodified desktop Market, including exceptions and parent variations.
"""
import re
import eos.db
from logbook import Logger
from .catalog import HIDDEN

pyfalog = Logger(__name__)

class RegexTokenizationError(ValueError):
    pass

class MarketPolicy:
    ITEMS_FORCEPUBLISHED = {'Data Subverter I': False,
     'QA Cross Protocol Analyzer': False,
     'QA Damage Module': False,
     'QA ECCM': False,
     'QA Immunity Module': False,
     'QA Multiship Module - 10 Players': False,
     'QA Multiship Module - 20 Players': False,
     'QA Multiship Module - 40 Players': False,
     'QA Multiship Module - 5 Players': False,
     'QA Remote Armor Repair System - 5 Players': False,
     'QA Shield Transporter - 5 Players': False,
     "Goru's Shuttle": False,
     'Guristas Shuttle': False,
     'Mobile Decoy Unit': False,
     'Tournament Micro Jump Unit': False}
    ITEMS_FORCEDMETAGROUP = {"'Habitat' Miner I": ('Storyline', 'Miner I'),
     "'Wild' Miner I": ('Storyline', 'Miner I'),
     'Khanid Navy Torpedo Launcher': ('Faction', 'Torpedo Launcher I'),
     'Dread Guristas Standup Variable Spectrum ECM': ('Structure Faction',
                                                      'Standup Variable Spectrum ECM I'),
     'Dark Blood Standup Heavy Energy Neutralizer': ('Structure Faction',
                                                     'Standup Heavy Energy Neutralizer I')}
    ITEMS_FORCEDMARKETGROUP = {'Advanced Cerebral Accelerator': 2487,
     'Civilian Hobgoblin': 837,
     'Civilian Light Missile Launcher': 640,
     'Civilian Scourge Light Missile': 920,
     'Civilian Small Remote Armor Repairer': 1059,
     'Civilian Small Remote Shield Booster': 603,
     "Hardwiring - Zainou 'Sharpshooter' ZMX10": 1493,
     "Hardwiring - Zainou 'Sharpshooter' ZMX100": 1493,
     "Hardwiring - Zainou 'Sharpshooter' ZMX1000": 1493,
     "Hardwiring - Zainou 'Sharpshooter' ZMX11": 1493,
     "Hardwiring - Zainou 'Sharpshooter' ZMX110": 1493,
     "Hardwiring - Zainou 'Sharpshooter' ZMX1100": 1493,
     'Prototype Cerebral Accelerator': 2487,
     'Prototype Iris Probe Launcher': 712,
     'Standard Cerebral Accelerator': 2487}
    FORCEDMARKETGROUP = {685: False, 681: False, 1639: False, 2527: True}
    SEARCH_CATEGORIES = ('Drone',
     'Module',
     'Subsystem',
     'Charge',
     'Implant',
     'Deployable',
     'Fighter',
     'Structure',
     'Structure Module')
    SEARCH_GROUPS = ('Ice Product',
     'Cargo Container',
     'Secure Cargo Container',
     'Audit Log Secure Container',
     'Freight Container',
     'Jump Filaments',
     'Triglavian Space Filaments')
    ROOT_MARKET_GROUPS = (9, 1111, 157, 11, 1112, 24, 404, 2202, 2203, 2456)

    def __init__(self):
        self.SHOWN_MARKET_GROUPS = eos.db.getMarketTreeNodeIds(self.ROOT_MARKET_GROUPS)
        self.ITEMS_FORCEPUBLISHED = dict(self.ITEMS_FORCEPUBLISHED, **{name: False for name in HIDDEN})
        self.ITEMS_FORCEDMARKETGROUP_R = {}
        self.ITEMS_FORCEDMETAGROUP_R = {}
        for name, group in self.ITEMS_FORCEDMARKETGROUP.items():
            self.ITEMS_FORCEDMARKETGROUP_R.setdefault(group, set()).add(name)
        for name, (_, parent) in self.ITEMS_FORCEDMETAGROUP.items():
            self.ITEMS_FORCEDMETAGROUP_R.setdefault(parent, set()).add(name)

    getItem = staticmethod(eos.db.getItem)
    getMarketGroup = staticmethod(eos.db.getMarketGroup)


    def getMetaGroupByItem(self, item):
        """Get meta group by item"""
        if item.name in self.ITEMS_FORCEDMETAGROUP:
            metaGroupName = self.ITEMS_FORCEDMETAGROUP[item.name][0]
            metaGroup = eos.db.getMetaGroup(metaGroupName)
        else:
            metaGroup = item.metaGroup
        return metaGroup

    def getMetaGroupIdByItem(self, item, fallback=0):
        """Get meta group ID by item"""
        id_ = getattr(self.getMetaGroupByItem(item), 'ID', fallback)
        return id_

    def getMarketGroupByItem(self, item, parentcheck=True):
        """Get market group by item, its ID or name"""
        if item.name in self.ITEMS_FORCEDMARKETGROUP:
            mgid = self.ITEMS_FORCEDMARKETGROUP[item.name]
            if mgid in self.SHOWN_MARKET_GROUPS:
                return self.getMarketGroup(mgid)
            else:
                return None
        elif item.marketGroupID:
            if item.marketGroupID in self.SHOWN_MARKET_GROUPS:
                return item.marketGroup
            else:
                return None
        elif parentcheck:
            parent = self.getParentItemByItem(item, selfparent=False)
            if parent and parent.marketGroupID in self.SHOWN_MARKET_GROUPS:
                return parent.marketGroup
            else:
                return None
        else:
            return None

    def getParentItemByItem(self, item, selfparent=True):
        """Get parent item by item"""
        parent = None
        if item.name in self.ITEMS_FORCEDMETAGROUP:
            parentName = self.ITEMS_FORCEDMETAGROUP[item.name][1]
            parent = self.getItem(parentName)
        if parent is None:
            parent = item.varParent
        if parent is None and selfparent is True:
            parent = item
        return parent

    def getVariationsByItems(self, items, alreadyparent=False):
        """Get item variations by item, its ID or name"""
        parents = set()
        variations = set()
        variations_limiter = set()
        categories = ['Drone', 'Fighter', 'Implant']
        for item in items:
            if item.category.ID == 20 and item.group.ID != 303:
                implant_remove_list = set()
                implant_remove_list.add('Low-Grade ')
                implant_remove_list.add('Low-grade ')
                implant_remove_list.add('Mid-Grade ')
                implant_remove_list.add('Mid-grade ')
                implant_remove_list.add('High-Grade ')
                implant_remove_list.add('High-grade ')
                implant_remove_list.add('Limited ')
                implant_remove_list.add(' - Advanced')
                implant_remove_list.add(' - Basic')
                implant_remove_list.add(' - Elite')
                implant_remove_list.add(' - Improved')
                implant_remove_list.add(' - Standard')
                for implant_prefix in ('-6', '-7', '-8', '-9', '-10'):
                    for i in range(50):
                        implant_remove_list.add(implant_prefix + str('%02d' % i))
                for text_to_remove in implant_remove_list:
                    if text_to_remove in item.name:
                        variations_limiter.add(item.name.replace(text_to_remove, ''))
            if alreadyparent is False:
                parent = self.getParentItemByItem(item)
            else:
                parent = item
            parents.add(parent)
            if parent.name in self.ITEMS_FORCEDMETAGROUP_R:
                for _item in self.ITEMS_FORCEDMETAGROUP_R[parent.name]:
                    i = self.getItem(_item)
                    if i:
                        variations.add(i)
        variations.update(parents)
        parentids = tuple((item.ID for item in parents))
        groupids = tuple((item.group.ID for item in parents if item.category.name in categories))
        variations_list = eos.db.getVariations(parentids, groupids)
        if variations_limiter:
            for limit in variations_limiter:
                trimmed_variations_list = [variation_item for variation_item in variations_list if limit in variation_item.name]
            if trimmed_variations_list:
                variations_list = trimmed_variations_list
        BOOSTER_GROUP_ID = 303
        if all(map(lambda i: i.group.ID == BOOSTER_GROUP_ID, items)) and len(items) > 0:
            reqSlot = next(items.__iter__()).getAttribute('boosterness')
            marketGroupID = [next(filter(None, map(lambda i: i.marketGroupID, items)), None), None]
            matchSlotAndMktGrpID = lambda v: v.getAttribute('boosterness') == reqSlot and v.marketGroupID in marketGroupID
            variations_list = list(filter(matchSlotAndMktGrpID, variations_list))
        variations.update(variations_list)
        return variations

    def getItemsByMarketGroup(self, mg, vars_=True):
        """Get items in the given market group"""
        result = set()
        baseitms = set(mg.items)
        if mg.ID in self.ITEMS_FORCEDMARKETGROUP_R:
            forceditms = set((self.getItem(itmn) for itmn in self.ITEMS_FORCEDMARKETGROUP_R[mg.ID]))
            baseitms.update(forceditms)
        if vars_:
            parents = set()
            for item in baseitms:
                result.add(item)
                parent = self.getParentItemByItem(item, selfparent=False)
                if parent is None:
                    parents.add(item)
            variations = self.getVariationsByItems(parents, alreadyparent=True)
            for variation in variations:
                if self.getMarketGroupByItem(variation, parentcheck=False) is None:
                    result.add(variation)
        else:
            result = baseitms
        result = set([item_ for item_ in result if self.getPublicityByItem(item_)])
        return result

    def marketGroupHasTypesCheck(self, mg):
        """If market group has any items, return true"""
        if mg and mg.ID in self.ITEMS_FORCEDMARKETGROUP_R:
            if len(mg.children) > 0 and len(mg.items) == 0:
                pyfalog.error('Market group "{0}" contains no items and has children. ITEMS_FORCEDMARKETGROUP is likely outdated and will need to be updated for {1} to display correctly.'.format(mg, self.ITEMS_FORCEDMARKETGROUP_R[mg.ID]))
                return False
            return True
        elif len(mg.items) > 0 and len(mg.children) == 0:
            return True
        else:
            return False

    def marketGroupValidityCheck(self, mg):
        """Check market group validity"""
        if mg.ID in self.FORCEDMARKETGROUP:
            return self.FORCEDMARKETGROUP[mg.ID]
        if mg.hasTypes and (not self.marketGroupHasTypesCheck(mg)):
            return False
        else:
            return True

    def getPublicityByItem(self, item):
        """Return if an item is published"""
        if item.typeName in self.ITEMS_FORCEPUBLISHED:
            pub = self.ITEMS_FORCEPUBLISHED[item.typeName]
        else:
            pub = item.published
        return pub

    def _prepareRequestNormal(self, request):
        request = re.escape(request)
        request = re.sub('\\\\(?P<ws>\\s+)', '\\g<ws>', request)
        request = re.sub('\\\\\\*', '\\\\w*', request)
        request = re.sub('\\\\\\?', '\\\\w?', request)
        tokens = request.split()
        return tokens

    def _prepareRequestRegex(self, request):
        roundLvl = 0
        squareLvl = 0
        nextEscaped = False
        tokens = []
        currentToken = ''

        def verifyErrors():
            if squareLvl not in (0, 1):
                raise RegexTokenizationError('Square braces level is {}'.format(squareLvl))
            if roundLvl < 0:
                raise RegexTokenizationError('Round braces level is {}'.format(roundLvl))
        try:
            for char in request:
                thisEscaped = nextEscaped
                nextEscaped = False
                if thisEscaped:
                    currentToken += char
                elif char == '\\':
                    currentToken += char
                    nextEscaped = True
                elif char == '[':
                    currentToken += char
                    squareLvl += 1
                elif char == ']':
                    currentToken += char
                    squareLvl -= 1
                elif char == '(' and squareLvl == 0:
                    currentToken += char
                    roundLvl += 1
                elif char == ')' and squareLvl == 0:
                    currentToken += char
                    roundLvl -= 1
                elif char.isspace() and roundLvl == squareLvl == 0:
                    if currentToken:
                        tokens.append(currentToken)
                        currentToken = ''
                else:
                    currentToken += char
                verifyErrors()
            else:
                if currentToken:
                    tokens.append(currentToken)
        except RegexTokenizationError:
            tokens = self._prepareRequestNormal(request)
        return tokens

# Default jargon from service/jargon/defaults.yaml; Jargon.apply policy by
# Filip Sufitchi (2018), GPL-3.0-or-later. User jargon editing remains I06.
JARGON = {'1': ['1', ' I$'],
 '10k': ['10k', '10000'],
 '10kmn': ['10kmn', '10000mn'],
 '2': ['2', ' II$'],
 '25k': ['25k', '25000'],
 '25kmm': ['25kmm', '25000mm'],
 '25m': ['25m', '25000mm'],
 '3': ['3', ' III$'],
 '4': ['4', ' IV$'],
 '50k': ['50k', '50000'],
 '50kmn': ['50kmn', '50000mn'],
 'aar': ['aar', 'ancillary (.+ )?(?<!remote )armor repairer'],
 'ab': ['(^| )ab', 'afterburner'],
 'ac': ['ac', 'autocannon'],
 'acr': ['acr', 'ancillary current router'],
 'adc': ['adc', 'assault damage control'],
 'adcu': ['adcu', 'assault damage control'],
 'aif': ['aif', 'multispectrum shield hardener'],
 'am': ['(^| )am', 'antimatter'],
 'amarr': ['amarr', 'radar'],
 'anp': ['anp', 'multispectrum coating'],
 'anti': ['anti', '(shield|armor) reinforcer'],
 'anti\\-': ['anti-', '(shield|armor) reinforcer'],
 'ar': ['(?<!remote )armor repairer'],
 'armour': ['armour', 'armor'],
 'arsb': ['arsb', 'ancillary remote shield booster'],
 'arty': ['arty', 'artillery'],
 'asb': ['asb', 'ancillary shield booster'],
 'ats': ['ats', 'auto targeting system'],
 'bc': ['bc', 'breach control'],
 'bcs': ['bcs', 'ballistic control system'],
 'bcu': ['bcu', 'ballistic control system', 'breach control'],
 'bdc': ['bdc', 'breach control'],
 'bdcu': ['bdcu', 'breach control'],
 'blue': ['blue', 'gravimetric'],
 'boosh': ['boosh', 'micro jump field generator'],
 'bubble': ['bubble',
            'interdiction sphere launcher',
            'warp disrupt probe',
            'warp disruption field generator',
            'warp disruption (.+ )?projector',
            'mobile (.+ )?warp disruptor'],
 'caar': ['caar', 'capital ancillary (.+ )?(?<!remote )armor repairer'],
 'caldari': ['caldari', 'gravimetric'],
 'caprech': ['caprech', 'cap recharger'],
 'caprelay': ['caprelay', 'capacitor power relay'],
 'car': ['car', 'capital (.+ )?(?<!remote )armor repairer'],
 'carsb': ['carsb', 'capital ancillary remote shield booster'],
 'casb': ['casb', 'capital ancillary (.+ )?(?<!remote )shield booster'],
 'cb': ['cb', 'capacitor booster', 'command burst'],
 'ccc': ['ccc', 'capacitor control circuit'],
 'cdfe': ['cdfe', 'core defense field extender'],
 'cehe': ['cehe', 'capital (.+ )?emergency hull energizer'],
 'cet': ['cet', 'capital (.+ )?remote capacitor transmitter'],
 'charge': ['charge', 'cap booster \\d+'],
 'cl': ['(^| )cl', 'carbonized lead'],
 'cm': ['(^| )cm', 'cruise missile'],
 'cml': ['cml', '(?<!xl )cruise (missile )?(launcher|bay)'],
 'cn': ['(^| )cn', 'caldari navy'],
 'coproc': ['coproc', 'co-proc'],
 'cp': ['cp', 'command processor'],
 'cpr': ['cpr', 'capacitor power relay'],
 'craar': ['craar', 'capital ancillary remote armor repairer'],
 'crar': ['crar', 'capital (.+ )?remote armor repairer'],
 'crasb': ['crasb', 'capital ancillary remote shield booster'],
 'crct': ['crct', 'capital (.+ )?remote capacitor transmitter'],
 'cret': ['cret', 'capital (.+ )?remote capacitor transmitter'],
 'crr': ['crr',
         'capital (.+ )?remote shield booster',
         'capital (.+ )?remote (armor|hull) repairer'],
 'crsb': ['crsb', 'capital (.+ )?remote shield booster'],
 'csb': ['csb', 'capital (.+ )?(?<!remote )shield booster'],
 'cse': ['cse', 'capital (.+ )?shield extender'],
 'damp': ['damp', 'sd-\\d00'],
 'dampener': ['dampener', 'sd-\\d00', '(targeting range|scan resolution) dampening script'],
 'db': ['(^| )db', 'dark blood'],
 'dc': ['dc', '(?<!assault )damage control'],
 'dcu': ['dcu', '(?<!assault )damage control'],
 'dd': ['dd', 'doomsday', 'lance$', 'reaper', 'bosonic', 'arcing vorton projector'],
 'dda': ['dda', 'drone damage amplifier'],
 'dg': ['(^| )dg', 'dread guristas'],
 'disco': ['disco', 'smartbomb'],
 'dla': ['dla', 'drone link augmentor'],
 'dnc': ['dnc', 'drone navigation computer'],
 'doomsday': ['doomsday', 'lance$', 'reaper', 'bosonic', 'arcing vorton projector'],
 'dtc': ['dtc', 'omnidirectional tracking link', '(optimal range|tracking speed) script'],
 'dte': ['dte', 'omnidirectional tracking enhancer'],
 'dtl': ['dtl', 'omnidirectional tracking link', '(optimal range|tracking speed) script'],
 'du': ['(^| )du', 'depleted uranium'],
 'eanm': ['eanm', 'multispectrum energized membrane'],
 'eccm': ['eccm', '(?<!remote )sensor booster', 'signal amplifier'],
 'ecm': ['ecm', 'jammer', 'ec-\\d00', 'lockbreaker bomb'],
 'economiser': ['economiser', 'economizer'],
 'ehe': ['ehe', 'emergency hull energizer'],
 'em': ['em', 'mjolnir (.+ )?(missile|rocket|torpedo)', 'electromagnetic', 'electron bomb'],
 'enam': ['enam', 'multispectrum energized membrane'],
 'energised': ['energised', 'energized'],
 'ess': ['encounter surveillance system'],
 'et': ['(^| )et', 'remote capacitor transmitter'],
 'exp': ['exp', 'nova (.+ )?(missile|rocket|torpedo)', 'proton smartbomb', 'shrapnel bomb'],
 'expl': ['expl', 'nova (.+ )?(missile|rocket|torpedo)', 'proton smartbomb', 'shrapnel bomb'],
 'explo': ['explo', 'nova (.+ )?(missile|rocket|torpedo)', 'proton smartbomb', 'shrapnel bomb'],
 'explosive': ['explosive',
               'nova (.+ )?(missile|rocket|torpedo)',
               'proton smartbomb',
               'shrapnel bomb'],
 'flex': ['flex', 'resistance script'],
 'fn': ['(^| )fn', 'federation navy'],
 'fof': ['fof', 'auto-targeting (.+ )?missile'],
 'fsu': ['fsu', 'fighter support unit'],
 'fvb': ['fvb', 'focused void bomb'],
 'gallente': ['gallente', 'magnetometric'],
 'gbomb': ['gbomb', 'guided bomb'],
 'gd': ['gd', 'guidance disrupt', 'weapon disrupt', 'missile (precision|range) disruption script'],
 'green': ['green', 'magnetometric'],
 'gs': ['(^| )gs', 'gyrostabilizer'],
 'gtfo': ['gravitational transportation field oscillator'],
 'ham': ['(^| )ham', 'heavy assault missile'],
 'haml': ['haml', 'heavy assault missile (launcher|bay)'],
 'haw': ['haw',
         'quad 800mm repeating cannon',
         'triple neutron blaster cannon',
         'quad mega pulse laser',
         'rapid torpedo (launcher|bay)'],
 'heatsink': ['heatsink', 'heat sink'],
 'hg': ['hg', 'high-grade'],
 'hm': ['(^| )hm', 'heavy missile'],
 'hml': ['hml', '(?<!rapid )heavy missile (launcher|bay)'],
 'hs': ['hs', 'heat sink'],
 'hvy': ['hvy', 'heavy'],
 'hwd': ['hwd', 'heavy warp disruptor'],
 'hws': ['hws', 'heavy warp scrambler'],
 'in': ['(^| )in', 'imperial navy'],
 'infinipoint': ['infinipoint',
                 'warp disruption field generator',
                 '^focused warp disruption script',
                 '^focused warp scrambling script'],
 'infiniscram': ['infiniscram',
                 'warp disruption field generator',
                 '^focused warp disruption script',
                 '^focused warp scrambling script'],
 'inj': ['inj', 'capacitor booster'],
 'injector': ['injector', 'capacitor booster'],
 'inv': ['inv', 'multispectrum shield hardener'],
 'invul': ['invul', 'multispectrum shield hardener'],
 'invuln': ['invuln', 'multispectrum shield hardener'],
 'invulnerability': ['invulnerability', 'multispectrum shield hardener'],
 'ir': ['(^| )ir', 'infrared'],
 'isa': ['isa', 'integrated sensor array'],
 'istab': ['istab', 'inertial stabilizer'],
 'jam': ['jam', 'ecm', 'ec-\\d00', 'lockbreaker bomb'],
 'jamm': ['jamm', 'ecm', 'ec-\\d00', 'lockbreaker bomb'],
 'jammer': ['jammer', 'ecm', 'ec-\\d00'],
 'jde': ['jde', 'jump drive economizer'],
 'kin': ['kin', 'scourge (.+ )?(missile|rocket|torpedo)', 'concussion bomb'],
 'kinet': ['kinet', 'scourge (.+ )?(missile|rocket|torpedo)', 'concussion bomb'],
 'kinetic': ['kinetic', 'scourge (.+ )?(missile|rocket|torpedo)', 'concussion bomb'],
 'laar': ['laar', 'large ancillary (.+ )?(?<!remote )armor repairer'],
 'lar': ['lar', 'large (.+ )?(?<!remote )armor repairer'],
 'larsb': ['larsb', 'large ancillary remote shield booster'],
 'lasb': ['lasb', '(?<!x-)large ancillary (.+ )?(?<!remote )shield booster'],
 'let': ['(^| )let', 'large (.+ )?remote capacitor transmitter'],
 'lg': ['lg', 'low-grade'],
 'lm': ['(^| )lm', 'light missile'],
 'lmjd': ['lmjd', 'large micro jump drive'],
 'lml': ['lml', '(?<!rapid )light missile (launcher|bay)'],
 'lo': ['(^| )lo', 'liquid ozone'],
 'lraar': ['lraar', 'large ancillary remote armor repairer'],
 'lrar': ['lrar', 'large (.+ )?remote armor repairer', 'heavy (.+ )?armor maintenance bot'],
 'lrasb': ['lrasb', 'large ancillary remote shield booster'],
 'lrct': ['lrct', 'large (.+ )?remote capacitor transmitter'],
 'lret': ['lret', 'large (.+ )?remote capacitor transmitter'],
 'lrg': ['lrg', 'large'],
 'lrr': ['lrr',
         'large (.+ )?remote shield booster',
         'large (.+ )?remote (armor|hull) repairer',
         'heavy (.+ )?maintenance bot'],
 'lrsb': ['lrsb', 'large (.+ )?remote shield booster', 'heavy shield maintenance bot'],
 'lsb': ['lsb', '(?<!x-)large (.+ )?(?<!remote )shield booster'],
 'lse': ['(^| )lse', 'large (.+ )?shield extender'],
 'maar': ['maar', 'medium ancillary (.+ )?(?<!remote )armor repairer'],
 'magstab': ['magstab', 'magnetic field stabilizer'],
 'mapc': ['mapc', 'micro auxiliary power core'],
 'mar': ['medium (.+ )?(?<!remote )armor repairer'],
 'marsb': ['marsb', 'medium ancillary remote shield booster'],
 'masb': ['masb', 'medium ancillary (.+ )?(?<!remote )shield booster'],
 'mc': ['mc', 'multispectrum coating'],
 'mem': ['mem', 'multispectrum energized membrane'],
 'met': ['(^| )met', 'medium (.+ )?remote capacitor transmitter'],
 'mf': ['mf', 'multifrequency'],
 'mfs': ['mfs', 'magnetic field stabilizer'],
 'mg': ['mg', 'mid-grade'],
 'mgc': ['mgc', 'missile guidance computer', 'missile (precision|range) script'],
 'mge': ['mge', 'missile guidance enhancer'],
 'minmatar': ['minmatar', 'ladar'],
 'mjd': ['mjd', 'micro jump drive', 'micro jump field generator', 'micro jump unit'],
 'mjfg': ['mjfg', 'micro jump field generator'],
 'mju': ['mju', 'micro jump unit'],
 'mk': ['mk', 'mark'],
 'ml': ['ml', 'missile (launcher|bay)'],
 'mlu': ['mlu', '(mining laser|harvester) upgrade'],
 'mmjd': ['mmjd', 'medium micro jump drive'],
 'mmju': ['mmju', 'mobile micro jump unit'],
 'mraar': ['mraar', 'medium ancillary remote armor repairer'],
 'mrar': ['mrar',
          'medium (.+ )?remote armor repairer',
          'heavy mutadaptive (.+ )?remote armor repairer',
          'medium (.+ )?armor maintenance bot'],
 'mrasb': ['mrasb', 'medium ancillary remote shield booster'],
 'mrct': ['mrct', 'medium (.+ )?remote capacitor transmitter'],
 'mret': ['mret', 'medium (.+ )?remote capacitor transmitter'],
 'mrr': ['mrr',
         'medium (.+ )?remote shield booster',
         'medium (.+ )?remote (armor|hull) repairer',
         'heavy mutadaptive (.+ )?remote armor repairer',
         'medium (.+ )?maintenance bot'],
 'mrsb': ['mrsb', 'medium (.+ )?remote shield booster', 'medium shield maintenance bot'],
 'ms': ['(^| )ms', 'magnetic field stabilizer'],
 'msb': ['msb', 'medium (.+ )?(?<!remote )shield booster'],
 'mse': ['mse', 'medium (.+ )?shield extender'],
 'mtu': ['mtu', 'mobile tractor unit'],
 'mw': ['mw', 'microwave'],
 'mwd': ['mwd', 'microwarpdrive'],
 'ncb': ['ncb', 'navy cap booster \\d+'],
 'neut': ['neutralizer', 'neutralization', 'ev-\\d00', 'void bomb'],
 'neutraliser': ['neutraliser', 'neutralizer', 'neutralization', 'ev-\\d00'],
 'neutralizer': ['neutralizer', 'neutralization', 'ev-\\d00'],
 'np': ['(^| )np', 'nanite repair paste'],
 'nrp': ['nrp', 'nanite repair paste'],
 'nsa': ['nsa', 'networked sensor array'],
 'od': ['(^| )od', 'overdrive injector'],
 'odi': ['(^| )odi', 'overdrive injector'],
 'odtc': ['odtc', 'omnidirectional tracking link', '(optimal range|tracking speed) script'],
 'odte': ['odte', 'omnidirectional tracking enhancer'],
 'odtl': ['odtl', 'omnidirectional tracking link', '(optimal range|tracking speed) script'],
 'otc': ['otc', 'omnidirectional tracking link', '(optimal range|tracking speed) script'],
 'ote': ['(^| )ote', 'omnidirectional tracking enhancer'],
 'otl': ['otl', 'omnidirectional tracking link', '(optimal range|tracking speed) script'],
 'paint': ['paint', 'target illumination'],
 'painter': ['painter', 'target illumination'],
 'panic': ['pulse activated nexus invulnerability core'],
 'pdb': ['pdb', 'point defense battery'],
 'pds': ['pds', 'power diagnostic system', 'point defense battery'],
 'pdu': ['pdu', 'power diagnostic system'],
 'plating': ['plating', 'coating'],
 'point': ['(^| )point', '(?<!mobile small )(?<!mobile medium )(?<!mobile large )warp disruptor'],
 'pp': ['(^| )pp', 'phased plasma'],
 'raar': ['raar', 'ancillary remote armor repairer'],
 'radsink': ['radsink', 'entropic radiation sink'],
 'rah': ['rah', 'reactive armor hardener'],
 'rar': ['rar', 'remote armor repairer'],
 'rasb': ['rasb', 'ancillary remote shield booster'],
 'rcs': ['rcs', 'reactor control unit'],
 'rct': ['rct', 'remote capacitor transmitter'],
 'rcu': ['rcu', 'reactor control unit', 'reactor control unit'],
 'reccm': ['reccm', 'remote sensor booster', 'eccm script'],
 'red': ['red', 'ladar'],
 'resebo': ['resebo', 'remote sensor booster', '(targeting range|scan resolution|eccm) script'],
 'ret': ['(^| )ret', 'remote capacitor transmitter'],
 'rf': ['(^| )rf', 'republic fleet'],
 'rhml': ['rhml', 'rapid heavy missile (launcher|bay)'],
 'rl': ['rl', 'rocket (launcher|bay)'],
 'rlml': ['rlml', 'rapid light missile (launcher|bay)'],
 'rr': ['(^| )rr', 'remote shield booster', 'remote (armor|hull) repairer', 'maintenance bot'],
 'rs': ['(^| )rs', 'entropic radiation sink'],
 'rsb': ['rsb',
         'remote shield booster',
         'shield maintenance bot',
         'remote sensor booster',
         '(targeting range|scan resolution|eccm) script'],
 'rsd': ['rsd',
         'sensor dampener',
         'sd-\\d00',
         '(targeting range|scan resolution) dampening script'],
 'rsebo': ['rsebo', 'remote sensor booster', '(targeting range|scan resolution|eccm) script'],
 'rtc': ['rtc', 'remote tracking computer', '(optimal range|tracking speed) script'],
 'rtl': ['rtl',
         'rapid torpedo (launcher|bay)',
         'remote tracking computer',
         '(optimal range|tracking speed) script'],
 'sa': ['signal amplifier'],
 'saar': ['saar', 'small ancillary (.+ )?(?<!remote )armor repairer'],
 'sar': ['(^| )sar', 'small (.+ )?(?<!remote )armor repairer'],
 'sarsb': ['sarsb', 'small ancillary remote shield booster'],
 'sasb': ['sasb', 'small ancillary (.+ )?(?<!remote )shield booster'],
 'sb': ['sb',
        'smartbomb',
        '(?<!remote )shield booster',
        '(?<!remote )sensor booster',
        '(targeting range|scan resolution|eccm) script'],
 'sba': ['sba', 'shield boost amplifier'],
 'sbomb': ['sbomb', 'smartbomb'],
 'scan': ['scan', 'probe launcher'],
 'scanner': ['scanner', 'probe launcher'],
 'sd': ['(^| )sd', 'sensor dampener', '(targeting range|scan resolution) dampening script'],
 'sda': ['sda', 'signal distortion amplifier'],
 'se': ['(^| )se-', 'shield extender'],
 'sebo': ['sebo', '(?<!remote )sensor booster', '(targeting range|scan resolution|eccm) script'],
 'set': ['(^| )set', 'small (.+ )?remote capacitor transmitter'],
 'sg': ['sg', 'stasis grappler'],
 'shieldrech': ['shieldrech', 'shield recharger'],
 'siege': ['siege', 'bastion module', 'industrial core', 'triage module'],
 'sigamp': ['sigamp', 'signal amplifier'],
 'slave': ['slave', 'amulet'],
 'smc': ['smc', 'semiconductor memory cell'],
 'sml': ['sml', 'small'],
 'spr': ['spr', 'shield power relay'],
 'sraar': ['sraar', 'small ancillary remote armor repairer'],
 'srar': ['srar', 'small (.+ )?remote armor repairer', 'light (.+ )?armor maintenance bot'],
 'srasb': ['srasb', 'small ancillary remote shield booster'],
 'srct': ['srct', 'small (.+ )?remote capacitor transmitter'],
 'sret': ['sret', 'small (.+ )?remote capacitor transmitter'],
 'srr': ['srr',
         'small (.+ )?remote shield booster',
         'small (.+ )?remote (armor|hull) repairer',
         'light (.+ )? maintenance bot'],
 'srs': ['srs', 'signature radius suppressor'],
 'srsb': ['srsb', 'small (.+ )?remote shield booster', 'light shield maintenance bot'],
 'ss': ['(^| )ss', 'shadow serpentis'],
 'ssb': ['ssb', 'small (.+ )?(?<!remote )shield booster'],
 'sse': ['(^| )sse', 'small (.+ )?shield extender'],
 'stabiliser': ['stabiliser', 'stabilizer'],
 'std': ['std', 'standard'],
 'stick': ['stick', 'cap booster \\d+'],
 'sw': ['sw', 'stasis webifier', 'stasis grappler'],
 't1': ['t1', ' I$'],
 't2': ['t2', ' II$'],
 'tc': ['tc', '(?<!remote )tracking computer', '(optimal range|tracking speed) script'],
 'td': ['td',
        'tracking disrupt',
        'weapon disrupt',
        '(optimal range|tracking speed) disruption script'],
 'te': ['(?<!omnidirectional )tracking enhancer'],
 'therm': ['therm', 'inferno (.+ )?(missile|rocket|torpedo)', 'plasma smartbomb', 'scorch bomb'],
 'thermal': ['thermal',
             'inferno (.+ )?(missile|rocket|torpedo)',
             'plasma smartbomb',
             'scorch bomb'],
 'tl': ['(^| )tl',
        '(?<!rapid )(?<!XL )torpedo (launcher|bay)',
        'remote tracking computer',
        '(optimal range|tracking speed) script'],
 'tp': ['(^| )tp', 'target painter', 'target illumination', 'tp-\\d00'],
 'ts': ['(^| )ts', 'true sansha', 'titanium sabot'],
 'uv': ['(^| )uv', 'ultraviolet'],
 'uw': ['uw', 'microwave'],
 'vts': ['vts', 'vorton tuning system'],
 'wcs': ['wcs', 'warp core stabilizer'],
 'wd': ['wd',
        'weapon disrupt',
        'tracking disrupt',
        'guidance disrupt',
        'td-\\d00',
        '(?<!mobile small )(?<!mobile medium )(?<!mobile large )(?<!heavy )warp disruptor'],
 'wdfg': ['wdfg',
          'warp disruption field generator',
          '^focused warp disruption script',
          '^focused warp scrambling script'],
 'web': ['web', 'grappler', 'sw-\\d00'],
 'webifier': ['webifier', 'grappler', 'sw-\\d00'],
 'ws': ['ws', '(?<!heavy )warp scrambler'],
 'wstab': ['wstab', 'warp core stabilizer'],
 'wub': ['wub', 'stasis webification probe', 'interdiction sphere launcher'],
 'wubble': ['wubble', 'stasis webification probe', 'interdiction sphere launcher'],
 'x\\-ray': ['x-ray', 'xray'],
 'xl': ['xl', 'x-large'],
 'xlasb': ['xlasb', 'x-large ancillary (.+ )?(?<!remote )shield booster'],
 'xlcm': ['xlcm', 'xl cruise missile'],
 'xlcml': ['xlcml', 'xl cruise missile (launcher|bay)'],
 'xlsb': ['xlsb', 'x-large (.+ )?(?<!remote )shield booster'],
 'xltl': ['xltl', 'xl torpedo (launcher|bay)'],
 'yellow': ['yellow', 'radar'],
 'zpme': ['zpme', 'zero-point mass entangler']}
