"""Offline hull browser using EOS data and the pinned desktop market policy.

The small display-policy port is checked against the independent desktop Market
service. No fitting rules or calculations live here. IDs are game IDs, except
desktop's synthetic Limited Issue Ships group (-1).
"""

LIMITED = set("""Opux Luxury Yacht|Silver Magnate|Gold Magnate|Armageddon Imperial Issue|
Apocalypse Imperial Issue|Guardian-Vexor|Megathron Federate Issue|Raven State Issue|
Tempest Tribal Issue|Zephyr|Primae|Council Diplomatic Shuttle|Freki|Mimir|Utu|Adrestia|
Echelon|Malice|Vangel|Cambion|Etana|Chremoas|Moracha|Stratios Emergency Responder|
Miasmos Quafe Ultra Edition|InterBus Shuttle|Leopard|Whiptail|Chameleon|
Victorieux Luxury Yacht|Imp|Fiend|Caedes|Rabisu|Victor|Virtuoso|Hydra|Tiamat|Raiju|
Laelaps|Boobook|Geri|Bestla|Shapash|Cybele|Sidewinder|Cobra|Python|Skua|Anhinga""".replace("\n", "").split("|"))
HIDDEN = set("""Goru's Shuttle|Guristas Shuttle|Miasmos Amastris Edition|
Miasmos Quafe Ultramarine Edition|Rattlesnake Victory Edition|Aliastra Catalyst|
Inner Zone Shipping Catalyst|Intaki Syndicate Catalyst|InterBus Catalyst|Quafe Catalyst|
Inner Zone Shipping Imicus|Nefantar Thrasher|Sarum Magnate|Tash-Murkon Magnate|
Sukuuvestaa Heron|Vherokior Probe""".replace("\n", "").split("|"))


def hull_catalog(engine):
    engine._check_thread()
    import eos.db
    groups = {-1: {"id": -1, "name": "Limited Issue Ships"}}
    hulls = []
    for category in ("Ship", "Structure"):
        for group in eos.db.getCategory(category).groups:
            if group.published and group.name != "Prototype Exploration Ship":
                groups[group.ID] = {"id": group.ID, "name": group.name}
        for item in eos.db.getItemsByCategory(category):
            if not item.published or item.name in HIDDEN:
                continue
            group_id = (-1 if item.name in LIMITED else
                        eos.db.getGroup("Shuttle").ID if item.name == "Capsule" else item.group.ID)
            if group_id in groups:
                hulls.append({"id": item.ID, "name": item.name, "group_id": group_id, "race": item.race})
    return {"version": 1, "groups": sorted(groups.values(), key=lambda group: group["name"]),
            "hulls": sorted(hulls, key=lambda hull: hull["id"])}
