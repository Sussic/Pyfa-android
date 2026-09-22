"""Read-only equipment discovery on the existing serialized EOS worker."""
from copy import deepcopy


class EquipmentMarket:
    def __init__(self, engine):
        engine._check_thread()
        from .market_policy import MarketPolicy
        self.engine = engine
        self.policy = MarketPolicy()
        self._catalog = None

    def catalog(self):
        self.engine._check_thread()
        if self._catalog is None:
            self._catalog = self._build_catalog()
        return deepcopy(self._catalog)

    def _build_catalog(self):
        import eos.db
        policy = self.policy
        groups, items, searchable = {}, {}, set()
        for name in policy.SEARCH_CATEGORIES:
            for item in eos.db.getItemsByCategory(name):
                if policy.getPublicityByItem(item):
                    items[item.ID] = item
                    searchable.add(item.ID)
        for name in policy.SEARCH_GROUPS:
            for item in eos.db.getGroup(name).items:
                if policy.getPublicityByItem(item):
                    items[item.ID] = item
                    searchable.add(item.ID)

        def visit(group, parent=None):
            leaf = policy.marketGroupHasTypesCheck(group)
            members = policy.getItemsByMarketGroup(group) if leaf else set()
            groups[group.ID] = {"id": group.ID, "name": group.name, "parent_id": parent,
                                "item_ids": sorted(item.ID for item in members)}
            items.update((item.ID, item) for item in members)
            if not leaf:
                for child in group.children:
                    if policy.marketGroupValidityCheck(child):
                        visit(child, group.ID)

        for group_id in policy.ROOT_MARKET_GROUPS:
            visit(eos.db.getMarketGroup(group_id))
        records = []
        for item in items.values():
            meta_id = policy.getMetaGroupIdByItem(item)
            market_group = policy.getMarketGroupByItem(item)
            parent = policy.getParentItemByItem(item)
            tab = "Faction" if meta_id in (4, 3, 52) else "Complex" if meta_id == 6 else "Officer" if meta_id == 5 else "Normal"
            records.append({"id": item.ID, "name": item.name, "category": item.category.name,
                "meta_id": meta_id, "meta": tab, "parent_id": parent.ID,
                "market_group_id": market_group.ID if market_group is not None else None,
                "searchable": item.ID in searchable})
        return {"version": 1, "roots": sorted(policy.ROOT_MARKET_GROUPS),
                "groups": sorted(groups.values(), key=lambda row: row["id"]),
                "items": sorted(records, key=lambda row: row["id"])}

    def search(self, text):
        """Desktop token, wildcard, default-jargon and regex behavior; same 100-row cap."""
        self.engine._check_thread()
        if type(text) is not str:
            raise ValueError("Search text must be a string")
        import eos.db
        from eos.gamedata import Category, Group, Item
        from sqlalchemy import or_
        from utils.cjk import isStringCjk
        from .market_policy import JARGON
        tokens = (self.policy._prepareRequestRegex(text[3:]) if text.strip().lower().startswith("re:")
                  else self.policy._prepareRequestNormal(text))
        tokens = ["(" + "|".join(JARGON[token.lower()]) + ")" if JARGON.get(token.lower()) else token for token in tokens]
        joined = " ".join(tokens)
        if len(joined) < (1 if isStringCjk(joined) else 3):
            return []
        candidates = eos.db.searchItemsRegex(tuple(tokens),
            where=or_(Category.name.in_(self.policy.SEARCH_CATEGORIES), Group.name.in_(self.policy.SEARCH_GROUPS)),
            join=(Item.group, Group.category), eager=("group.category", "metaGroup"))
        return sorted(item.ID for item in candidates if self.policy.getPublicityByItem(item))
