from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from build_best_in_slot_catalog import (STAGES, catalog_digests, check, check_coverage, eligible,
                                        load_builds, load_late_policy, published_digests, rank,
                                        rerun, score, severity, skill_label, stale_from, traits)
from export_items import ExportError

POLICY = {
    'schemaVersion': '1.0.0', 'policyVersion': 'test',
    'tiers': {'essential': 10, 'strong': 6, 'qol': 3, 'low': 1},
    'toggles': {'allowFormidableSources': {'default': False, 'formidableLevel': 30, 'note': ''}},
    'effects': {
        'Restore Health': {'tier': 'essential', 'cap': 5, 'fit': 'all', 'source': 'research'},
        'Fortify Maximum Magicka': {'tier': 'strong', 'cap': 20, 'fit': 'caster', 'source': 'research'},
        'Fortify Attack': {'tier': 'strong', 'cap': 25, 'fit': 'fighter', 'source': 'placed'},
        'Night Eye': {'tier': 'qol', 'cap': 1, 'fit': 'all', 'source': 'research'}},
    'derived': {
        'Fortify Skill': {'cap': 25, 'major': 8, 'minor': 5, 'misc': 1},
        'Fortify Attribute': {'cap': 25, 'favoured': 8, 'perGovernedSkill': 1.5,
                              'floor': 2, 'ceiling': 8, 'luck': 3}},
    'armour': {'major': 8, 'minor': 5, 'misc': 2, 'ratingCap': 80},
    'weapons': {'major': 8, 'minor': 5, 'misc': 1, 'damageCap': 60},
    'archetypes': {'caster': {'skills': ['destruction', 'restoration'], 'atLeast': 2},
                   'fighter': {'skills': ['long_blade'], 'atLeast': 1}},
    'criticalAttributes': {'all': ['endurance'], 'caster': ['willpower'],
                           'fighter': ['strength']},
    'drawbacks': {
        'Drain Magicka': {'rule': 'archetype', 'caster': 'disqualifying', 'other': 'minor'},
        'Drain Attribute': {'rule': 'attribute', 'favoured': 'disqualifying',
                            'critical': 'significant', 'governing': 'significant',
                            'other': 'minor', 'zeroesAt': 100},
        'Drain Skill': {'rule': 'skill', 'major': 'significant', 'minor': 'significant',
                        'misc': 'minor', 'zeroesAt': 100},
        'Blind': {'rule': 'flat', 'severity': 'significant', 'mitigation': 'Resist Magicka'},
        'Sun Damage': {'rule': 'flat', 'severity': 'none'}},
    'picksPerSlot': 3}

REFERENCE = {
    'races': {'nord': [{'key': 'nord', 'name': 'Nord', 'playable': True, 'beast': False}],
              'argonian': [{'key': 'argonian', 'name': 'Argonian', 'playable': True, 'beast': True}],
              'khajiit': [{'key': 'a', 'name': 'Khajiit', 'playable': True},
                          {'key': 'b', 'name': 'Khajiit', 'playable': True}],
              'tsaesci': [{'key': 't', 'name': 'Tsaesci', 'playable': False, 'beast': False}]},
    'skills': {'long blade': 'long_blade', 'destruction': 'destruction',
               'restoration': 'restoration', 'heavy armor': 'heavy_armor', 'sneak': 'sneak'},
    'governs': {'long_blade': 'strength', 'destruction': 'willpower',
                'restoration': 'willpower', 'heavy_armor': 'endurance', 'sneak': 'agility'},
    'allSkills': ['long_blade', 'destruction', 'restoration', 'heavy_armor', 'sneak'],
    'attributes': {'strength': 'strength', 'willpower': 'willpower', 'endurance': 'endurance',
                   'agility': 'agility', 'luck': 'luck'},
    'settings': {}}


def build(name='Test', race='Nord', maj='Long Blade, Destruction, Restoration',
          minor='Heavy Armor', fav='Strength, Endurance', cat='Battlemage'):
    return {'name': name, 'race': race, 'maj': maj, 'min': minor, 'fav': fav,
            'cat': cat, 'set': 'BUILDS'}


def effect(name, magnitude=10, skill=None, attribute=None):
    return {'name': name, 'skill': skill, 'attribute': attribute, 'magnitude': magnitude}


def item(key='i', slot='amulet', effects=(), source=None, beast=True, **extra):
    return {'key': key, 'name': key, 'slot': slot, 'effects': list(effects),
            'beastWearable': beast,
            'source': source or {'kind': 'placed', 'routes': 1, 'easiestLevel': 5,
                                 'questGrants': []},
            **extra}


class PolicyTests(unittest.TestCase):
    def write(self, payload):
        path = Path(tempfile.mkdtemp())/'late-game.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_an_unreadable_schema_is_refused(self):
        with self.assertRaises(ExportError):
            load_late_policy(self.write(POLICY | {'schemaVersion': '9.9.9'}))

    def test_an_effect_naming_an_unknown_tier_is_refused(self):
        broken = json.loads(json.dumps(POLICY))
        broken['effects']['Restore Health']['tier'] = 'legendary'
        with self.assertRaises(ExportError) as caught:
            load_late_policy(self.write(broken))
        self.assertIn('legendary', str(caught.exception))

    def test_an_effect_cannot_be_both_benefit_and_drawback(self):
        broken = json.loads(json.dumps(POLICY))
        broken['drawbacks']['Night Eye'] = {'rule': 'flat', 'severity': 'minor'}
        with self.assertRaises(ExportError) as caught:
            load_late_policy(self.write(broken))
        self.assertIn('Night Eye', str(caught.exception))

    def test_an_unknown_severity_is_refused(self):
        broken = json.loads(json.dumps(POLICY))
        broken['drawbacks']['Blind']['severity'] = 'annoying'
        with self.assertRaises(ExportError) as caught:
            load_late_policy(self.write(broken))
        self.assertIn('annoying', str(caught.exception))

    def test_the_shipped_policy_loads(self):
        loaded = load_late_policy(Path(__file__).parent/'policy/late-game.json')
        self.assertEqual(loaded['toggles']['allowFormidableSources']['formidableLevel'], 30)
        self.assertFalse(loaded['toggles']['allowFormidableSources']['default'])


class CoverageTests(unittest.TestCase):
    def test_an_effect_on_a_candidate_that_the_policy_misses_is_refused(self):
        with self.assertRaises(ExportError) as caught:
            check_coverage(POLICY, {'tr': {'Restore Health', 'Absorb Fatigue'}})
        self.assertIn('Absorb Fatigue', str(caught.exception))

    def test_an_effect_the_policy_names_that_exists_nowhere_is_refused(self):
        with self.assertRaises(ExportError) as caught:
            check_coverage(POLICY, {'tr': {'Restore Health'}})
        self.assertIn('Night Eye', str(caught.exception))

    def test_appearing_in_one_profile_is_enough(self):
        # Most of these effects exist only on Tamriel Rebuilt items; demanding every
        # profile would fail an entry that is doing its job.
        everything = set(POLICY['effects']) | set(POLICY['derived']) | set(POLICY['drawbacks'])
        check_coverage(POLICY, {'vanilla': {'Restore Health'}, 'tr': everything})


class TraitTests(unittest.TestCase):
    def test_skills_are_tiered_by_where_the_build_puts_them(self):
        found, _ = traits(build(), REFERENCE, POLICY)
        self.assertEqual(found['skillTier']['long_blade'], 'major')
        self.assertEqual(found['skillTier']['heavy_armor'], 'minor')
        self.assertEqual(found['skillTier']['sneak'], 'misc')

    def test_a_favoured_attribute_outweighs_a_governing_one(self):
        found, _ = traits(build(), REFERENCE, POLICY)
        self.assertEqual(found['attributeWeight']['strength'], 8)
        # willpower governs two of the build's classed skills: 2 + 1.5*2
        self.assertEqual(found['attributeWeight']['willpower'], 5)

    def test_luck_governs_nothing_and_gets_a_flat_weight(self):
        found, _ = traits(build(), REFERENCE, POLICY)
        self.assertEqual(found['attributeWeight']['luck'], 3)

    def test_two_casting_schools_make_a_caster(self):
        found, _ = traits(build(), REFERENCE, POLICY)
        self.assertTrue(found['caster'])
        self.assertTrue(found['fighter'])

    def test_one_casting_school_does_not(self):
        found, _ = traits(build(maj='Long Blade, Destruction, Heavy Armor', minor='Sneak'),
                          REFERENCE, POLICY)
        self.assertFalse(found['caster'])

    def test_a_beast_race_is_carried_through(self):
        found, _ = traits(build(race='Argonian'), REFERENCE, POLICY)
        self.assertTrue(found['beast'])

    def test_a_race_the_profile_lacks_skips_the_build(self):
        found, reason = traits(build(race='Ayleid'), REFERENCE, POLICY)
        self.assertIsNone(found)
        self.assertIn('0 records', reason)

    def test_an_unplayable_race_skips_the_build(self):
        # This is how ARCE builds stay out of the profiles without ARCE.
        found, reason = traits(build(race='Tsaesci'), REFERENCE, POLICY)
        self.assertIsNone(found)
        self.assertIn('not playable', reason)

    def test_an_ambiguous_race_label_skips_rather_than_guessing(self):
        found, reason = traits(build(race='Khajiit'), REFERENCE, POLICY)
        self.assertIsNone(found)
        self.assertIn('2 records', reason)

    def test_an_unknown_skill_fails_loudly(self):
        with self.assertRaises(ExportError):
            traits(build(maj='Spellcraft'), REFERENCE, POLICY)


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.battlemage, _ = traits(build(), REFERENCE, POLICY)
        self.melee, _ = traits(build(maj='Long Blade, Heavy Armor', minor='Sneak',
                                     cat='Pure melee'), REFERENCE, POLICY)

    def test_a_full_cap_effect_scores_its_whole_tier(self):
        value, parts, _ = score(item(effects=[effect('Restore Health', 5)]),
                                self.battlemage, POLICY)
        self.assertEqual(value, 10)
        self.assertEqual(parts[0][0], 'Restore Health 5')

    def test_magnitude_saturates_rather_than_growing_without_limit(self):
        value, _, _ = score(item(effects=[effect('Restore Health', 500)]),
                            self.battlemage, POLICY)
        self.assertEqual(value, 10)

    def test_a_caster_effect_counts_for_a_caster_only(self):
        piece = item(effects=[effect('Fortify Maximum Magicka', 20)])
        self.assertEqual(score(piece, self.battlemage, POLICY)[0], 6)
        self.assertEqual(score(piece, self.melee, POLICY)[0], 0)

    def test_fortify_skill_is_weighted_by_the_builds_own_skills(self):
        major = score(item(effects=[effect('Fortify Skill', 25, skill='long_blade')]),
                      self.battlemage, POLICY)[0]
        misc = score(item(effects=[effect('Fortify Skill', 25, skill='sneak')]),
                     self.battlemage, POLICY)[0]
        self.assertEqual((major, misc), (8, 1))

    def test_armour_rating_is_weighted_by_the_builds_armour_skill(self):
        piece = item(slot='cuirass', armorRating=80, armorClass='heavy')
        self.assertEqual(score(piece, self.battlemage, POLICY)[0], 5)   # heavy armor minor
        self.assertEqual(score(piece, self.melee, POLICY)[0], 8)        # heavy armor major

    def test_a_weapon_is_weighted_by_the_builds_weapon_skill(self):
        piece = item(slot='weapon', weaponSkill='long_blade', damage=60)
        self.assertEqual(score(piece, self.battlemage, POLICY)[0], 8)

    def test_reasons_come_back_largest_first(self):
        _, parts, _ = score(item(effects=[effect('Night Eye', 1),
                                          effect('Restore Health', 5)]),
                            self.battlemage, POLICY)
        self.assertEqual([label for label, _ in parts], ['Restore Health 5', 'Night Eye 1'])


class DrawbackTests(unittest.TestCase):
    """Drawbacks are never subtracted. They disqualify, warn, or are noted."""
    def setUp(self):
        self.battlemage, _ = traits(build(), REFERENCE, POLICY)
        self.melee, _ = traits(build(maj='Long Blade, Heavy Armor', minor='Sneak',
                                     cat='Pure melee'), REFERENCE, POLICY)

    def test_the_darksun_shield_case(self):
        # Drain Magicka 100 alongside a strong benefit: ruinous for a caster, merely
        # untidy for a fighter. The same item, two answers.
        shield = item('darksun', slot='shield',
                      effects=[effect('Drain Magicka', 100), effect('Restore Health', 5)])
        self.assertIsNone(score(shield, self.battlemage, POLICY))
        self.assertEqual(score(shield, self.melee, POLICY)[0], 5 * 2)

    def test_a_significant_drawback_warns_without_reducing_the_score(self):
        boots = item('boots', slot='boots',
                     effects=[effect('Blind', 100), effect('Restore Health', 5)])
        value, _, warnings = score(boots, self.melee, POLICY)
        self.assertEqual(value, 10, 'the benefit is not netted down')
        self.assertEqual(warnings, ['Blind 100 (cancelled by Resist Magicka)'])

    def test_a_drawback_rated_none_does_not_even_warn(self):
        _, _, warnings = score(item(effects=[effect('Sun Damage', 20)]), self.melee, POLICY)
        self.assertEqual(warnings, [])

    def test_draining_a_favoured_attribute_disqualifies(self):
        piece = item(effects=[effect('Drain Attribute', 50, attribute='strength')])
        self.assertIsNone(score(piece, self.battlemage, POLICY))

    def test_draining_a_governing_attribute_only_warns(self):
        piece = item(effects=[effect('Drain Attribute', 50, attribute='willpower'),
                              effect('Restore Health', 5)])
        value, _, warnings = score(piece, self.battlemage, POLICY)
        self.assertEqual(value, 10)
        self.assertTrue(warnings)

    def test_draining_an_unrelated_attribute_is_only_noted(self):
        piece = item(effects=[effect('Drain Attribute', 50, attribute='agility'),
                              effect('Restore Health', 5)])
        self.assertEqual(score(piece, self.battlemage, POLICY)[2], [])

    def test_severity_follows_the_named_rule(self):
        self.assertEqual(severity(effect('Drain Skill', skill='long_blade'),
                                  POLICY['drawbacks']['Drain Skill'], self.battlemage),
                         'significant')
        self.assertEqual(severity(effect('Drain Skill', skill='sneak'),
                                  POLICY['drawbacks']['Drain Skill'], self.battlemage),
                         'minor')


class MagnitudeTests(unittest.TestCase):
    """A drain of 5 and a drain of 255 are not the same drawback.

    Neb-Crescen drains Willpower and Intelligence by 255, which ends a caster. The
    Mantle of Woe drains Personality by 100, which a caster survives -- even though
    Personality governs the Illusion that both Conjurer builds carry. So magnitude
    escalates only on what the archetype actually runs on.
    """
    def setUp(self):
        self.caster, _ = traits(build(), REFERENCE, POLICY)

    def test_zeroing_a_critical_attribute_disqualifies(self):
        weapon = item('neb-crescen', slot='weapon',
                      effects=[effect('Drain Attribute', 255, attribute='willpower'),
                               effect('Restore Health', 5)])
        self.assertIsNone(score(weapon, self.caster, POLICY))

    def test_a_small_drain_on_the_same_attribute_only_warns(self):
        weapon = item('lesser', slot='weapon',
                      effects=[effect('Drain Attribute', 10, attribute='willpower'),
                               effect('Restore Health', 5)])
        value, _, warnings = score(weapon, self.caster, POLICY)
        self.assertEqual(value, 10)
        self.assertTrue(warnings)

    def test_zeroing_an_attribute_the_archetype_does_not_use_survives(self):
        # The Mantle of Woe case: Personality governs a classed skill but casting
        # does not depend on it.
        robe = item('mantle', slot='robe',
                    effects=[effect('Drain Attribute', 100, attribute='agility'),
                             effect('Restore Health', 5)])
        value, _, warnings = score(robe, self.caster, POLICY)
        self.assertEqual(value, 10)
        self.assertEqual(warnings, [])

    def test_zeroing_a_classed_skill_disqualifies(self):
        piece = item(effects=[effect('Drain Skill', 100, skill='long_blade')])
        self.assertIsNone(score(piece, self.caster, POLICY))

    def test_critical_attributes_follow_the_archetype(self):
        melee, _ = traits(build(maj='Long Blade, Heavy Armor', minor='Sneak'), REFERENCE, POLICY)
        self.assertIn('strength', melee['critical'])
        self.assertNotIn('willpower', melee['critical'])
        self.assertIn('willpower', self.caster['critical'])
        self.assertIn('endurance', melee['critical'], 'everyone runs on endurance')


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.normal, _ = traits(build(), REFERENCE, POLICY)
        self.beast, _ = traits(build(race='Argonian'), REFERENCE, POLICY)

    def test_an_unconfirmed_item_is_never_offered(self):
        piece = item(source={'kind': 'unconfirmed', 'routes': 0, 'easiestLevel': None,
                             'questGrants': []})
        self.assertFalse(eligible(piece, self.normal, True, 30))

    def test_a_beast_race_never_sees_what_it_cannot_equip(self):
        piece = item(slot='helmet', beast=False)
        self.assertTrue(eligible(piece, self.normal, False, 30))
        self.assertFalse(eligible(piece, self.beast, False, 30))

    def test_a_formidable_source_is_hidden_until_the_toggle_allows_it(self):
        # The Royal Signet Ring: only route is robbing a level 35 king.
        ring = item(slot='ring', source={'kind': 'placed', 'routes': 1, 'easiestLevel': 35,
                                         'questGrants': []})
        self.assertFalse(eligible(ring, self.normal, False, 30))
        self.assertTrue(eligible(ring, self.normal, True, 30))

    def test_a_quest_grant_beats_a_formidable_holder(self):
        # Questing is always assumed, so a scripted grant is a way in regardless.
        piece = item(source={'kind': 'placed', 'routes': 1, 'easiestLevel': 52,
                             'questGrants': ['somequest']})
        self.assertTrue(eligible(piece, self.normal, False, 30))


class RankTests(unittest.TestCase):
    def setUp(self):
        self.build, _ = traits(build(), REFERENCE, POLICY)

    def test_picks_are_best_first_and_capped(self):
        items = [item(f'i{n}', effects=[effect('Restore Health', n)]) for n in (1, 2, 3, 4, 5)]
        picks = rank(items, self.build, POLICY, True)['amulet']
        self.assertEqual([p['item'] for p in picks], ['i5', 'i4', 'i3'])

    def test_only_the_first_pick_carries_its_reasons(self):
        items = [item(f'i{n}', effects=[effect('Restore Health', n)]) for n in (1, 2)]
        picks = rank(items, self.build, POLICY, True)['amulet']
        self.assertIn('reasons', picks[0])
        self.assertNotIn('reasons', picks[1])

    def test_an_easier_source_breaks_a_tie(self):
        hard = item('hard', source={'kind': 'placed', 'routes': 1, 'easiestLevel': 25,
                                    'questGrants': []}, effects=[effect('Restore Health', 5)])
        easy = item('easy', source={'kind': 'placed', 'routes': 1, 'easiestLevel': 2,
                                    'questGrants': []}, effects=[effect('Restore Health', 5)])
        picks = rank([hard, easy], self.build, POLICY, True)['amulet']
        self.assertEqual(picks[0]['item'], 'easy')

    def test_a_slot_with_nothing_worth_wearing_is_absent(self):
        # A Battlemage really does get no shield: the only candidate drains magicka.
        shield = item('darksun', slot='shield', effects=[effect('Drain Magicka', 100)])
        self.assertNotIn('shield', rank([shield], self.build, POLICY, True))

    def test_an_item_scoring_nothing_is_not_offered(self):
        self.assertEqual(rank([item(effects=[effect('Fortify Maximum Magicka', 20)])],
                              self.build, POLICY, True).get('amulet', [])[0]['score'], 6)
        melee, _ = traits(build(maj='Long Blade, Heavy Armor', minor='Sneak'), REFERENCE, POLICY)
        self.assertEqual(rank([item(effects=[effect('Fortify Maximum Magicka', 20)])],
                              melee, POLICY, True), {})


class BuildSourceTests(unittest.TestCase):
    def test_duplicate_build_names_are_refused_because_they_are_the_keys(self):
        path = Path(tempfile.mkdtemp())/'builds.json'
        path.write_text(json.dumps({'BUILDS': [build('Same'), build('Same')]}), encoding='utf-8')
        with self.assertRaises(ExportError) as caught:
            load_builds(None, path)
        self.assertIn('unique', str(caught.exception))

    def test_a_digest_travels_with_the_builds(self):
        path = Path(tempfile.mkdtemp())/'builds.json'
        path.write_text(json.dumps({'BUILDS': [build('One')]}), encoding='utf-8')
        builds, source, digest = load_builds(None, path)
        self.assertEqual(len(builds), 1)
        self.assertEqual(len(digest), 64)
        self.assertIn('builds.json', source)

    @unittest.skipUnless(shutil.which('node'), 'node reads the site builds')
    def test_the_site_module_and_a_json_file_agree_on_the_same_builds(self):
        # Build names are the catalog keys, and 62 of the site's carry an em dash. Node
        # writes UTF-8; reading it back in the Windows code page turned "—" into "â€”",
        # so the site's lookups by name missed every one of them.
        name = 'High Elf male \u2014 Atronach mage'
        sets = {'BUILDS': [build(name)]}
        site = Path(tempfile.mkdtemp())
        (site/'lib').mkdir()
        (site/'lib/premade-data.mjs').write_text(
            ''.join(f'export const {key} = {json.dumps(value, ensure_ascii=False)};\n'
                    for key, value in sets.items()), encoding='utf-8')
        (site/'builds.json').write_text(json.dumps(sets, ensure_ascii=False), encoding='utf-8')
        from_node, _, node_digest = load_builds(site)
        _, _, file_digest = load_builds(None, site/'builds.json')
        self.assertEqual(from_node[0]['name'], name)
        self.assertEqual(node_digest, file_digest)


CURRENT = {'vanilla': 'new', 'tr': 'new', 'tr_arce': 'new'}


def publish_bundle(digests, inherit=()):
    """A published bundle with one BestInSlot file per profile. A profile in `inherit`
    carries none and names tr as its base, the way tr_arce can."""
    root = Path(tempfile.mkdtemp())
    profiles = []
    for profile, digest in digests.items():
        entry = {'id': profile, 'base': 'tr' if profile in inherit else None, 'files': {}}
        if profile not in inherit:
            (root/'b1'/profile).mkdir(parents=True)
            (root/'b1'/profile/'BestInSlot.json').write_text(
                json.dumps({'builds': {'digest': digest}}), encoding='utf-8')
            entry['files']['BestInSlot'] = {'path': f'{profile}/BestInSlot.json'}
        profiles.append(entry)
    (root/'b1').mkdir(exist_ok=True)
    (root/'b1/manifest.json').write_text(json.dumps({'profiles': profiles}), encoding='utf-8')
    (root/'current.json').write_text(
        json.dumps({'bundleId': 'b1', 'manifest': 'b1/manifest.json'}), encoding='utf-8')
    return root


class FreshnessTests(unittest.TestCase):
    def test_nothing_to_rerun_when_every_stage_carries_the_current_builds(self):
        self.assertIsNone(stale_from('new', {stage: CURRENT for stage in STAGES}))

    def test_the_first_stale_stage_decides_what_to_rerun(self):
        old = dict(CURRENT, tr='old')
        self.assertEqual(stale_from('new', {'catalog': old, 'bundle': old, 'site': old}), 'catalog')
        self.assertEqual(stale_from('new', {'catalog': CURRENT, 'bundle': old, 'site': old}),
                         'bundle')
        self.assertEqual(stale_from('new', {'catalog': CURRENT, 'bundle': CURRENT, 'site': old}),
                         'site')

    def test_nothing_published_or_no_digest_is_stale_rather_than_current(self):
        self.assertEqual(stale_from('new', {'catalog': CURRENT, 'bundle': CURRENT, 'site': None}),
                         'site')
        self.assertEqual(stale_from('new', {'catalog': dict(CURRENT, vanilla=None),
                                            'bundle': CURRENT, 'site': CURRENT}), 'catalog')
        self.assertEqual(stale_from('new', {'catalog': {}, 'bundle': CURRENT, 'site': CURRENT}),
                         'catalog')

    def test_rerun_starts_at_the_stale_stage(self):
        self.assertEqual(len(rerun('catalog', 'A:/site')), 3)
        self.assertEqual(rerun('bundle', 'A:/site')[0], 'python build_app_bundle.py')
        only = rerun('site', 'A:/site')
        self.assertEqual(len(only), 1)
        self.assertIn('stage-game-data.mjs', only[0])

    def test_an_inheriting_profile_reports_its_bases_digest(self):
        root = publish_bundle({'vanilla': 'v', 'tr': 't', 'tr_arce': None}, inherit={'tr_arce'})
        self.assertEqual(published_digests(root), {'vanilla': 'v', 'tr': 't', 'tr_arce': 't'})

    def test_a_base_that_names_itself_ends_instead_of_looping(self):
        self.assertEqual(published_digests(publish_bundle({'tr': None}, inherit={'tr'})),
                         {'tr': None})

    def test_no_pointer_is_nothing_published_and_a_broken_pointer_is_refused(self):
        empty = Path(tempfile.mkdtemp())
        self.assertIsNone(published_digests(empty))
        (empty/'current.json').write_text('{"bundleId": "x"}', encoding='utf-8')
        with self.assertRaises(ExportError):
            published_digests(empty)

    def test_a_bundle_built_without_best_in_slot_has_no_digest(self):
        root = publish_bundle({'vanilla': 'v'})
        manifest = root/'b1/manifest.json'
        data = json.loads(manifest.read_text(encoding='utf-8'))
        data['profiles'][0]['files'] = {}
        manifest.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(published_digests(root), {'vanilla': None})

    def test_the_catalog_stage_reads_the_file_bundling_would_take(self):
        directory = Path(tempfile.mkdtemp())
        for name, digest, when in (('tr-old.json', 'old', 1000), ('tr-new.json', 'new', 2000),
                                   ('tr_arce-x.json', 'arce', 3000)):
            (directory/name).write_text(json.dumps({'builds': {'digest': digest}}),
                                        encoding='utf-8')
            os.utime(directory/name, (when, when))
        # The newest tr file, not the newest file: tr_arce's are not tr's.
        self.assertEqual(catalog_digests(directory, ['tr', 'vanilla']),
                         {'tr': 'new', 'vanilla': None})

    def test_the_report_names_only_the_commands_still_needed(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = check('new', 'builds.json', {'catalog': CURRENT,
                                                'bundle': dict(CURRENT, tr='old'),
                                                'site': None}, 'A:/site')
        self.assertEqual(code, 1)
        self.assertIn('Stale from the bundle onward', out.getvalue())
        self.assertIn('python build_app_bundle.py', out.getvalue())
        self.assertNotIn('python build_best_in_slot_catalog.py', out.getvalue())
        self.assertRegex(out.getvalue(), r'site\s+nothing published')
        with redirect_stdout(io.StringIO()):
            self.assertEqual(check('new', 'b', {stage: CURRENT for stage in STAGES}, 'A:/s'), 0)


class LabelTests(unittest.TestCase):
    def test_skill_labels_match_the_sites_own(self):
        self.assertEqual(skill_label('long_blade'), 'Long Blade')
        self.assertEqual(skill_label('hand_to_hand'), 'Hand-to-hand')


if __name__ == '__main__':
    unittest.main()
