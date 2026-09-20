import json
from pathlib import Path
import tempfile
import unittest

import autocalc
from export_items import ExportError

# A stripped reference set: two attributes' worth of skills, enough to exercise every
# branch without restating all 27.
SKILLS = [
    {'skill': 'mercantile', 'governingAttribute': 'personality', 'specialization': 'stealth'},
    {'skill': 'speechcraft', 'governingAttribute': 'personality', 'specialization': 'stealth'},
    {'skill': 'security', 'governingAttribute': 'agility', 'specialization': 'stealth'},
    {'skill': 'block', 'governingAttribute': 'agility', 'specialization': 'combat'},
]
RACE = {'key': 'imperial',
        'attributes': {'personality': {'male': 50, 'female': 50},
                       'agility': {'male': 40, 'female': 40},
                       'luck': {'male': 40, 'female': 45}},
        'skillBonuses': [{'skill': 'mercantile', 'bonus': 10},
                         {'skill': 'speechcraft', 'bonus': 10}]}
CLASS = {'key': 'trader', 'specialization': 'stealth',
         'favoredAttributes': ['personality', 'luck'],
         'majorSkills': ['mercantile'], 'minorSkills': ['speechcraft']}


def reference():
    return {'races': {'imperial': RACE}, 'classes': {'trader': CLASS}, 'skills': SKILLS}


class SkillTests(unittest.TestCase):
    """autoCalculateSkills, apps/openmw/mwclass/npc.cpp."""
    def at(self, level):
        return autocalc.skills(RACE, CLASS, level, SKILLS)

    def test_a_major_skill_at_level_one(self):
        # 25 major + 5 every skill + 10 race bonus + 5 specialisation, no level term.
        self.assertEqual(self.at(1)['mercantile'], 45)

    def test_a_minor_skill_at_level_one(self):
        self.assertEqual(self.at(1)['speechcraft'], 30)  # 10 + 5 + 10 + 5

    def test_a_miscellaneous_skill_in_the_class_specialisation(self):
        self.assertEqual(self.at(1)['security'], 10)  # 0 + 5 + 0 + 5

    def test_a_miscellaneous_skill_outside_it(self):
        self.assertEqual(self.at(1)['block'], 5)  # 0 + 5 only

    def test_a_major_specialised_skill_rises_by_one_and_a_half_a_level(self):
        # majority 1.0 + specialisation 0.5
        self.assertEqual(self.at(11)['mercantile'] - self.at(1)['mercantile'], 15)

    def test_a_miscellaneous_skill_outside_the_specialisation_barely_moves(self):
        self.assertEqual(self.at(11)['block'] - self.at(1)['block'], 1)  # 10 x 0.1

    def test_a_skill_never_exceeds_one_hundred(self):
        self.assertEqual(self.at(200)['mercantile'], 100)

    def test_level_zero_is_handled_rather_than_going_negative(self):
        # The engine's comment says "Must gracefully handle level 0".
        self.assertLessEqual(self.at(0)['mercantile'], self.at(1)['mercantile'])


class AttributeTests(unittest.TestCase):
    """autoCalculateAttributes, same file."""
    def at(self, level, female=False):
        return autocalc.attributes(RACE, CLASS, level, female, SKILLS)

    def test_a_favoured_attribute_gets_ten_over_the_race_value(self):
        self.assertEqual(self.at(1)['personality'], 60)  # 50 race + 10 favoured

    def test_an_unfavoured_attribute_is_the_race_value(self):
        self.assertEqual(self.at(1)['agility'], 40)

    def test_gender_selects_the_race_value(self):
        self.assertEqual(self.at(1)['luck'], 50)          # 40 male + 10 favoured
        self.assertEqual(self.at(1, female=True)['luck'], 55)

    def test_an_attribute_rises_by_the_weight_of_the_skills_it_governs(self):
        # personality governs mercantile (major, 1.0) and speechcraft (minor, 0.5)
        self.assertEqual(self.at(11)['personality'] - self.at(1)['personality'], 15)

    def test_an_attribute_governing_only_miscellaneous_skills_rises_slowly(self):
        # agility governs security and block, both miscellaneous: 0.2 each
        self.assertEqual(self.at(11)['agility'] - self.at(1)['agility'], 4)

    def test_an_attribute_never_exceeds_one_hundred(self):
        self.assertEqual(self.at(500)['personality'], 100)


class LevelOneEquivalenceTests(unittest.TestCase):
    """At level 1 the (level - 1) terms vanish.

    That is what makes this checkable at all: autocalc then reduces to exactly what
    character creation produces, and the user's 96 saves are almost all level 1. See
    MERCHANTS.md — 32 of 49 characters matched exactly, 15 more once their birthsign's
    Fortify Attribute was added, and no skill was ever *below* the prediction.
    """
    def test_no_level_term_contributes_at_level_one(self):
        skills = autocalc.skills(RACE, CLASS, 1, SKILLS)
        self.assertEqual(skills['mercantile'],
                         autocalc.MAJOR_SKILL_BONUS + autocalc.EVERY_SKILL_BONUS
                         + 10 + autocalc.SPECIALISATION_BONUS)

    def test_attributes_at_level_one_are_race_plus_favoured_only(self):
        found = autocalc.attributes(RACE, CLASS, 1, False, SKILLS)
        self.assertEqual(found['personality'], 50 + autocalc.FAVOURED_ATTRIBUTE_BONUS)
        self.assertEqual(found['agility'], 40)


class DeriveTests(unittest.TestCase):
    def test_it_returns_the_three_stats_barter_needs(self):
        found = autocalc.derive(reference(), 'Imperial', 'Trader', 9, False)
        self.assertEqual(sorted(found), ['luck', 'mercantile', 'personality'])
        self.assertEqual(found['mercantile'], 57)

    def test_lookup_ignores_case_because_records_do_not_agree_on_it(self):
        self.assertIsNotNone(autocalc.derive(reference(), 'IMPERIAL', 'trader', 5, False))

    def test_an_unknown_class_derives_nothing_rather_than_guessing(self):
        self.assertIsNone(autocalc.derive(reference(), 'Imperial', 'Jeweler', 9, False))

    def test_an_unknown_race_derives_nothing(self):
        # A creature has no race, and the engine never autocalculates one this way.
        self.assertIsNone(autocalc.derive(reference(), None, 'Trader', 9, False))

    def test_a_missing_level_derives_nothing(self):
        self.assertIsNone(autocalc.derive(reference(), 'Imperial', 'Trader', None, False))


class ReferenceTests(unittest.TestCase):
    def test_a_missing_catalog_fails_loudly(self):
        with self.assertRaises(ExportError) as caught:
            autocalc.reference(Path(tempfile.mkdtemp()), 'vanilla')
        self.assertIn('autocalc', str(caught.exception))

    def test_it_keys_races_and_classes_for_lookup(self):
        root = Path(tempfile.mkdtemp())
        (root/'vanilla').mkdir()
        for name, records in (('Races', [RACE]), ('Classes', [CLASS]), ('Skills', SKILLS)):
            (root/'vanilla'/(name+'.json')).write_text(
                json.dumps({'records': records}), encoding='utf-8')
        loaded = autocalc.reference(root, 'vanilla')
        self.assertIn('imperial', loaded['races'])
        self.assertIn('trader', loaded['classes'])
        self.assertEqual(len(loaded['skills']), len(SKILLS))


if __name__ == '__main__':
    unittest.main()
