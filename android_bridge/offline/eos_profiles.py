"""Translate a validated C06 record to EOS, preserving unlearned versus level 0.

EOS must already be initialized by its serialized worker. This adapter uses EOS
for skill dependency normalization; it contains no requirement/skill formula.
Alpha clone remains outside this bounded slice.
"""
from .profiles import level, require


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
