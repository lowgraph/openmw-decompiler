"""Work out the stats the engine derives for an auto-calculated actor.

One NPC in five stores no skills and no attributes: its record sets the autocalc flag
and OpenMW computes everything from race, class and level when the game loads. Nothing
in the plugin files can be extracted for them, so a merchant's Mercantile — which
decides what it charges — is simply absent.

Both routines are transcribed from apps/openmw/mwclass/npc.cpp, autoCalculateAttributes
and autoCalculateSkills. See MERCHANTS.md for how they were checked against 49 real
level-1 characters, where the (level - 1) terms vanish and the result is exactly what
character creation produces.

Level 1 never rounds, so that check could not reach the rounding. The source did: at tag
openmw-0.51.0, npc.cpp defines its own round_ieee_754, which rounds ties to even exactly
as Python's round() does. The release this was checked against is TRANSCRIBED_FROM in
build_merchant_catalog.py, and the build stops when the extraction names another.
"""
from __future__ import annotations

import json
from pathlib import Path

from export_items import ExportError

# autoCalculateAttributes: every skill governed by an attribute contributes to how fast
# that attribute rises with level.
MAJOR_ATTRIBUTE_WEIGHT = 1.0
MINOR_ATTRIBUTE_WEIGHT = 0.5
MISC_ATTRIBUTE_WEIGHT = 0.2
FAVOURED_ATTRIBUTE_BONUS = 10
# autoCalculateSkills.
MAJOR_SKILL_BONUS = 25
MINOR_SKILL_BONUS = 10
EVERY_SKILL_BONUS = 5
SPECIALISATION_BONUS = 5
SPECIALISATION_MULTIPLIER = 0.5
MAJORITY_MULTIPLIER = 1.0
MISC_MULTIPLIER = 0.1
CEILING = 100.0


def reference(catalogs, profile):
    """Races, classes and skills, keyed for lookup, from a catalog release."""
    loaded = {}
    for name in ('Races', 'Classes', 'Skills'):
        path = Path(catalogs)/profile/(name+'.json')
        if not path.is_file():
            raise ExportError(f'Catalog missing for autocalc: {path}')
        loaded[name] = json.loads(path.read_text(encoding='utf-8'))['records']
    return {'races': {r['key'].casefold(): r for r in loaded['Races']},
            'classes': {c['key'].casefold(): c for c in loaded['Classes']},
            'skills': loaded['Skills']}


def attributes(race, npc_class, level, female, skills_reference):
    """The eight attributes an auto-calculated NPC ends up with."""
    gender = 'female' if female else 'male'
    found = {name: float(value[gender]) for name, value in race['attributes'].items()}
    for favoured in npc_class['favoredAttributes']:
        if favoured in found:
            found[favoured] += FAVOURED_ATTRIBUTE_BONUS
    major = set(npc_class['majorSkills'])
    minor = set(npc_class['minorSkills'])
    for name in list(found):
        weight = 0.0
        for skill in skills_reference:
            if skill['governingAttribute'] != name:
                continue
            weight += (MAJOR_ATTRIBUTE_WEIGHT if skill['skill'] in major
                       else MINOR_ATTRIBUTE_WEIGHT if skill['skill'] in minor
                       else MISC_ATTRIBUTE_WEIGHT)
        # round() is half-to-even, matching the engine's round_ieee_754.
        found[name] = min(float(round(found[name] + (level - 1) * weight)), CEILING)
    return found


def skills(race, npc_class, level, skills_reference):
    """Every skill an auto-calculated NPC ends up with."""
    bonus = {b['skill']: b['bonus'] for b in race['skillBonuses']}
    major = set(npc_class['majorSkills'])
    minor = set(npc_class['minorSkills'])
    found = {}
    for skill in skills_reference:
        slug = skill['skill']
        value = (MAJOR_SKILL_BONUS if slug in major
                 else MINOR_SKILL_BONUS if slug in minor else 0.0)
        specialised = skill['specialization'] == npc_class['specialization']
        value += EVERY_SKILL_BONUS + bonus.get(slug, 0) + (SPECIALISATION_BONUS if specialised else 0)
        majority = MAJORITY_MULTIPLIER if slug in major or slug in minor else MISC_MULTIPLIER
        value += (level - 1) * (majority + (SPECIALISATION_MULTIPLIER if specialised else 0.0))
        found[slug] = min(float(round(value)), CEILING)
    return found


def derive(reference_data, race_key, class_key, level, female):
    """Barter-relevant stats for one actor, or None when it cannot be worked out.

    A creature has no class and no race, and a record naming a class the catalogs do
    not carry cannot be derived either. Returning None keeps the caller honest: it
    publishes null rather than a number built from a missing input.
    """
    if level is None:
        return None
    race = reference_data['races'].get((race_key or '').casefold())
    npc_class = reference_data['classes'].get((class_key or '').casefold())
    if not race or not npc_class:
        return None
    every_attribute = attributes(race, npc_class, level, female, reference_data['skills'])
    every_skill = skills(race, npc_class, level, reference_data['skills'])
    return {'mercantile': every_skill.get('mercantile'),
            'personality': every_attribute.get('personality'),
            'luck': every_attribute.get('luck')}
