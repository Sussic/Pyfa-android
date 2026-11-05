"""Translate a validated C06 record to EOS, preserving unlearned versus level 0.

EOS must already be initialized by its serialized worker. This adapter uses EOS
for skill dependency normalization; it contains no requirement/skill formula.
The source catalogue and Skill.level own Alpha caps; learned inputs stay intact.
"""
from .profiles import level, require
import unicodedata


def alpha_catalogue(skill_ids):
    """Read source data on the owning worker; never invent a fallback table."""
    try:
        import eos.db
        rows = eos.db.getAlphaCloneList()
        require(rows, 'alpha_unavailable', 'Alpha cap catalogue is empty')
        choices, seen = [], set()
        for clone in rows:
            identity, label = clone.ID, clone.alphaCloneName
            require(type(identity) is int and 0 < identity <= 2**31-1 and identity not in seen,
                    'alpha_unavailable', 'Invalid Alpha clone identity')
            require(type(label) is str and label.strip() and len(label) <= 200 and
                    all(unicodedata.category(c) != 'Cc' and not 0xD800 <= ord(c) <= 0xDFFF for c in label),
                    'alpha_unavailable', 'Invalid Alpha clone name')
            require(clone.skills, 'alpha_unavailable', 'Alpha cap table is empty')
            skills = set()
            for row in clone.skills:
                require(type(row.typeID) is int and row.typeID in skill_ids and row.typeID not in skills and
                        type(row.level) is int and 0 <= row.level <= 5 and
                        type(row.alphaCloneID) is int and row.alphaCloneID == identity,
                        'alpha_unavailable', 'Malformed Alpha cap row')
                skills.add(row.typeID)
            seen.add(identity)
            choices.append(dict(alpha_clone_id=identity, name=label))
        return dict(available=True, clones=sorted(choices, key=lambda row: row['alpha_clone_id']), error=None)
    except Exception:
        return dict(available=False, clones=[], error='Source Alpha cap data is missing, empty or malformed')


def materialize(record, *, include_implants=True):
    from eos.saveddata.character import Character
    # Validated custom records cannot use these reserved names. Preserve the
    # builtin All 0 active/learned side effect of EOS Skill.level as well as its
    # effective level; a custom unlearned character must keep the neutral name.
    eos_name = record['name'] if record['name'] in ('All 0', 'All 5') else 'Offline profile inputs'
    character = Character(eos_name, defaultLevel=record['default_level'])
    from android_bridge.pilot_security import number
    character.secStatus = number(record['sec_status'])
    for skill_id, value in record['levels'].items():
        character.getSkill(int(skill_id)).setLevel(value, persist=True, ignoreRestrict=True)
    clone = record.get('alpha_clone_id')
    if clone is not None:
        catalogue = alpha_catalogue(character.getSkillIDMap())
        require(type(clone) is int and clone in {row['alpha_clone_id'] for row in catalogue['clones']},
                'alpha_unavailable', 'Alpha clone is unknown or unavailable')
    character.alphaCloneID = clone
    if include_implants:
        from android_bridge.character_implants import catalogue, validate
        from eos.saveddata.implant import Implant
        validate(record.get('implants', []))
        for row in record.get('implants', []):
            implant = Implant(catalogue(row['item_id'])[0])
            implant.active = row['active']
            character.implants.append(implant)
    return character


def capture(character):
    return {str(skill.itemID): skill.activeLevel for skill in character.skills
            if skill.activeLevel != character.defaultLevel}


def edit_level(record, skill_id, new_level):
    """Return detached EOS-normalized overrides; caller places them in a draft."""
    level(new_level)
    require(type(skill_id) is int and skill_id > 0, 'skill', 'Invalid skill identity')
    # Read-only dependency normalization owns no fit, ORM session, or implants.
    # A same scalar can still change dependents under EOS strictSkillLevels.
    character = materialize(record, include_implants=False)
    require(skill_id in character.getSkillIDMap(), 'skill', 'Unknown skill identity')
    character.getSkill(skill_id).setLevel(new_level, persist=True)
    return capture(character)
