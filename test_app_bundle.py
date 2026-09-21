import contextlib
import hashlib
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from build_app_bundle import (base_game_settings, build as build_bundle, delta, differing_settings,
                              pick_base)
from build_catalogs import build as build_catalogs
from extract_foundation import build as build_foundation
from export_items import ExportError
from test_export_items import pack_record, plugin_file, VERSIONS, NAMES
from effect_names import EFFECT_GMSTS


def race(flags):
    """ARCE's real effect: the same race record with its playable flag set."""
    values = [-1, 0]*7 + list(range(16)) + [1.0, 1.0, 1.0, 1.0, flags]
    return pack_record('RACE', [('NAME', b'testrace'), ('FNAM', b'Test Race'),
                                ('RADT', struct.pack('<30i4fI', *values))])


def apply_delta(base_records, payload):
    """The client rule the manifest documents, implemented once for verification."""
    rows = {record.get('key', record.get('id')): record for record in base_records}
    for key in payload['removed']:
        rows.pop(key, None)
    for record in payload['changed']:
        rows[record.get('key', record.get('id'))] = record
    return list(rows.values())


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        raw = json.loads((Path(__file__).parent/'items/examples/sample-records.raw.json').read_text())
        body = b''
        for tag, sample in raw.items():
            body += pack_record(tag, [(f['tag'], bytes.fromhex(f['hex'])) for f in sample['fields']])
        for ident, name in NAMES.items():
            body += pack_record('GMST', [('NAME', EFFECT_GMSTS[ident].encode()), ('STRV', name.encode())])
        body += race(0)
        base, mod, arce = root/'Morrowind.esm', root/'mod.esp', root/'arce.esp'
        plugin_file(base, body)
        plugin_file(mod, pack_record('MISC', [(f['tag'], b'tr_coin' if f['tag'] == 'NAME' else bytes.fromhex(f['hex']))
                                              for f in raw['MISC']['fields']]), ('Morrowind.esm',))
        plugin_file(arce, race(1), ('Morrowind.esm',))
        config = {'profiles': [
            {'id': 'vanilla', 'world': 'vanilla', 'version': VERSIONS['vanilla'], 'arce': False,
             'plugins': [base.name]},
            {'id': 'tr', 'world': 'tamriel_rebuilt', 'version': VERSIONS['tamriel_rebuilt'], 'arce': False,
             'plugins': [base.name, mod.name]},
            {'id': 'tr_arce', 'world': 'tamriel_rebuilt', 'version': VERSIONS['tamriel_rebuilt'], 'arce': True,
             'plugins': [base.name, mod.name, arce.name]}]}
        with contextlib.redirect_stdout(io.StringIO()):
            build_foundation(config, [base, mod, arce], 'cp1252', root/'foundation.sqlite')
            cls.release = build_catalogs(root/'foundation.sqlite', root/'catalogs')
            cls.bundle = build_bundle(root/'catalogs', root/'bundle')
        cls.manifest = json.loads((cls.bundle/'manifest.json').read_text(encoding='utf-8'))
        cls.profiles = {p['id']: p for p in cls.manifest['profiles']}
        cls.root = root

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def catalog(self, profile_id, name):
        return json.loads((self.release/profile_id/(name+'.json')).read_text(encoding='utf-8'))['records']

    def bundled(self, profile_id, name):
        entry = self.profiles[profile_id]['files'][name]
        return json.loads((self.bundle/entry['path']).read_text(encoding='utf-8'))

    def test_book_prose_leaves_the_catalog_and_the_bundle(self):
        books = self.catalog('vanilla', 'Books')
        self.assertTrue(books)
        for book in books:
            self.assertNotIn('text', book)
        texts = {row['key']: row['text'] for row in self.catalog('vanilla', 'BookText')}
        self.assertEqual(sorted(texts), sorted(book['key'] for book in books))
        self.assertTrue(any(texts.values()))
        self.assertNotIn('BookText', self.manifest['catalogs'])
        self.assertNotIn('BookText', self.profiles['vanilla']['files'])
        for book in self.bundled('vanilla', 'Books')['records']:
            self.assertNotIn('text', book)

    def test_skill_book_metadata_survives_the_split(self):
        book = next(b for b in self.bundled('vanilla', 'Books')['records'] if b['skill'])
        self.assertEqual(book['skill'], 'enchant')

    def test_full_profiles_carry_no_base(self):
        for profile_id in ('vanilla', 'tr'):
            self.assertIsNone(self.profiles[profile_id]['base'])
            self.assertEqual(self.profiles[profile_id]['inherits'], [])
            self.assertEqual(self.bundled(profile_id, 'Races')['kind'], 'full')

    def test_arce_ships_only_what_it_changes(self):
        arce = self.profiles['tr_arce']
        self.assertEqual(arce['base'], 'tr')
        self.assertEqual(list(arce['files']), ['Races'])
        self.assertIn('Weapons', arce['inherits'])
        self.assertIn('Books', arce['inherits'])
        payload = self.bundled('tr_arce', 'Races')
        self.assertEqual((payload['kind'], payload['base']), ('delta', 'tr'))
        self.assertEqual(payload['removed'], [])
        self.assertEqual([row['key'] for row in payload['changed']], ['testrace'])
        self.assertTrue(payload['changed'][0]['playable'])
        self.assertFalse(self.catalog('tr', 'Races')[0]['playable'])

    def test_delta_reconstructs_the_full_profile(self):
        rebuilt = apply_delta(self.catalog('tr', 'Races'), self.bundled('tr_arce', 'Races'))
        self.assertEqual(sorted(rebuilt, key=lambda r: r['key']),
                         sorted(self.catalog('tr_arce', 'Races'), key=lambda r: r['key']))
        for name in self.profiles['tr_arce']['inherits']:
            self.assertEqual(self.catalog('tr_arce', name), self.catalog('tr', name))

    def test_arce_costs_a_fraction_of_a_full_profile(self):
        arce = sum(f['bytes'] for f in self.profiles['tr_arce']['files'].values())
        full = sum(f['bytes'] for f in self.profiles['tr']['files'].values())
        self.assertLess(arce, full/10)

    def test_manifest_sizes_and_hashes_match_the_files(self):
        self.assertEqual(self.manifest['totals']['files'],
                         sum(len(p['files']) for p in self.manifest['profiles']))
        total = 0
        for profile in self.manifest['profiles']:
            for entry in profile['files'].values():
                body = (self.bundle/entry['path']).read_bytes()
                self.assertEqual(entry['bytes'], len(body))
                self.assertEqual(entry['sha256'], hashlib.sha256(body).hexdigest())
                self.assertLess(entry['gzipBytes'], entry['bytes'])
                total += entry['bytes']
        self.assertEqual(self.manifest['totals']['bytes'], total)

    def test_pointer_selects_the_release(self):
        pointer = json.loads((self.root/'bundle/current.json').read_text(encoding='utf-8'))
        self.assertEqual(pointer['bundleId'], self.bundle.name)
        self.assertEqual(pointer['snapshotId'], self.manifest['snapshotId'])
        self.assertEqual(self.manifest['catalogSchemaVersion'], '1.1.0')

    def test_single_profile_selection_emits_it_in_full(self):
        with contextlib.redirect_stdout(io.StringIO()):
            alone = build_bundle(self.root/'catalogs', self.root/'bundle-arce', ['tr_arce'])
        manifest = json.loads((alone/'manifest.json').read_text(encoding='utf-8'))
        profile = manifest['profiles'][0]
        self.assertIsNone(profile['base'])
        self.assertEqual(profile['inherits'], [])
        self.assertEqual(json.loads((alone/profile['files']['Races']['path']).read_text(encoding='utf-8'))['kind'], 'full')

    # --- gear rows, built separately but shipped as an ordinary catalog ---

    def rows_dir(self, name, profiles=('vanilla', 'tr', 'tr_arce'), rows=None, snapshot=None):
        directory = self.root/name
        directory.mkdir(parents=True, exist_ok=True)
        default = [{'key': 'shield/-/light/000', 'category': 'shield', 'primary': None},
                   {'key': 'shield/-/heavy/000', 'category': 'shield', 'primary': None}]
        for profile in profiles:
            payload = {'schemaVersion': '1.0.0', 'profile': profile,
                       'snapshotId': snapshot or self.manifest['snapshotId'],
                       'policy': {'version': 'test-policy'}, 'limits': {'source': 'authored'},
                       'categories': ['shield'], 'coverage': 'test rows', 'builtAtUnix': 0.0,
                       'rows': default if rows is None else rows}
            (directory/(profile+'-0000.json')).write_text(json.dumps(payload), encoding='utf-8')
        return directory

    def bundle_with(self, tag, gear_rows=None, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return build_bundle(self.root/'catalogs', self.root/('bundle-'+tag),
                                extras={'GearRows': gear_rows}, **kwargs)

    def test_gear_rows_ship_as_a_catalog_carrying_their_policy(self):
        bundle = self.bundle_with('gear', gear_rows=self.rows_dir('rows-ok'))
        manifest = json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
        self.assertIn('GearRows', manifest['catalogs'])
        vanilla = next(p for p in manifest['profiles'] if p['id'] == 'vanilla')
        payload = json.loads((bundle/vanilla['files']['GearRows']['path']).read_text(encoding='utf-8'))
        self.assertEqual(payload['kind'], 'full')
        self.assertEqual([r['key'] for r in payload['records']],
                         ['shield/-/light/000', 'shield/-/heavy/000'])
        self.assertEqual(payload['policy']['version'], 'test-policy',
                         'the policy that produced the rows travels with them')
        self.assertEqual(payload['limits']['source'], 'authored')

    def test_identical_rows_are_inherited_by_arce(self):
        bundle = self.bundle_with('gear-inherit', gear_rows=self.rows_dir('rows-same'))
        manifest = json.loads((bundle/'manifest.json').read_text(encoding='utf-8'))
        arce = next(p for p in manifest['profiles'] if p['id'] == 'tr_arce')
        self.assertIn('GearRows', arce['inherits'])
        self.assertNotIn('GearRows', arce['files'])

    def test_rows_are_omitted_when_the_directory_is_absent_or_declined(self):
        for tag, gear in (('gear-none', None), ('gear-missing', self.root/'no-such-rows')):
            manifest = json.loads((self.bundle_with(tag, gear_rows=gear)/'manifest.json')
                                  .read_text(encoding='utf-8'))
            self.assertNotIn('GearRows', manifest['catalogs'])

    def test_rows_for_only_some_profiles_are_refused(self):
        partial = self.rows_dir('rows-partial', profiles=('tr',))
        with self.assertRaises(ExportError) as caught:
            self.bundle_with('gear-partial', gear_rows=partial)
        self.assertIn('vanilla', str(caught.exception))

    def test_rows_from_another_snapshot_are_refused(self):
        stale = self.rows_dir('rows-stale', snapshot='a-different-snapshot')
        with self.assertRaises(ExportError) as caught:
            self.bundle_with('gear-stale', gear_rows=stale)
        self.assertIn('different snapshot', str(caught.exception))

    def test_rows_without_a_key_are_refused_before_the_browser_sees_them(self):
        keyless = self.rows_dir('rows-keyless', rows=[{'category': 'shield', 'primary': None}])
        with self.assertRaises(ExportError) as caught:
            self.bundle_with('gear-keyless', gear_rows=keyless)
        self.assertIn('without a key', str(caught.exception))

    def test_duplicate_row_keys_are_refused(self):
        duplicated = self.rows_dir('rows-dupe', rows=[{'key': 'shield/-/light/000'},
                                                      {'key': 'shield/-/light/000'}])
        with self.assertRaises(ExportError) as caught:
            self.bundle_with('gear-dupe', gear_rows=duplicated)
        self.assertIn('duplicate keys', str(caught.exception))

    def test_rebuild_refuses_and_preserves_the_active_pointer(self):
        before = (self.root/'bundle/current.json').read_bytes()
        with self.assertRaises(ExportError):
            build_bundle(self.root/'catalogs', self.root/'bundle')
        self.assertEqual(before, (self.root/'bundle/current.json').read_bytes())
        self.assertFalse((self.root/'bundle/build.lock').exists())

    def test_output_may_not_contain_the_release(self):
        with self.assertRaises(ExportError):
            build_bundle(self.root/'catalogs', self.root/'catalogs')


class LegacyReleaseTests(unittest.TestCase):
    """A schema 1.0.0 release still has prose inside Books; the bundle must strip it."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        release = self.root/'catalogs/abc123'
        (release/'vanilla').mkdir(parents=True)
        profile = {'id': 'vanilla', 'world': 'vanilla', 'version': VERSIONS['vanilla'], 'arce': False}
        (release/'vanilla/Books.json').write_text(json.dumps({
            'schemaVersion': '1.0.0', 'snapshotId': 'snap', 'profile': profile, 'recordType': 'BOOK',
            'records': [{'key': 'b1', 'id': 'b1', 'name': 'A Book', 'skill': 'enchant', 'text': 'x'*5000}]}),
            encoding='utf-8')
        (release/'manifest.json').write_text(json.dumps({
            'schemaVersion': '1.0.0', 'snapshotId': 'snap', 'releaseId': 'abc123',
            'profiles': [profile | {'counts': {'Books': 1}}]}), encoding='utf-8')
        self.release = release

    def tearDown(self):
        self.tmp.cleanup()

    def test_prose_is_stripped_without_rebuilding_catalogs(self):
        with contextlib.redirect_stdout(io.StringIO()):
            bundle = build_bundle(self.release, self.root/'bundle')
        record = json.loads((bundle/'vanilla/Books.json').read_text(encoding='utf-8'))['records'][0]
        self.assertNotIn('text', record)
        self.assertEqual(record['skill'], 'enchant')

    def test_book_text_request_names_the_rebuild(self):
        with self.assertRaises(ExportError) as caught:
            build_bundle(self.release, self.root/'bundle', include_book_text=True)
        self.assertIn('1.1.0', str(caught.exception))


class DeltaUnitTests(unittest.TestCase):
    def test_changed_added_and_removed(self):
        base = [{'key': 'a', 'v': 1}, {'key': 'b', 'v': 2}]
        target = [{'key': 'a', 'v': 1}, {'key': 'b', 'v': 9}, {'key': 'c', 'v': 3}]
        changed, removed = delta(base, target, 'test')
        self.assertEqual(changed, [{'key': 'b', 'v': 9}, {'key': 'c', 'v': 3}])
        self.assertEqual(removed, [])
        changed, removed = delta(target, base, 'test')
        self.assertEqual(changed, [{'key': 'b', 'v': 2}])
        self.assertEqual(removed, ['c'])

    def test_duplicate_keys_fail(self):
        with self.assertRaises(ExportError):
            delta([], [{'key': 'a'}, {'key': 'a'}], 'test')

    def test_derived_rows_join_on_id(self):
        changed, removed = delta([{'id': 'strength', 'index': 0}], [{'id': 'strength', 'index': 1}], 'test')
        self.assertEqual(changed, [{'id': 'strength', 'index': 1}])
        self.assertEqual(removed, [])

    def test_base_is_only_chosen_for_a_matching_world(self):
        tr = {'id': 'tr', 'world': 'tamriel_rebuilt', 'version': '26.08', 'arce': False}
        vanilla = {'id': 'vanilla', 'world': 'vanilla', 'version': '0.51', 'arce': False}
        arce = {'id': 'tr_arce', 'world': 'tamriel_rebuilt', 'version': '26.08', 'arce': True}
        self.assertEqual(pick_base(arce, [vanilla, tr, arce]), 'tr')
        self.assertIsNone(pick_base(tr, [vanilla, tr, arce]))
        self.assertIsNone(pick_base(arce, [vanilla, arce]))
        self.assertIsNone(pick_base(arce | {'version': '26.09'}, [vanilla, tr, arce]))

class GameSettingsTests(unittest.TestCase):
    """The site hardcodes formulas built on game settings; the bundler says when they vary."""
    def settings(self, **values):
        return [{'key': key, 'value': value} for key, value in values.items()]

    def test_identical_settings_report_nothing(self):
        same = self.settings(ilevelup10mult=5, fencumbrancestrmult=5.0)
        self.assertEqual(differing_settings({'vanilla': same, 'tr': same}), [])

    def test_a_changed_value_is_named(self):
        self.assertEqual(differing_settings({
            'vanilla': self.settings(ilevelup10mult=5, fencumbrancestrmult=5.0),
            'tr': self.settings(ilevelup10mult=4, fencumbrancestrmult=5.0)}),
            ['ilevelup10mult'])

    def test_a_setting_only_one_profile_has_counts_as_different(self):
        self.assertEqual(differing_settings({'vanilla': self.settings(a=1),
                                             'tr': self.settings(a=1, snewmodstring='x')}),
                         ['snewmodstring'])

    def test_nothing_to_compare_is_empty_not_an_error(self):
        self.assertEqual(differing_settings({}), [])


class BaseGameSettingsTests(unittest.TestCase):
    """A plugin every profile loads changes a setting in all of them alike, so comparing
    profiles with each other cannot see it. Five official plugins carry game settings."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        raw = json.loads((Path(__file__).parent/'items/examples/sample-records.raw.json').read_text())
        body = b''
        for tag, sample in raw.items():
            body += pack_record(tag, [(f['tag'], bytes.fromhex(f['hex'])) for f in sample['fields']])
        for ident, name in NAMES.items():
            body += pack_record('GMST', [('NAME', EFFECT_GMSTS[ident].encode()), ('STRV', name.encode())])
        body += pack_record('GMST', [('NAME', b'fTestMult'), ('FLTV', struct.pack('<f', 1.0))])
        body += race(0)
        base, dirty = root/'Morrowind.esm', root/'dirty.esp'
        plugin_file(base, body)
        plugin_file(dirty, pack_record('GMST', [('NAME', b'fTestMult'),
                                                ('FLTV', struct.pack('<f', 2.0))]), ('Morrowind.esm',))
        plugins = [base.name, dirty.name]
        config = {'profiles': [
            {'id': 'vanilla', 'world': 'vanilla', 'version': VERSIONS['vanilla'], 'arce': False,
             'plugins': plugins},
            {'id': 'tr', 'world': 'tamriel_rebuilt', 'version': VERSIONS['tamriel_rebuilt'],
             'arce': False, 'plugins': plugins},
            {'id': 'tr_arce', 'world': 'tamriel_rebuilt', 'version': VERSIONS['tamriel_rebuilt'],
             'arce': True, 'plugins': plugins}]}
        cls.foundation = root/'foundation.sqlite'
        with contextlib.redirect_stdout(io.StringIO()):
            build_foundation(config, [base, dirty], 'cp1252', cls.foundation)
            build_catalogs(cls.foundation, root/'catalogs')
        cls.root = root

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def bundle(self, output, foundation):
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            build_bundle(self.root/'catalogs', self.root/output, foundation=foundation)
        return said.getvalue()

    def test_comparing_profiles_only_with_each_other_misses_it(self):
        said = self.bundle('without-base', None)
        self.assertIn('each other only', said)
        self.assertNotIn('ftestmult', said)

    def test_comparing_with_the_base_game_names_it(self):
        said = self.bundle('with-base', self.foundation)
        self.assertIn('Notice: 1 game setting(s) differ', said)
        self.assertIn('the base game and each other', said)
        self.assertIn('ftestmult', said)

    def test_base_values_decode_exactly_as_the_catalogs_do(self):
        snapshot, rows = base_game_settings(self.foundation)
        values = {row['key']: row['value'] for row in rows}
        self.assertEqual(values['ftestmult'], 1.0)
        self.assertEqual(len(snapshot), 64)
        # Every other setting must compare equal, or the check would cry wolf on each.
        catalog = {row['key']: row['value'] for row in json.loads(
            next((self.root/'catalogs').glob('*/vanilla/GameSettings.json')).read_text(
                encoding='utf-8'))['records']}
        self.assertEqual({k for k in catalog if catalog[k] != values.get(k)}, {'ftestmult'})

    def test_no_extraction_means_no_base_comparison_rather_than_a_guess(self):
        self.assertIsNone(base_game_settings(self.root/'absent.sqlite'))
        self.assertIsNone(base_game_settings(None))


if __name__ == '__main__':
    unittest.main()
