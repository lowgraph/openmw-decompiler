import unittest

from build_gear_rows import (ARMOR_CLASSES, ARMOR_SLOTS, CLOTHING_SLOTS, WEAPON_ROWS,
                             armor_class, assemble, best, row_key, strength, toggle_sets, variant)
from export_items import ExportError

SETTINGS = {'ihelmweight': 5, 'icuirassweight': 30, 'igreavesweight': 15, 'ishieldweight': 15,
            'ibootsweight': 20, 'ipauldronweight': 10, 'igauntletweight': 5,
            'flightmaxmod': 0.6, 'fmedmaxmod': 0.9}
POLICY = {'earlyGame': {'allowTheft': False, 'allowEndgameEarly': False,
                        'nearStart': {'required': False, 'places': ['balmora']}}}


def armour(kind, weight, rating=10):
    return {'recordType': 'ARMO', 'type': kind, 'weight': weight, 'armorRating': rating,
            'key': kind, 'name': kind, 'value': 100}


def candidate(name, strength_value, near, price=None):
    return {'key': name, 'name': name, 'strength': strength_value, 'nearStart': near,
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
        self.assertEqual(len(set(keys)), len(rows), 'keys must be unique across all 424 rows')
        self.assertIn('armor/helmet/light/000', keys)
        self.assertIn('shield/-/heavy/111', keys)
        self.assertIn('weapon/short_blade-1h/-/000', keys)
        self.assertIn('clothing/ring/-/010', keys)

    def test_the_key_encodes_the_toggle_set(self):
        rows = {r['key']: r for r in self.rows({}) if r['category'] == 'shield'}
        self.assertEqual(rows['shield/-/light/101']['toggles'],
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


if __name__ == '__main__':
    unittest.main()
