from contextlib import redirect_stdout
import io
from pathlib import Path
import unittest

from build_gear_rows import (ARMOR_CLASSES, ARMOR_SLOTS, BEAST_FORBIDDEN_PARTS,
                             CLOTHING_SLOTS, OBJECTIVES, WEAPON_ROWS, armor_class,
                             assemble, beast_wearable, best, main, objectives_from, row_key,
                             strength, toggle_sets, variant)
from evaluate_policy import load_policy
from export_items import ExportError

SETTINGS = {'ihelmweight': 5, 'icuirassweight': 30, 'igreavesweight': 15, 'ishieldweight': 15,
            'ibootsweight': 20, 'ipauldronweight': 10, 'igauntletweight': 5,
            'flightmaxmod': 0.6, 'fmedmaxmod': 0.9}
POLICY = {'earlyGame': {'allowTheft': False, 'allowEndgameEarly': False,
                        'nearStart': {'required': False, 'places': ['balmora']}}}


def armour(kind, weight, rating=10):
    return {'recordType': 'ARMO', 'type': kind, 'weight': weight, 'armorRating': rating,
            'key': kind, 'name': kind, 'value': 100}


def candidate(name, strength_value, near, price=None, beast=True, enchantment=0):
    return {'key': name, 'name': name, 'strength': strength_value, 'nearStart': near,
            'enchantment': enchantment, 'beastWearable': beast,
            'price': price, 'acquisition': 'take', 'cellKey': 'somewhere'}


class ArmourClassTests(unittest.TestCase):
    def test_thresholds_match_the_engine(self):
        # iHelmWeight 5: light at or under 3.0, medium at or under 4.5, heavy above.
        self.assertEqual(armor_class(armour('helmet', 3.0), SETTINGS), 'light')
        self.assertEqual(armor_class(armour('helmet', 3.01), SETTINGS), 'medium')
        self.assertEqual(armor_class(armour('helmet', 4.5), SETTINGS), 'medium')
        self.assertEqual(armor_class(armour('helmet', 4.51), SETTINGS), 'heavy')

    def test_each_slot_uses_its_own_threshold(self):
        self.assertEqual(armor_class(armour('cuirass', 18.0), SETTINGS), 'light')
        self.assertEqual(armor_class(armour('helmet', 18.0), SETTINGS), 'heavy')

    def test_bracers_borrow_the_gauntlet_threshold(self):
        for kind in ('left_bracer', 'right_bracer', 'left_gauntlet'):
            self.assertEqual(armor_class(armour(kind, 3.0), SETTINGS), 'light')
            self.assertEqual(armor_class(armour(kind, 5.0), SETTINGS), 'heavy')

    def test_a_missing_setting_is_an_error_not_a_guess(self):
        with self.assertRaises(ExportError):
            armor_class(armour('helmet', 1), {'flightmaxmod': 0.6, 'fmedmaxmod': 0.9})


class StrengthTests(unittest.TestCase):
    def test_armour_ranks_on_rating(self):
        self.assertEqual(strength(armour('helmet', 1, rating=45)), 45)

    def test_weapons_rank_on_their_best_attack(self):
        record = {'recordType': 'WEAP', 'chop': {'min': 1, 'max': 20},
                  'slash': {'min': 1, 'max': 31}, 'thrust': {'min': 1, 'max': 5}}
        self.assertEqual(strength(record), 31)

    def test_clothing_ranks_on_enchantment_capacity(self):
        self.assertEqual(strength({'recordType': 'CLOT', 'enchantp': 1200}), 1200)
        self.assertEqual(strength({'recordType': 'CLOT', 'enchantp': None}), 0)


class RowKeyTests(unittest.TestCase):
    def test_shields_are_their_own_category_but_still_split_by_class(self):
        self.assertEqual(row_key(armour('shield', 8), SETTINGS), ('shield', None, 'light', None))
        self.assertEqual(row_key(armour('shield', 14), SETTINGS), ('shield', None, 'heavy', None))

    def test_armour_splits_by_slot_and_class(self):
        self.assertEqual(row_key(armour('boots', 5), SETTINGS), ('armor', 'boots', 'light', None))

    def test_weapons_split_by_skill_and_handedness(self):
        for kind, expected in [('SB1H', ('short_blade', 1)), ('LB2H', ('long_blade', 2)),
                               ('BL2C', ('blunt', 2)), ('BL2W', ('blunt', 2)), ('THROWN', ('marksman', 1))]:
            self.assertEqual(row_key({'recordType': 'WEAP', 'type': kind}, SETTINGS),
                             ('weapon', None, None, expected))

    def test_ammunition_has_no_row(self):
        for kind in ('ARROW', 'BOLT'):
            self.assertIsNone(row_key({'recordType': 'WEAP', 'type': kind}, SETTINGS))

    def test_clothing_slots_are_listed_explicitly(self):
        self.assertEqual(row_key({'recordType': 'CLOT', 'type': 'ring'}, SETTINGS),
                         ('clothing', 'ring', None, None))
        self.assertIsNone(row_key({'recordType': 'CLOT', 'type': 'tail'}, SETTINGS))


class ToggleTests(unittest.TestCase):
    def test_every_combination_appears_once(self):
        sets = toggle_sets()
        self.assertEqual(len(sets), 8)
        self.assertEqual(len({tuple(sorted(t.items())) for t in sets}), 8)

    def test_a_variant_does_not_mutate_the_source_policy(self):
        rules = variant(POLICY, {'theft': True, 'endgame': True, 'nearStart': True})
        self.assertTrue(rules['earlyGame']['allowTheft'])
        self.assertTrue(rules['earlyGame']['allowEndgameEarly'])
        self.assertTrue(rules['earlyGame']['nearStart']['required'])
        self.assertFalse(POLICY['earlyGame']['allowTheft'])
        self.assertFalse(POLICY['earlyGame']['nearStart']['required'])


class BeastRaceTests(unittest.TestCase):
    """Argonians and Khajiit cannot equip anything covering the head or a foot.

    MWClass::Armor::canBeEquipped refuses on ESM::PRT_Head, PRT_LFoot or PRT_RFoot, so
    an open helm that dresses PRT_Hair is fine and a closed one is not. Measured on the
    real catalogs: 45 of 79 vanilla helmets are closed, and every one of the 37 boots.
    """
    def test_a_closed_helm_is_refused(self):
        self.assertFalse(beast_wearable({'bodyParts': [{'slot': 0, 'male': 'a_helm'}]}))

    def test_an_open_helm_dresses_the_hair_and_is_allowed(self):
        self.assertTrue(beast_wearable({'bodyParts': [{'slot': 1, 'male': 'a_helm'}]}))

    def test_boots_are_refused_on_either_foot(self):
        for slot in (15, 16):
            self.assertFalse(beast_wearable({'bodyParts': [{'slot': slot}]}), slot)

    def test_ankles_and_knees_are_not_feet(self):
        # Boots reference ankles too, but an ankle alone does not forbid the item.
        self.assertTrue(beast_wearable({'bodyParts': [{'slot': 17}, {'slot': 19}]}))

    def test_one_forbidden_part_among_several_is_enough(self):
        self.assertFalse(beast_wearable({'bodyParts': [{'slot': 17}, {'slot': 15}]}))

    def test_an_item_with_no_body_parts_is_unrestricted(self):
        # Weapons carry none, and the engine never reaches the check for them.
        self.assertTrue(beast_wearable({}))
        self.assertTrue(beast_wearable({'bodyParts': None}))

    def test_the_forbidden_parts_are_the_engine_s_own_numbers(self):
        self.assertEqual(sorted(BEAST_FORBIDDEN_PARTS), [0, 15, 16])


class ObjectiveTests(unittest.TestCase):
    """A row is answered once per objective; the two often disagree."""
    def rows(self, candidates, objectives=('power', 'enchantment')):
        key = ('armor', 'cuirass', 'heavy', None)
        buckets = {key: {(False, False, False): candidates}}
        return {r['key']: r for r in assemble(buckets, {'armor'}, objectives)
                if r['slot'] == 'cuirass' and r['armorClass'] == 'heavy'
                and r['toggles'] == {'theft': False, 'endgame': False, 'nearStart': False}}

    def test_each_objective_gets_its_own_row(self):
        rows = self.rows([candidate('a', 10, True)])
        self.assertEqual(sorted(rows), ['armor/cuirass/heavy/000/enchantment',
                                        'armor/cuirass/heavy/000/power'])

    def test_the_objectives_can_choose_differently(self):
        # Eleidon's Ward is the real case: huge capacity, ordinary protection.
        tough = candidate('tough', 80, True, enchantment=100)
        capacious = candidate('capacious', 20, True, enchantment=3000)
        rows = self.rows([tough, capacious])
        self.assertEqual(rows['armor/cuirass/heavy/000/power']['primary']['key'], 'tough')
        self.assertEqual(rows['armor/cuirass/heavy/000/enchantment']['primary']['key'],
                         'capacious')

    def test_a_row_says_which_objective_it_answered(self):
        rows = self.rows([candidate('a', 10, True)])
        self.assertEqual(rows['armor/cuirass/heavy/000/power']['objective'], 'power')
        self.assertEqual(rows['armor/cuirass/heavy/000/enchantment']['objective'],
                         'enchantment')

    def test_the_or_row_is_judged_on_the_same_objective(self):
        near = candidate('near', 50, True, enchantment=10)
        far = candidate('far', 10, False, enchantment=9000)
        rows = self.rows([near, far])
        # On power the far piece is weaker, so it earns no "or".
        self.assertIsNone(rows['armor/cuirass/heavy/000/power']['alternative'])
        # On capacity it is far better, so it does.
        self.assertEqual(rows['armor/cuirass/heavy/000/enchantment']['alternative']['key'],
                         'far')

    def test_the_beast_pick_follows_the_objective_too(self):
        rows = self.rows([candidate('closed', 90, True, enchantment=1, beast=False),
                          candidate('open-weak', 5, True, enchantment=5000, beast=True)])
        self.assertEqual(rows['armor/cuirass/heavy/000/power']['beastPrimary']['key'],
                         'open-weak')
        self.assertEqual(rows['armor/cuirass/heavy/000/enchantment']['beastPrimary']['key'],
                         'open-weak')

    def test_one_objective_gives_the_old_row_count(self):
        self.assertEqual(len(self.rows([candidate('a', 1, True)], ('power',))), 1)

    def test_an_objective_the_builder_cannot_measure_is_refused(self):
        with self.assertRaises(ExportError) as caught:
            objectives_from({'objectives': ['power', 'lightest']})
        self.assertIn('lightest', str(caught.exception))

    def test_no_objectives_named_falls_back_to_power(self):
        self.assertEqual(objectives_from({}), ['power'])

    def test_the_shipped_policy_asks_for_both(self):
        policy = load_policy(Path(__file__).parent/'policy/early-game.json')
        self.assertEqual(objectives_from(policy), ['power', 'enchantment'])


class BeastRowTests(unittest.TestCase):
    """A row carries a beast race's own pick, because it is often a different item."""
    def rows(self, candidates):
        key = ('armor', 'helmet', 'light', None)
        buckets = {key: {(False, False, False): candidates}}
        return [r for r in assemble(buckets, {'armor'})
                if r['slot'] == 'helmet' and r['armorClass'] == 'light'
                and r['toggles'] == {'theft': False, 'endgame': False, 'nearStart': False}][0]

    def test_a_beast_gets_the_best_helm_it_can_actually_wear(self):
        row = self.rows([candidate('closed', 50, True, beast=False),
                         candidate('open', 20, True, beast=True)])
        self.assertEqual(row['primary']['key'], 'closed')
        self.assertEqual(row['beastPrimary']['key'], 'open',
                         'the stronger helm is unequippable, so it is not the answer')
        self.assertEqual(row['beastEligible'], 1)

    def test_a_row_with_nothing_wearable_says_so_rather_than_lying(self):
        # Every boots row in the game is this: all 37 vanilla boots cover a foot.
        row = self.rows([candidate('boots', 50, True, beast=False)])
        self.assertIsNotNone(row['primary'])
        self.assertIsNone(row['beastPrimary'])
        self.assertEqual(row['beastEligible'], 0)

    def test_an_unrestricted_row_gives_a_beast_the_same_pick(self):
        row = self.rows([candidate('cuirass', 50, True), candidate('worse', 10, True)])
        self.assertEqual(row['beastPrimary']['key'], row['primary']['key'])
        self.assertEqual(row['beastEligible'], 2)

    def test_the_beast_pick_prefers_a_close_source_like_the_primary_does(self):
        row = self.rows([candidate('far-open', 50, False, beast=True),
                         candidate('near-open', 20, True, beast=True)])
        self.assertEqual(row['beastPrimary']['key'], 'near-open')


class AssembleTests(unittest.TestCase):
    def rows(self, buckets, categories=('armor', 'shield', 'weapon', 'clothing')):
        return assemble(buckets, set(categories))

    def shield_row(self, buckets, toggles=(False, False, False), armour='light'):
        theft, endgame, near = toggles
        return next(r for r in self.rows(buckets) if r['category'] == 'shield'
                    and r['armorClass'] == armour
                    and r['toggles'] == {'theft': theft, 'endgame': endgame, 'nearStart': near})

    def test_one_row_per_slot_per_toggle_combination(self):
        rows = self.rows({})
        expected = ((len(ARMOR_SLOTS) + 1)*len(ARMOR_CLASSES)
                    + len(set(WEAPON_ROWS.values())) + len(CLOTHING_SLOTS))
        self.assertEqual(len(rows), expected*8)
        self.assertTrue(all(row['primary'] is None for row in rows))

    def test_every_row_has_a_unique_stable_key(self):
        rows = self.rows({})
        keys = [r['key'] for r in rows]
        self.assertEqual(len(set(keys)), len(rows), 'keys must be unique across every row')
        self.assertIn('armor/helmet/light/000/power', keys)
        self.assertIn('shield/-/heavy/111/power', keys)
        self.assertIn('weapon/short_blade-1h/-/000/power', keys)
        self.assertIn('clothing/ring/-/010/power', keys)

    def test_the_key_encodes_the_toggle_set(self):
        rows = {r['key']: r for r in self.rows({}) if r['category'] == 'shield'}
        self.assertEqual(rows['shield/-/light/101/power']['toggles'],
                         {'theft': True, 'endgame': False, 'nearStart': True})

    def test_categories_can_be_built_separately(self):
        self.assertEqual(len(self.rows({}, ('shield',))), len(ARMOR_CLASSES)*8)
        self.assertEqual(len(self.rows({}, ('clothing',))), len(CLOTHING_SLOTS)*8)

    def test_the_closest_source_wins_even_when_weaker(self):
        key = ('shield', None, 'light', None)
        buckets = {key: {(False, False, False): [candidate('near shield', 10, True),
                                                 candidate('far shield', 90, False)]}}
        row = self.shield_row(buckets)
        self.assertEqual(row['primary']['name'], 'near shield')
        self.assertEqual(row['alternative']['name'], 'far shield')
        self.assertEqual((row['eligible'], row['nearStart']), (2, 1))

    def test_no_or_row_when_the_far_piece_is_not_stronger(self):
        key = ('shield', None, 'light', None)
        buckets = {key: {(False, False, False): [candidate('near', 50, True), candidate('far', 50, False)]}}
        row = self.shield_row(buckets)
        self.assertEqual(row['primary']['name'], 'near')
        self.assertIsNone(row['alternative'], 'an equal piece farther away earns no row')

    def test_a_far_piece_fills_the_row_when_nothing_is_close(self):
        key = ('shield', None, 'light', None)
        buckets = {key: {(False, False, False): [candidate('far', 20, False)]}}
        row = self.shield_row(buckets)
        self.assertEqual(row['primary']['name'], 'far')
        self.assertIsNone(row['alternative'], 'the far piece is already the primary')

    def test_toggle_buckets_do_not_leak_into_each_other(self):
        key = ('shield', None, 'light', None)
        buckets = {key: {(True, False, False): [candidate('stolen', 40, True)]}}
        self.assertEqual(self.shield_row(buckets, (True, False, False))['primary']['name'], 'stolen')
        self.assertIsNone(self.shield_row(buckets, (False, False, False))['primary'])

    def test_cheaper_wins_a_tie_on_strength(self):
        self.assertEqual(best([candidate('dear', 10, True, price=400),
                               candidate('cheap', 10, True, price=27)])['name'], 'cheap')
        self.assertIsNone(best([]))


class PartialRunTests(unittest.TestCase):
    """A partial run must not land where the bundler takes the newest rows from."""
    def refused(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = main(list(argv))
        return code, out.getvalue()

    def test_a_smoke_run_without_its_own_folder_is_refused(self):
        code, said = self.refused('--limit', '60')
        self.assertEqual(code, 1)
        self.assertIn('--output', said)

    def test_a_limit_of_zero_is_still_a_partial_run(self):
        # 0 is falsy; the guard asks "was a limit given", not "is it truthy".
        self.assertEqual(self.refused('--limit', '0')[0], 1)

    def test_a_category_run_is_partial_too_because_nothing_merges_it(self):
        code, said = self.refused('--profile', 'vanilla', '--category', 'weapon')
        self.assertEqual(code, 1)
        self.assertIn('in place of the full ones', said)


if __name__ == '__main__':
    unittest.main()
