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


class EnchantedTests(unittest.TestCase):
    """An enchantment already on a piece beats room for one a new character cannot afford."""

    def setUp(self):
        import json, tempfile
        from evaluate_policy import _CATEGORIES
        _CATEGORIES.clear()
        self.addCleanup(_CATEGORIES.clear)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.catalogs = Path(folder.name)
        (self.catalogs/'p').mkdir()
        def effect(effect_id, name, low, high, seconds=1, reach='self', **extra):
            return {'effectId': effect_id, 'name': name, 'magnitude': {'min': low, 'max': high},
                    'durationSeconds': seconds, 'range': reach, 'areaFeet': 0,
                    'attribute': extra.get('attribute'), 'skill': extra.get('skill')}
        records = {
            'Enchantments': [
                {'key': "The Master's Circle", 'castType': 'constant_effect', 'cost': 0, 'charges': 0,
                 'effects': [effect(79, 'Fortify Attribute', 10, 10, attribute='intelligence'),
                             effect(79, 'Fortify Attribute', 10, 10, attribute='willpower')]},
                {'key': 'cursed_en', 'castType': 'constant_effect', 'cost': 0, 'charges': 0,
                 'effects': [effect(17, 'Drain Attribute', 5, 5, attribute='strength')]},
                {'key': 'frost_en', 'castType': 'when_strikes', 'cost': 5, 'charges': 50,
                 'effects': [effect(16, 'Frost Damage', 2, 4, seconds=3, reach='touch')]},
                {'key': 'bolt_en', 'castType': 'when_used', 'cost': 5, 'charges': 50,
                 'effects': [effect(16, 'Frost Damage', 2, 4, seconds=3, reach='target')]},
                {'key': 'recall_en', 'castType': 'when_used', 'cost': 5, 'charges': 50,
                 'effects': [effect(61, 'Recall', 1, 1, seconds=1)]}],
            'MagicEffects': [{'key': '79', 'effectId': 79, 'baseCost': 1, 'name': 'Fortify Attribute'},
                             {'key': '17', 'effectId': 17, 'baseCost': 1, 'name': 'Drain Attribute'},
                             {'key': '16', 'effectId': 16, 'baseCost': 5, 'name': 'Frost Damage'},
                             {'key': '61', 'effectId': 61, 'baseCost': 350, 'name': 'Recall'}],
            'GameSettings': [{'key': 'fEffectCostMult', 'value': 0.5},
                             {'key': 'fEnchantmentConstantDurationMult', 'value': 100}]}
        for name, rows in records.items():
            (self.catalogs/'p'/f'{name}.json').write_text(json.dumps({'records': rows}), encoding='utf-8')

    FLAGS = {17: {'harmful': True}, 61: {'noMagnitude': True, 'noDuration': True}}

    def spell(self, enchantment_id, flags=FLAGS):
        from build_gear_rows import enchanted
        return enchanted({'enchantmentId': enchantment_id}, self.catalogs, 'p', flags)

    def test_a_constant_effect_is_worth_what_the_engine_charges_to_make_it(self):
        mentor = self.spell("the master's circle")
        # ((10 + 10) x 100 + 1) x 1 x 0.5 x 0.05 per attribute: about 100 in all, against
        # an Exquisite Ring's 120 of room. The record's own cost says 0.
        self.assertEqual(mentor['worth'], 100.1)
        self.assertEqual(mentor['castType'], 'constant_effect')
        self.assertEqual([(e['attribute'], e['min'], e['seconds']) for e in mentor['effects']],
                         [('intelligence', 10, None), ('willpower', 10, None)])

    def test_a_curse_on_the_wearer_counts_against(self):
        cursed = self.spell('cursed_en')
        self.assertLess(cursed['worth'], 0)
        self.assertTrue(cursed['effects'][0]['drawback'])
        self.assertGreater(self.spell('cursed_en', flags={})['worth'], 0,
                           'harm is read from the rules library, not guessed')

    def test_a_charged_effect_lasts_its_own_seconds_and_costs_more_at_range(self):
        touch, target = self.spell('frost_en'), self.spell('bolt_en')
        self.assertEqual(touch['worth'], 2.4)  # ((2 + 4) x 3 + 1) x 5 x 0.025 = 2.375
        self.assertEqual(target['worth'], 3.6)  # half again at range: 3.5625
        self.assertEqual((touch['charges'], touch['effects'][0]['seconds']), (50, 3))
        self.assertIsNone(self.spell('nothing'))

    def test_an_effect_without_magnitude_or_duration_shows_neither(self):
        recall = self.spell('recall_en')
        self.assertEqual((recall['effects'][0]['min'], recall['effects'][0]['seconds']), (None, None))
        self.assertEqual(recall['worth'], 8.8, '(2 x 0 + 1) x 350 x 0.025 = 8.75, priced as the engine does')

    def ring(self, name, capacity, worth=None):
        spell = None if worth is None else {'worth': worth, 'effects': []}
        return candidate(name, capacity, True, enchantment=capacity) | {'enchanted': spell}

    def test_clothing_wears_an_enchantment_before_room_for_one(self):
        from build_gear_rows import best
        mentor, exquisite, cursed = self.ring('mentor', 100, 100.1), self.ring('exquisite', 1200), \
            self.ring('cursed', 5000, -12.5)
        self.assertEqual(best([exquisite, mentor, cursed], 'power', 'clothing')['key'], 'mentor')
        self.assertEqual(best([exquisite, cursed], 'power', 'clothing')['key'], 'exquisite',
                         'a curse is worse than nothing')
        self.assertEqual(best([exquisite, mentor, cursed], 'enchantment', 'clothing')['key'], 'exquisite',
                         'only a blank piece takes your own enchantment')

    def test_armour_ranks_on_protection_and_an_enchantment_breaks_a_tie(self):
        from build_gear_rows import best
        plain = candidate('plain', 20, True)
        charmed = candidate('charmed', 20, True) | {'enchanted': {'worth': 30}}
        heavier = candidate('heavier', 25, True)
        self.assertEqual(best([plain, charmed], 'power', 'armor')['key'], 'charmed')
        self.assertEqual(best([plain, charmed, heavier], 'power', 'armor')['key'], 'heavier')

    TABLE = {'tiers': {'essential': 1.0, 'situational': 0.5, 'convenience': 0.2, 'none': 0.0},
             'defaultTier': 'situational',
             'effects': {'essential': ['Fortify Attribute'], 'convenience': ['Frost Damage'],
                         'none': ['Drain Attribute']}}

    def weighed(self, enchantment_id, table=None):
        from build_gear_rows import Usefulness, enchanted
        usefulness = Usefulness(table or self.TABLE)
        return enchanted({'enchantmentId': enchantment_id}, self.catalogs, 'p', self.FLAGS, usefulness), usefulness

    def test_value_weighs_each_effect_by_its_tier(self):
        mentor, _ = self.weighed("the master's circle")
        self.assertEqual(mentor['value'], mentor['worth'], 'essential effects count in full')
        self.assertEqual([e['tier'] for e in mentor['effects']], ['essential', 'essential'])
        frost, _ = self.weighed('frost_en')
        self.assertAlmostEqual(frost['value'], round(2.375 * 0.2, 1))
        self.assertEqual(frost['worth'], 2.4, 'the engine cost is kept beside it')

    def test_one_attribute_can_be_tiered_apart_from_its_effect(self):
        table = self.TABLE | {'effects': self.TABLE['effects'] | {
            'convenience': ['Frost Damage', 'Fortify Attribute: willpower']}}
        mentor, _ = self.weighed("the master's circle", table)
        # Each attribute costs (20 x 100 + 1) x 0.025 = 50.025: intelligence in full,
        # willpower at 0.2.
        self.assertAlmostEqual(mentor['value'], round(50.025 + 50.025 * 0.2, 1))
        self.assertEqual([e['tier'] for e in mentor['effects']], ['essential', 'convenience'])

    def test_a_curse_counts_in_full_against_whatever_its_tier(self):
        cursed, _ = self.weighed('cursed_en')
        self.assertLess(cursed['value'], 0)
        self.assertEqual(cursed['value'], cursed['worth'], 'even in the none tier')

    def test_an_effect_the_table_does_not_place_takes_the_default_and_is_named(self):
        recall, usefulness = self.weighed('recall_en')
        self.assertEqual(recall['effects'][0]['tier'], 'situational')
        self.assertEqual(recall['value'], round(8.75 * 0.5, 1))
        self.assertEqual(usefulness.summary()['defaulted'], ['Recall'])

    def test_rows_rank_on_the_useful_value_not_the_cost(self):
        from build_gear_rows import best
        feather = self.ring('feather', 100) | {'enchanted': {'worth': 120, 'value': 24, 'effects': []}}
        fortify = self.ring('fortify', 100) | {'enchanted': {'worth': 60, 'value': 60, 'effects': []}}
        self.assertEqual(best([feather, fortify], 'power', 'clothing')['key'], 'fortify')
        older = self.ring('older', 100, 120)  # a row published before the table: worth only
        self.assertEqual(best([older, fortify], 'power', 'clothing')['key'], 'older',
                         'without a value, the worth decides as before')

    def test_without_a_table_nothing_changes(self):
        mentor = self.spell("the master's circle")
        self.assertNotIn('value', mentor)
        self.assertNotIn('tier', mentor['effects'][0])

    def test_a_table_naming_an_effect_the_profile_lacks_is_refused(self):
        from build_gear_rows import Usefulness, check_effect_names
        from export_items import ExportError
        check_effect_names(Usefulness(self.TABLE), self.catalogs, 'p')
        typo = self.TABLE | {'effects': {'essential': ['Fortify Atribute']}}
        with self.assertRaises(ExportError) as caught:
            check_effect_names(Usefulness(typo), self.catalogs, 'p')
        self.assertIn('Fortify Atribute', str(caught.exception))
        check_effect_names(Usefulness(self.TABLE | {'effects': {'essential': ['Fortify Attribute: luck']}}),
                           self.catalogs, 'p')

    def test_a_malformed_table_is_refused_by_the_policy_loader(self):
        from evaluate_policy import check_usefulness
        from export_items import ExportError
        check_usefulness(None)
        check_usefulness(self.TABLE)
        for broken in ({'tiers': {}, 'defaultTier': 'x', 'effects': {}},
                       self.TABLE | {'tiers': {'essential': 3}},
                       self.TABLE | {'tiers': {'essential': True}},
                       self.TABLE | {'defaultTier': 'legendary'},
                       self.TABLE | {'effects': {'legendary': ['Feather']}},
                       self.TABLE | {'effects': {'essential': 'Feather'}},
                       self.TABLE | {'effects': {'essential': ['Feather'], 'convenience': ['feather']}}):
            with self.assertRaises(ExportError, msg=repr(broken)):
                check_usefulness(broken)

    def test_the_shipped_policy_places_every_effect_once(self):
        from evaluate_policy import load_policy
        table = load_policy(Path(__file__).parent/'policy/early-game.json')['enchantmentUsefulness']
        names = [n for names in table['effects'].values() for n in names]
        self.assertEqual(len(names), len({n.casefold() for n in names}))
        self.assertGreaterEqual(len(names), 141, 'every vanilla effect has a tier')

    def test_the_rows_split_the_two_questions(self):
        buckets = {('clothing', 'ring', None, None): {(False, False, False): [
            self.ring('mentor', 100, 100.1), self.ring('exquisite', 1200)]}}
        rows = {r['objective']: r for r in assemble(buckets, {'clothing'}, ('power', 'enchantment'))
                if r['slot'] == 'ring' and r['toggles'] == {'theft': False, 'endgame': False, 'nearStart': False}}
        self.assertEqual(rows['power']['primary']['key'], 'mentor')
        self.assertEqual(rows['enchantment']['primary']['key'], 'exquisite')


class AmbushTests(unittest.TestCase):
    """Tribunal's assassins: gear a script sends at a sleeping player, under its own toggle."""
    AMBUSH = {'toggle': 'darkBrotherhood', 'label': 'Dark Brotherhood armor',
              'script': 'dbattackscript', 'actor': 'db_assassin1b', 'categories': ['armor'],
              'place': 'Wherever you rest', 'note': 'Worn by the assassin.'}

    def game(self, *versions):
        """A foundation with the attack script as each plugin in load order last saved it."""
        import sqlite3
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('CREATE TABLE profile_plugins(profile_id,plugin_id,load_order);'
                         'CREATE TABLE record_versions(plugin_id,record_type,record_key,payload);')
        for order, text in enumerate(versions):
            db.execute('INSERT INTO profile_plugins VALUES(?,?,?)', ('p', order + 1, order))
            db.execute("INSERT INTO record_versions VALUES(?, 'SCPT', 'dbattackscript', ?)",
                       (order + 1, b'SCHD' + text.encode('cp1252')))
        return db

    def test_the_winning_script_must_still_send_the_actor(self):
        from build_gear_rows import script_places
        sends = 'if ( playerLevel == 1 )\n\tPlaceAtPC "db_assassin1b" 1 128 1\nendif'
        self.assertTrue(script_places(self.game(sends), 'p', 'dbAttackScript', 'db_assassin1b'))
        self.assertFalse(script_places(self.game(sends, 'return'), 'p', 'dbattackscript', 'db_assassin1b'),
                         'a later plugin that rewrites the script decides')
        self.assertFalse(script_places(self.game(sends), 'p', 'dbattackscript', 'db_assassin1'),
                         'db_assassin1 is not db_assassin1b')
        self.assertFalse(script_places(self.game(), 'p', 'dbattackscript', 'db_assassin1b'))

    def graph(self, *parents):
        nodes = [{'versionId': 1, 'key': 'darkbrotherhood helm', 'recordType': 'ARMO', 'name': 'Helm'}]
        edges = []
        for version, (key, kind) in enumerate(parents, 2):
            nodes.append({'versionId': version, 'key': key, 'recordType': 'NPC_', 'name': key.title()})
            edges.append({'parentVersionId': version, 'targetVersionId': 1, 'kind': kind, 'details': {}})
        return {'nodes': nodes, 'edges': edges, 'placements': []}

    def test_only_the_named_actor_carrying_it_counts(self):
        from build_gear_rows import carried_by
        self.assertEqual(carried_by(self.graph(('db_assassin4', 'inventory'), ('DB_Assassin1b', 'inventory')),
                                    'db_assassin1b')['key'], 'DB_Assassin1b')
        self.assertIsNone(carried_by(self.graph(('db_assassin4', 'inventory')), 'db_assassin1b'))
        self.assertIsNone(carried_by(self.graph(('db_assassin1b', 'leveled')), 'db_assassin1b'))

    def test_the_pick_is_taken_from_the_body(self):
        from build_gear_rows import ambush_pick
        record = {'key': 'darkbrotherhood helm', 'name': 'Dark Brotherhood Helm', 'recordType': 'ARMO',
                  'type': 'helmet', 'armorRating': 30, 'value': 200, 'enchantp': 100}
        pick = ambush_pick(record, {'name': 'Dark Brotherhood Assassin'}, self.AMBUSH,
                           {'earlyGame': {'endgame': {'armorRating': 50, 'armorValue': 2000, 'anyValue': 10000}}})
        self.assertEqual((pick['acquisition'], pick['strength'], pick['price'], pick['cellKey']),
                         ('ambush', 30, None, None))
        self.assertEqual((pick['place'], pick['holder'], pick['note']),
                         ('Wherever you rest', 'Dark Brotherhood Assassin', 'Worn by the assassin.'))
        self.assertTrue(pick['nearStart'], 'the assassin comes to wherever you sleep')
        self.assertFalse(pick['theftRequired'] or pick['endgame'])

    def test_ambush_rows_stand_apart_and_only_where_something_is_worn(self):
        helm = candidate('darkbrotherhood helm', 30, True)
        chitin = candidate('chitin helm', 10, True)
        buckets = {('armor', 'helmet', 'medium', None): {('ambush', 'darkBrotherhood'): [helm],
                                                         (False, False, False): [chitin]}}
        rows = assemble(buckets, {'armor'}, ('power',), ['darkBrotherhood'])
        ambush = [r for r in rows if 'darkBrotherhood' in r['toggles']]
        self.assertEqual(len(ambush), 1, 'no empty ambush rows for the other slots')
        self.assertEqual(ambush[0]['key'], 'armor/helmet/medium/darkBrotherhood/power')
        self.assertEqual((ambush[0]['toggles'], ambush[0]['primary']['key']),
                         ({'darkBrotherhood': True}, 'darkbrotherhood helm'))
        plain = [r for r in rows if r['toggles'] == {'theft': False, 'endgame': False, 'nearStart': False}
                 and r['slot'] == 'helmet' and r['armorClass'] == 'medium']
        self.assertEqual(plain[0]['primary']['key'], 'chitin helm', 'the policy rows are untouched')
        self.assertEqual(len(rows), len(assemble(buckets, {'armor'}, ('power',))) + 1)

    def test_the_shipped_policy_sends_the_level_one_assassin(self):
        policy = load_policy(Path(__file__).parent/'policy/early-game.json')
        [ambush] = policy['earlyGame']['ambushes']
        self.assertEqual((ambush['toggle'], ambush['actor'], ambush['categories']),
                         ('darkBrotherhood', 'db_assassin1b', ['armor']))

    def test_a_malformed_ambush_is_refused(self):
        import copy, json, tempfile
        policy = load_policy(Path(__file__).parent/'policy/early-game.json')
        for broken in ({'categories': []}, {'toggle': 'theft'}, {'actor': ''}):
            changed = copy.deepcopy(policy)
            changed['earlyGame']['ambushes'][0].update(broken)
            with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as handle:
                json.dump(changed, handle)
            self.addCleanup(lambda name=handle.name: Path(name).unlink(missing_ok=True))
            with self.assertRaises(ExportError, msg=str(broken)):
                load_policy(handle.name)


if __name__ == '__main__':
    unittest.main()


class BoundSummonTests(unittest.TestCase):
    """A Devil Tanto costs 157 gold and conjures a Bound Dagger that hits like Daedric."""

    def setUp(self):
        import json, tempfile
        from evaluate_policy import _CATEGORIES
        _CATEGORIES.clear()
        self.addCleanup(_CATEGORIES.clear)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.catalogs = Path(folder.name)
        (self.catalogs/'p').mkdir()
        def weapon(key, name, kind, top, ench=None, value=100):
            return {'key': key, 'name': name, 'recordType': 'WEAP', 'type': kind, 'value': value,
                    'chop': {'min': 1, 'max': top}, 'slash': {'min': 1, 'max': top},
                    'thrust': {'min': 1, 'max': top}, 'enchantmentId': ench}
        records = {
            'Weapons': [weapon('devil tanto', 'Devil Tanto', 'SB1H', 6, 'Devil Tanto_en', 157),
                        weapon('bound_dagger', 'Bound Dagger', 'SB1H', 20, value=0),
                        weapon('bound_longbow', 'Bound Longbow', 'BOW', 50, value=0),
                        weapon('stinger', 'Stinger', 'SB1H', 9, 'stinger_en'),
                        weapon('archer blade', 'Archer Blade', 'SB1H', 7, 'archer_en')],
            'Armor': [{'key': 'devil helm', 'name': 'Devil Helm', 'recordType': 'ARMO', 'type': 'helmet',
                       'armorRating': 5, 'value': 1000, 'enchantmentId': 'devil helm_en'},
                      {'key': 'bound_gauntlet_left', 'name': 'Bound Gauntlet', 'recordType': 'ARMO',
                       'type': 'left_gauntlet', 'armorRating': 80, 'value': 0},
                      {'key': 'bound_gauntlet_right', 'name': 'Bound Gauntlet', 'recordType': 'ARMO',
                       'type': 'right_gauntlet', 'armorRating': 80, 'value': 0}],
            'Enchantments': [
                {'key': 'devil tanto_en', 'castType': 'when_used', 'charges': 70, 'cost': 14,
                 'effects': [{'effectId': 4, 'name': 'Fire Shield', 'durationSeconds': 10},
                             {'effectId': 120, 'name': 'Bound Dagger', 'durationSeconds': 60}]},
                {'key': 'stinger_en', 'castType': 'when_strikes', 'charges': 70, 'cost': 14,
                 'effects': [{'effectId': 120, 'name': 'Bound Dagger', 'durationSeconds': 60}]},
                {'key': 'archer_en', 'castType': 'when_used', 'charges': 15, 'cost': 3,
                 'effects': [{'effectId': 125, 'name': 'Bound Longbow', 'durationSeconds': 30}]},
                {'key': 'devil helm_en', 'castType': 'when_used', 'charges': 655, 'cost': 131,
                 'effects': [{'effectId': 131, 'name': 'Bound Gloves', 'durationSeconds': 60}]}],
            'GameSettings': [{'key': k, 'value': v} for k, v in {
                'smagicbounddaggerid': 'Bound_Dagger', 'smagicboundlongbowid': 'bound_longbow',
                'smagicboundleftgauntletid': 'bound_gauntlet_left',
                'smagicboundrightgauntletid': 'bound_gauntlet_right'}.items()]}
        for name, rows in records.items():
            (self.catalogs/'p'/f'{name}.json').write_text(json.dumps({'records': rows}), encoding='utf-8')

    def record(self, record_type, key):
        from evaluate_policy import catalog_record
        return catalog_record(self.catalogs, 'p', record_type, key)

    def summons(self, record_type, key):
        from evaluate_policy import bound_summons
        return bound_summons(self.catalogs, 'p', self.record(record_type, key))

    def pick(self, record_type, key):
        from build_gear_rows import pick
        route = {'acquisition': 'purchase', 'price': 157, 'value': 157, 'cellKey': 'shop',
                 'nearStart': True, 'needsRepair': False, 'condition': None,
                 'holder': {'name': 'Audenian Valius'}, 'theftRequired': False}
        verdict = {'endgame': True, 'evidenceTruncated': False,
                   'summons': self.summons(record_type, key)}
        return pick(self.record(record_type, key), verdict, route, self.catalogs, 'p')

    def test_the_setting_names_the_conjured_item_in_any_case(self):
        [dagger] = self.summons('WEAP', 'devil tanto')
        self.assertEqual((dagger['key'], dagger['name']), ('bound_dagger', 'Bound Dagger'))
        self.assertEqual((dagger['seconds'], dagger['uses']), (60, 5), '70 charge at 14 a cast')
        self.assertEqual(self.summons('WEAP', 'stinger'), [], 'Cast When Strikes is not at will')
        self.assertEqual(self.summons('WEAP', 'bound_dagger'), [], 'no enchantment, no summon')

    def test_bound_gloves_fill_both_hands(self):
        self.assertEqual([s['key'] for s in self.summons('ARMO', 'devil helm')],
                         ['bound_gauntlet_left', 'bound_gauntlet_right'])

    def test_a_summoner_is_endgame_only_when_the_policy_says_so(self):
        from evaluate_policy import is_endgame
        rules = {'armorRating': 50, 'armorValue': 2000, 'anyValue': 10000}
        tanto, summons = self.record('WEAP', 'devil tanto'), self.summons('WEAP', 'devil tanto')
        self.assertFalse(is_endgame(tanto, rules, summons), 'off by default')
        self.assertTrue(is_endgame(tanto, rules | {'boundSummons': True}, summons))
        self.assertFalse(is_endgame(tanto, rules | {'boundSummons': True}, []), '157 gold is not endgame')

    def test_a_weapon_ranks_on_what_it_conjures_in_its_own_skill(self):
        tanto = self.pick('WEAP', 'devil tanto')
        self.assertEqual((tanto['strength'], tanto['baseStrength']), (20, 6))
        self.assertEqual(tanto['summons'], [{'key': 'bound_dagger', 'name': 'Bound Dagger', 'recordType': 'WEAP', 'strength': 20,
                                             'seconds': 60, 'uses': 5, 'sameRow': True}])
        blade = self.pick('WEAP', 'archer blade')
        self.assertEqual(blade['strength'], 7, 'a short blade that conjures a bow is still a 7 damage blade')
        self.assertFalse(blade['summons'][0]['sameRow'])

    def test_a_helm_that_conjures_gloves_is_not_a_better_helm(self):
        helm = self.pick('ARMO', 'devil helm')
        self.assertEqual(helm['strength'], 5)
        self.assertEqual([s['strength'] for s in helm['summons']], [80, 80], 'but the gloves are shown')

    def test_ordinary_picks_carry_no_summon_fields(self):
        dagger = self.pick('WEAP', 'bound_dagger')
        self.assertNotIn('summons', dagger)
        self.assertNotIn('baseStrength', dagger)

    def test_the_shipped_policy_counts_summoners_as_endgame(self):
        policy = load_policy(Path(__file__).parent/'policy/early-game.json')
        self.assertIs(policy['earlyGame']['endgame']['boundSummons'], True)
