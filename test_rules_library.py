from collections import Counter
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from build_rules_library import (MINIMUM_USES, agreement, build, check_alignment, fixed_at,
                                 flags_for, load_flags, observe, rule)
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

    def flags(self, *records):
        """An effect-flags.json as import_effect_flags.py writes it."""
        # Name defaults to the fixture effect's, so records line up unless a test
        # deliberately shifts them.
        base = {'name': 'Test Effect', 'school': 'destruction', 'baseCost': 1.0,
                'harmful': False, 'continuousVfx': False, 'hasDuration': True,
                'hasMagnitude': True, 'isAppliedOnce': False, 'casterLinked': False,
                'nonRecastable': False, 'hasAttribute': False, 'hasSkill': False,
                'onSelf': True, 'onTouch': True, 'onTarget': True, 'unreflectable': False,
                'allowsSpellmaking': True, 'allowsEnchanting': True, 'negativeLight': False}
        written = [base | {'id': str(r.get('index', 0))} | r for r in records]
        # The importer reports repeated names; a fixture that did not would hide the
        # very case the name join has to handle.
        counted = Counter(r['name'] for r in written)
        path = Path(tempfile.mkdtemp())/'effect-flags.json'
        path.write_text(json.dumps(
            {'schemaVersion': '1.0.0', 'effects': len(written),
             'source': {'tool': 'test', 'snapshotId': SNAPSHOT},
             'ambiguousNames': sorted(n for n, c in counted.items() if c > 1),
             'records': written}), encoding='utf-8')
        return path

    def merged(self, profiles, flags, effects=None, ident=1):
        source = self.release(profiles, effects)
        with contextlib.redirect_stdout(io.StringIO()):
            written = build(source, Path(tempfile.mkdtemp()), list(profiles), flags)
        payload = json.loads(written[0].read_text(encoding='utf-8'))
        return payload, next(r for r in payload['records'] if r['effectId'] == ident)


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


class EngineFlagTests(RulesFixture):
    """When the engine's own table is available it outranks the inference."""

    def test_engine_facts_replace_the_inference_and_add_what_it_could_not_reach(self):
        quiet = [spell(use(1, magnitude=(1, 1), duration=1)) for _ in range(5)]
        flags = self.flags({'index': 1, 'harmful': True, 'hasMagnitude': False,
                            'hasDuration': False, 'onTouch': False, 'onTarget': False})
        payload, row = self.merged({'vanilla': {'Spells': quiet}}, flags)
        self.assertEqual(row['source'], 'engine')
        self.assertTrue(row['noMagnitude'])
        self.assertTrue(row['noDuration'])
        self.assertTrue(row['harmful'], 'harmful is not inferable from content at all')
        self.assertEqual((row['castSelf'], row['castTouch'], row['castTarget']),
                         (True, False, False))
        self.assertEqual(payload['verification']['source'], 'engine')

    def test_a_confirmed_inference_is_labelled_as_such(self):
        quiet = [spell(use(1, magnitude=(1, 1), duration=1)) for _ in range(5)]
        flags = self.flags({'index': 1, 'hasMagnitude': False, 'hasDuration': False})
        payload, row = self.merged({'vanilla': {'Spells': quiet}}, flags)
        self.assertEqual(row['agreement']['noMagnitude'], 'confirmed')
        self.assertEqual(row['agreement']['noDuration'], 'confirmed')
        self.assertEqual(payload['verification']['confirmed'], 4)
        self.assertEqual(payload['verification']['corrected'], 0)

    def test_a_wrong_inference_is_corrected_and_counted(self):
        # The Restore Skill shape: content says no duration, the engine says otherwise.
        quiet = [spell(use(1, magnitude=(4, 9), duration=1)) for _ in range(5)]
        flags = self.flags({'index': 1, 'hasDuration': True})
        payload, row = self.merged({'vanilla': {'Spells': quiet}}, flags)
        self.assertFalse(row['noDuration'])
        self.assertEqual(row['agreement']['noDuration'], 'corrected')
        self.assertEqual(row['inferred']['noDuration'], True, 'the inference is kept on record')
        self.assertEqual(payload['verification']['corrected'], 1)

    def test_what_the_content_could_not_decide_is_marked_decided(self):
        flags = self.flags({'index': 1, 'hasMagnitude': False})
        payload, row = self.merged({'vanilla': {}}, flags)
        self.assertTrue(row['noMagnitude'])
        self.assertEqual(row['agreement']['noMagnitude'], 'decided')
        self.assertEqual(payload['verification']['decided'], 2)

    def test_a_range_the_engine_forbids_but_content_uses_is_surfaced(self):
        used = [spell(use(1, kind='target')) for _ in range(3)]
        flags = self.flags({'index': 1, 'onTarget': False})
        payload, row = self.merged({'vanilla': {'Spells': used}}, flags)
        self.assertEqual(row['rangesUnexplained'], ['target'])
        self.assertEqual(payload['verification']['rangesUnexplained'], [row['name']])

    def test_a_dump_missing_a_catalog_effect_is_refused(self):
        flags = self.flags({'index': 999, 'name': 'Something Else'})
        with self.assertRaises(ExportError):
            self.merged({'vanilla': {'Spells': [spell(use(1))]*3}}, flags)

    def test_without_a_dump_nothing_claims_engine_provenance(self):
        payload, row = self.merged({'vanilla': {'Spells': [spell(use(1))]*3}}, None)
        self.assertEqual(row['source'], 'derived')
        self.assertIsNone(row['harmful'])
        self.assertEqual(payload['verification']['source'], 'content only')

    def test_an_unreadable_flag_schema_is_refused(self):
        path = Path(tempfile.mkdtemp())/'effect-flags.json'
        path.write_text(json.dumps({'schemaVersion': '9.9.9', 'records': []}), encoding='utf-8')
        with self.assertRaises(ExportError):
            load_flags(path)

    def test_a_shifted_dump_is_refused_before_it_rewrites_anything(self):
        # The off-by-one that positional keying produced: every index names a
        # different effect, and merging it would silently corrupt all 141 rules.
        effects = [effect(1, 'One'), effect(2, 'Two')]
        flags = self.flags({'index': 1, 'name': 'Two'}, {'index': 2, 'name': 'Three'})
        with self.assertRaises(ExportError) as caught:
            self.merged({'vanilla': {}}, flags, effects)
        self.assertIn('does not cover the catalogs', str(caught.exception))
        self.assertIn('One', str(caught.exception))

    def test_an_aligned_dump_passes_the_check(self):
        effects = [effect(1, 'One'), effect(2, 'Two')]
        flags = self.flags({'index': 1, 'name': 'One'}, {'index': 2, 'name': 'Two'})
        payload, _ = self.merged({'vanilla': {}}, flags, effects)
        self.assertEqual(payload['verification']['effectsFromEngine'], 2)

    def test_check_alignment_requires_every_catalog_effect(self):
        self.assertEqual(check_alignment([effect(1, 'One')], {'One': {'name': 'One'}}), 1)
        with self.assertRaises(ExportError):
            check_alignment([effect(1, 'One'), effect(2, 'Two')], {'One': {'name': 'One'}})

    def test_an_effect_only_the_engine_knows_is_published_as_a_rule(self):
        # Tamriel Rebuilt registers 45 effects through Lua. No plugin file defines them,
        # so they reach the catalogs through the dump or not at all.
        flags = self.flags({'id': 't_summon_devourer', 'name': 'Summon Devourer',
                            'school': 'conjuration', 'baseCost': 40.0, 'hasMagnitude': False},
                           {'id': 'one', 'name': 'One'})
        payload, _ = self.merged({'vanilla': {}}, flags, [effect(1, 'One')])
        self.assertEqual(payload['derivation']['engineOnly'], 1)
        added = next(r for r in payload['records'] if r['name'] == 'Summon Devourer')
        self.assertEqual(added['key'], 't_summon_devourer')
        self.assertIsNone(added['effectId'], 'nothing extracted can reference it')
        self.assertFalse(added['extracted'])
        self.assertEqual(added['school'], 'conjuration')
        self.assertEqual(added['baseCost'], 40.0)
        self.assertTrue(added['noMagnitude'], 'the engine decides it, with no content to infer from')
        self.assertEqual(added['evidence']['uses'], 0)

    def test_extracted_effects_are_marked_as_such(self):
        flags = self.flags({'id': 'one', 'name': 'One'})
        payload, row = self.merged({'vanilla': {}}, flags, [effect(1, 'One')])
        self.assertTrue(row['extracted'])
        self.assertEqual(payload['derivation']['engineOnly'], 0)

    def test_an_engine_effect_with_a_repeated_name_still_reaches_the_output(self):
        # Tamriel Rebuilt ships two Wabbajack effects with distinct ids. Neither can be
        # joined by name, but neither is being joined: nothing extracted shares the name.
        flags = self.flags({'id': 't_alteration_wabbajack', 'name': 'Wabbajack'},
                           {'id': 't_alteration_wabbajackhelper', 'name': 'Wabbajack'},
                           {'id': 'one', 'name': 'One'})
        payload, _ = self.merged({'vanilla': {}}, flags, [effect(1, 'One')])
        self.assertEqual(payload['derivation']['engineOnly'], 2)
        self.assertEqual(sorted(r['key'] for r in payload['records'] if not r['extracted']),
                         ['t_alteration_wabbajack', 't_alteration_wabbajackhelper'])

    def test_a_catalog_effect_whose_name_the_dump_repeats_is_refused_not_guessed(self):
        flags = self.flags({'id': 'a', 'name': 'One'}, {'id': 'b', 'name': 'One'})
        with self.assertRaises(ExportError) as caught:
            self.merged({'vanilla': {}}, flags, [effect(1, 'One')])
        self.assertIn('does not cover the catalogs', str(caught.exception))

    def test_an_engine_effect_keeps_its_own_key_so_the_bundle_can_index_it(self):
        flags = self.flags({'id': 'one', 'name': 'One'}, {'id': 'two', 'name': 'Two'})
        payload, _ = self.merged({'vanilla': {}}, flags, [effect(1, 'One')])
        keys = [r['key'] for r in payload['records']]
        self.assertEqual(len(keys), len(set(keys)), 'the bundle refuses duplicate keys')


class ProfileFlagTests(RulesFixture):
    def test_a_profile_with_its_own_dump_uses_it(self):
        directory = Path(tempfile.mkdtemp())
        (directory/'tr.json').write_text('{}', encoding='utf-8')
        self.assertEqual(flags_for(directory, 'tr', Path('shared.json')), directory/'tr.json')

    def test_a_profile_without_one_falls_back_to_the_shared_dump(self):
        directory = Path(tempfile.mkdtemp())
        self.assertEqual(flags_for(directory, 'tr', Path('shared.json')), Path('shared.json'))

    def test_no_directory_at_all_falls_back(self):
        self.assertEqual(flags_for(None, 'tr', Path('shared.json')), Path('shared.json'))

    def test_each_profile_reads_its_own_flags(self):
        # Vanilla knows 1 effect, Tamriel Rebuilt knows that one and a Lua-registered
        # second. A single shared dump would force one answer onto both.
        directory = Path(tempfile.mkdtemp())
        for name, records in (('vanilla', [{'id': 'one', 'name': 'One'}]),
                              ('tr', [{'id': 'one', 'name': 'One'},
                                      {'id': 'two', 'name': 'Summon Devourer'}])):
            (directory/f'{name}.json').write_bytes(
                self.flags(*records).read_bytes())
        source = self.release({'vanilla': {}, 'tr': {}}, [effect(1, 'One')])
        with contextlib.redirect_stdout(io.StringIO()):
            written = build(source, Path(tempfile.mkdtemp()), ['vanilla', 'tr'],
                            None, directory)
        counts = {}
        for path in written:
            payload = json.loads(path.read_text(encoding='utf-8'))
            counts[payload['profile']] = payload['derivation']['engineOnly']
        self.assertEqual(counts, {'vanilla': 0, 'tr': 1})

    def test_a_dump_from_an_older_extraction_is_refused_though_its_effects_match(self):
        # The hole check_alignment leaves: every name lines up, so only the recorded
        # extraction can tell these flags are stale.
        flags = self.flags({'index': 1})
        payload = json.loads(flags.read_text(encoding='utf-8'))
        payload['source']['snapshotId'] = 'an-older-extraction'
        flags.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaises(ExportError) as caught:
            self.merged({'vanilla': {'Spells': [spell(use(1))]*3}}, flags)
        self.assertIn('an-older-ext', str(caught.exception))
        self.assertIn('dump_profiles.py', str(caught.exception))

    def test_a_dump_recording_no_extraction_is_refused(self):
        flags = self.flags({'index': 1})
        payload = json.loads(flags.read_text(encoding='utf-8'))
        del payload['source']['snapshotId']
        flags.write_text(json.dumps(payload), encoding='utf-8')
        with self.assertRaisesRegex(ExportError, 'no recorded extraction'):
            self.merged({'vanilla': {'Spells': [spell(use(1))]*3}}, flags)

    def test_asking_for_flags_and_finding_none_is_refused_not_downgraded(self):
        # A skipped dump used to become "content only" without a word.
        source = self.release({'vanilla': {}}, [effect(1, 'One')])
        with self.assertRaisesRegex(ExportError, 'No effect dump for vanilla'):
            with contextlib.redirect_stdout(io.StringIO()):
                build(source, Path(tempfile.mkdtemp()), ['vanilla'], None,
                      Path(tempfile.mkdtemp()))

    def test_agreement_labels(self):
        self.assertEqual(agreement(None, True), 'decided')
        self.assertEqual(agreement(True, True), 'confirmed')
        self.assertEqual(agreement(False, True), 'corrected')


if __name__ == '__main__':
    unittest.main()
