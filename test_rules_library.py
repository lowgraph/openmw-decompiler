import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from build_rules_library import MINIMUM_USES, build, fixed_at, observe, rule
from export_items import ExportError

SNAPSHOT = 'snapshot-for-tests'


def effect(ident, name, **extra):
    return {'effectId': ident, 'name': name, 'school': 'destruction', 'baseCost': 1.0,
            'allowSpellmaking': True, 'allowEnchanting': True} | extra


def use(ident, magnitude=(5, 9), duration=10, area=0, kind='self', skill=None, attribute=None):
    return {'effectId': ident, 'range': kind, 'areaFeet': area, 'durationSeconds': duration,
            'magnitude': {'min': magnitude[0], 'max': magnitude[1]},
            'skill': skill, 'attribute': attribute}


def spell(*effects):
    return {'key': 'spell', 'name': 'spell', 'effects': list(effects)}


class RulesFixture(unittest.TestCase):
    """A catalog release is just files, so the fixtures are too."""
    def release(self, profiles, effects=None):
        directory = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: None)
        effects = effects or [effect(1, 'Test Effect')]
        for name, content in profiles.items():
            (directory/name).mkdir(parents=True)
            written = {'MagicEffects': effects, 'Spells': [], 'Enchantments': [], 'Potions': []}
            written.update(content)
            for catalog, records in written.items():
                (directory/name/(catalog+'.json')).write_text(
                    json.dumps({'records': records}), encoding='utf-8')
        (directory/'manifest.json').write_text(json.dumps(
            {'snapshotId': SNAPSHOT, 'profiles': [{'id': n} for n in profiles]}), encoding='utf-8')
        return directory

    def rules(self, profiles, effects=None, publish_to=None):
        source = self.release(profiles, effects)
        output = publish_to or Path(tempfile.mkdtemp())
        with contextlib.redirect_stdout(io.StringIO()):
            written = build(source, output, list(profiles))
        return {path.name.split('-')[0]: json.loads(path.read_text(encoding='utf-8'))
                for path in written}

    def only(self, profiles, effects=None, ident=1):
        published = self.rules(profiles, effects)
        records = next(iter(published.values()))['records']
        return next(r for r in records if r['effectId'] == ident)


class DerivationTests(RulesFixture):
    def test_a_field_fixed_at_its_sentinel_everywhere_is_unused(self):
        row = self.only({'vanilla': {'Spells': [spell(use(1, magnitude=(1, 1), duration=1))
                                                for _ in range(MINIMUM_USES)]}})
        self.assertTrue(row['noMagnitude'])
        self.assertTrue(row['noDuration'])

    def test_a_field_that_varies_is_in_use(self):
        row = self.only({'vanilla': {'Spells': [spell(use(1, magnitude=(1, 1), duration=1)),
                                                spell(use(1, magnitude=(1, 1), duration=5)),
                                                spell(use(1, magnitude=(4, 9), duration=1))]}})
        self.assertFalse(row['noMagnitude'])
        self.assertFalse(row['noDuration'])

    def test_one_counter_example_in_another_profile_refutes_the_flag(self):
        # The Restore Skill case: every vanilla use says no duration, Tamriel Rebuilt
        # content says otherwise, and a single counter-example decides it.
        quiet = [spell(use(1, magnitude=(1, 1), duration=1)) for _ in range(20)]
        row = self.only({'vanilla': {'Spells': quiet},
                         'tr': {'Spells': quiet + [spell(use(1, magnitude=(1, 1), duration=5))]}})
        self.assertFalse(row['noDuration'], 'pooled evidence must outrank a single profile')
        self.assertTrue(row['noMagnitude'], 'the magnitude was never contradicted')

    def test_thin_evidence_reports_unknown_rather_than_a_guess(self):
        row = self.only({'vanilla': {'Spells': [spell(use(1, magnitude=(1, 1), duration=1))]}})
        self.assertIsNone(row['noMagnitude'])
        self.assertIsNone(row['noDuration'])
        self.assertFalse(row['evidence']['sufficient'])
        self.assertEqual(row['evidence']['bestProfileUses'], 1)

    def test_an_effect_the_content_never_uses_is_unknown_and_empty(self):
        row = self.only({'vanilla': {}})
        self.assertIsNone(row['noMagnitude'])
        self.assertEqual(row['rangesObserved'], [])
        self.assertEqual(row['evidence']['uses'], 0)

    def test_skill_and_attribute_targeting_are_observed_directly(self):
        row = self.only({'vanilla': {'Spells': [spell(use(1, skill='destruction'))]}})
        self.assertTrue(row['targetsSkill'])
        self.assertFalse(row['targetsAttribute'])
        row = self.only({'vanilla': {'Spells': [spell(use(1, attribute='strength'))]}})
        self.assertTrue(row['targetsAttribute'])

    def test_observed_ranges_are_collected_but_potions_prove_none(self):
        row = self.only({'vanilla': {'Spells': [spell(use(1, kind='target')), spell(use(1, kind='touch'))],
                                     'Potions': [spell(use(1, kind='self'))]}})
        self.assertEqual(row['rangesObserved'], ['target', 'touch'],
                         'a potion is drunk by its holder, so it proves no range')

    def test_fixed_at_is_exact(self):
        self.assertTrue(fixed_at({1}, 1))
        self.assertFalse(fixed_at({1, 2}, 1))
        self.assertFalse(fixed_at({2}, 1))
        self.assertFalse(fixed_at(set(), 1))

    def test_observe_pools_value_sets_across_profiles(self):
        source = self.release({'vanilla': {'Spells': [spell(use(1, duration=1))]},
                               'tr': {'Spells': [spell(use(1, duration=7))]}})
        pooled = observe(source, ['vanilla', 'tr'])
        self.assertEqual(pooled[1]['durations'], {1, 7})
        self.assertEqual(dict(pooled[1]['uses']), {'vanilla': 1, 'tr': 1})


class PublicationTests(RulesFixture):
    def test_every_effect_becomes_one_keyed_record(self):
        effects = [effect(1, 'One'), effect(2, 'Two'), effect(3, 'Three')]
        published = self.rules({'vanilla': {}}, effects)['vanilla']
        keys = [r['key'] for r in published['records']]
        self.assertEqual(keys, ['1', '2', '3'])
        self.assertEqual(len(set(keys)), 3)

    def test_extracted_fields_survive_untouched(self):
        effects = [effect(1, 'One', school='restoration', baseCost=7.5, allowEnchanting=False)]
        row = self.only({'vanilla': {}}, effects)
        self.assertEqual((row['school'], row['baseCost'], row['allowEnchanting']),
                         ('restoration', 7.5, False))

    def test_the_payload_states_how_it_was_derived_and_pins_the_snapshot(self):
        published = self.rules({'vanilla': {}, 'tr': {}})['vanilla']
        self.assertEqual(published['snapshotId'], SNAPSHOT)
        self.assertEqual(published['derivation']['profilesPooled'], ['tr', 'vanilla'])
        self.assertEqual(published['derivation']['minimumUses'], MINIMUM_USES)
        self.assertIn('not read from the plugin files', published['coverage'])

    def test_the_cost_formula_is_marked_authored(self):
        published = self.rules({'vanilla': {}})['vanilla']
        formula = published['costFormula']
        self.assertEqual(formula['source'], 'authored')
        self.assertEqual(formula['targetRangeMultiplier'], 1.5)
        self.assertEqual(formula['unusedMagnitude'], 1)
        self.assertEqual(formula['unusedDuration'], 0)

    def test_each_profile_is_published_once_and_is_content_addressed(self):
        output = Path(tempfile.mkdtemp())
        published = self.rules({'vanilla': {}, 'tr': {}}, publish_to=output)
        self.assertEqual(sorted(published), ['tr', 'vanilla'])
        self.assertEqual(len(list(output.glob('*.json'))), 2)

    def test_a_missing_catalog_is_an_error_not_an_empty_result(self):
        source = self.release({'vanilla': {}})
        (source/'vanilla/Spells.json').unlink()
        with self.assertRaises(ExportError):
            with contextlib.redirect_stdout(io.StringIO()):
                build(source, Path(tempfile.mkdtemp()), ['vanilla'])


if __name__ == '__main__':
    unittest.main()
