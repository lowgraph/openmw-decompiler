import contextlib
import copy
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from build_acquisition_index import build as index_build, metadata
from build_ingredient_sources import (ALL_LEVELS, Evidence, Places, Spread, assemble, build, check_transcription,
                                      draw_chance, first_chance, fingerprint, main, outcomes)
from inspect_acquisition_index import query_item
from export_items import ExportError
from build_world_catalog import build as world_build
from evaluate_policy import load_policy
from extract_foundation import ROOT
import test_world_catalog
from test_export_items import pack_record
from test_export_locations import cell, holder, leveled, reference


def lists_of(table):
    """A levelled-list reader over {key: (kind, chance_none, flags, [(entry, level)])}."""
    return table.get


class DrawChanceTests(unittest.TestCase):
    def test_chance_none_comes_first(self):
        lists = lists_of({'plant': ('LEVI', 20, 0, [('root', 1)])})
        self.assertAlmostEqual(draw_chance(lists, 'plant', 'root', 1), 0.8)
        self.assertEqual(draw_chance(lists, 'plant', 'other', 1), 0.0)
        self.assertEqual(draw_chance(lists, 'missing', 'root', 1), 0.0, 'not a list')

    def test_only_the_highest_level_unless_all_levels(self):
        entries = [('root', 1), ('other', 5)]
        highest = lists_of({'l': ('LEVI', 0, 0, entries)})
        self.assertEqual(draw_chance(highest, 'l', 'root', 1), 1.0, 'level 1: root is the only entry')
        self.assertEqual(draw_chance(highest, 'l', 'root', 5), 0.0, 'level 5: only the level 5 entry')
        every = lists_of({'l': ('LEVI', 0, ALL_LEVELS['LEVI'], entries)})
        self.assertEqual(draw_chance(every, 'l', 'root', 5), 0.5, 'all levels: either')
        # The same flag sits on another bit for creature lists; the item bit means nothing there.
        creatures = lists_of({'c': ('LEVC', 0, ALL_LEVELS['LEVI'], entries)})
        self.assertEqual(draw_chance(creatures, 'c', 'root', 5), 0.0)
        creatures = lists_of({'c': ('LEVC', 0, ALL_LEVELS['LEVC'], entries)})
        self.assertEqual(draw_chance(creatures, 'c', 'root', 5), 0.5)

    def test_nested_lists_multiply_and_cycles_end(self):
        lists = lists_of({'outer': ('LEVI', 50, 0, [('inner', 1)]),
                          'inner': ('LEVI', 0, ALL_LEVELS['LEVI'], [('root', 1), ('other', 1), ('outer', 1)])})
        self.assertAlmostEqual(draw_chance(lists, 'outer', 'root', 1), 0.5 / 3)
        # The cycle shows up as itself, so a looping list is never taken for a single-ingredient one.
        self.assertEqual(outcomes(lists, 'outer'), {'root', 'other', 'outer'})

    def test_a_list_that_starts_later_names_its_level(self):
        lists = lists_of({'late': ('LEVI', 0, 0, [('root', 7)]), 'empty': ('LEVI', 100, 0, [('root', 1)])})
        self.assertEqual(first_chance(lists, 'late', 'root'), (1.0, 7))
        self.assertEqual(first_chance(lists, 'empty', 'root'), (0.0, None), 'chance-none 100 never gives it')

    def test_outcomes_tell_a_deposit_from_random_loot(self):
        lists = lists_of({'deposit': ('LEVI', 50, 0, [('root', 1)]),
                          'barrel': ('LEVI', 0, 0, [('root', 1), ('bread', 1)]),
                          'wrapped': ('LEVI', 0, 0, [('deposit', 1)])})
        self.assertEqual(outcomes(lists, 'deposit'), {'root'})
        self.assertEqual(outcomes(lists, 'wrapped'), {'root'}, 'through a nested list')
        self.assertEqual(outcomes(lists, 'barrel'), {'root', 'bread'})


class PlacesTests(unittest.TestCase):
    def places(self, rows, near=('ebonheart', 'old ebonheart', 'balmora')):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE cells(profile_id,cell_key,name,interior,grid_x,grid_y,region_key,deleted)')
        db.executemany('INSERT INTO cells VALUES (?,?,?,?,?,?,?,0)', [('tr', *row) for row in rows])
        return Places(db, 'tr', near)

    def test_towns_their_neighbours_and_the_longest_name(self):
        p = self.places([('exterior:0,0', 'Ebonheart', 0, 0, 0, 'ascadian isles region'),
                         ('exterior:20,0', 'Old Ebonheart', 0, 20, 0, 'old ebonheart region'),
                         ('exterior:1,1', None, 0, 1, 1, 'ascadian isles region'),
                         ('exterior:5,5', None, 0, 5, 5, None),
                         ('interior:balmora, guild of mages', 'Balmora, Guild of Mages', 1, None, None, None)])
        self.assertEqual(p.near('exterior:0,0'), 'Ebonheart')
        self.assertEqual(p.near('exterior:20,0'), 'Old Ebonheart', 'not Ebonheart')
        self.assertEqual(p.near('exterior:1,1'), 'Ebonheart', 'the square next to town')
        self.assertIsNone(p.near('exterior:5,5'))
        self.assertEqual(p.near('interior:balmora, guild of mages'), 'Balmora', 'named by its own cell, title-cased')
        self.assertEqual(p.region('exterior:5,5'), 'wilderness', 'an exterior without a region')
        self.assertIsNone(p.region('interior:balmora, guild of mages'))
        self.assertIsNone(p.near('interior:not a cell we know'))

    def test_ties_are_broken_by_key_whatever_the_order_placements_arrive_in(self):
        from collections import Counter
        spreads = []
        for order in (['b', 'a', 'c', 'd'], ['d', 'c', 'a', 'b']):
            spread = Spread()
            spread.regions = Counter({key: 1 for key in order})
            spread.cells = Counter({f'interior:{key}': 2 for key in order})
            spread.count = 8
            spreads.append(spread.publish())
        self.assertEqual(spreads[0], spreads[1])
        self.assertEqual(spreads[0]['regions'][:2], [['a', 1], ['b', 1]])

AIDT_INGREDIENTS = struct.pack('<Bx3B3xI', 30, 0, 20, 0, 0x10)


def npc(ident, *inventory, services=AIDT_INGREDIENTS):
    fields = [('NAME', ident.encode()), ('FNAM', ident.title().encode()),
              ('NPDT', struct.pack('<h3B3xi', 3, 50, 0, 0, 0)), ('AIDT', services)]
    return pack_record('NPC_', fields + [('NPCO', struct.pack('<i', n) + key.encode().ljust(32, b'\0'))
                                         for key, n in inventory])


def container(ident, name, flags, target, count=1):
    return pack_record('CONT', [('NAME', ident.encode()), ('FNAM', name.encode()), ('CNDT', struct.pack('<f', 10)),
                                ('FLAG', struct.pack('<I', flags)),
                                ('NPCO', struct.pack('<i', count) + target.encode().ljust(32, b'\0'))])


ORGANIC, RESPAWNS = 0x1, 0x2


class EndToEndTests(unittest.TestCase):
    """A small world through the real world and index builders, then classified."""

    def fixture(self, root):
        extra = pack_record('INGR', [('NAME', b'ingred_test'), ('FNAM', b'Test Root')])
        extra += pack_record('INGR', [('NAME', b'ingred_other'), ('FNAM', b'Other Root')])
        extra += leveled('LEVI', 'random_test', 'ingred_test', level=1, none=20)
        extra += pack_record('LEVI', [('NAME', b'random_mixed'), ('DATA', struct.pack('<I', 0)),
                                      ('NNAM', bytes([0])), ('INDX', struct.pack('<I', 2)),
                                      ('INAM', b'ingred_test'), ('INTV', struct.pack('<h', 1)),
                                      ('INAM', b'ingred_other'), ('INTV', struct.pack('<h', 1))])
        extra += container('flora_test', 'Test Plant', ORGANIC | RESPAWNS, 'random_test')
        extra += container('rock_test', 'Test Deposit', ORGANIC, 'random_test', 4)
        extra += container('barrel_test', 'Barrel', ORGANIC, 'random_mixed')
        extra += container('crate_test', 'Crate', 0, 'ingred_test', 2)
        extra += npc('test merchant', ('ingred_test', -3))
        extra += npc('test farmer', ('ingred_test', 1), services=struct.pack('<Bx3B3xI', 30, 0, 20, 0, 0))
        extra += pack_record('CREA', [('NAME', b'test crab'), ('FNAM', b'Test Crab'),
                                      ('NPDT', struct.pack('<24i', 0, 2, *range(22))),
                                      ('NPCO', struct.pack('<i', 1) + b'ingred_test'.ljust(32, b'\0'))])
        extra += leveled('LEVC', 'test spawn', 'test crab', level=1, none=0)
        # Creature loot: a long list gives the root 1 kill in 6, random loot; a short one gives
        # it 1 in 2, a drop to count on (CREATURE_MIN_CHANCE is 1 in 5).
        def loot(ident, entries):
            fields = [('NAME', ident.encode()), ('DATA', struct.pack('<I', 0)), ('NNAM', bytes([0])),
                      ('INDX', struct.pack('<I', len(entries)))]
            for entry in entries:
                fields += [('INAM', entry.encode()), ('INTV', struct.pack('<h', 1))]
            return pack_record('LEVI', fields)
        extra += loot('random_many', ['ingred_test'] + ['gem'] * 5) + loot('random_pair', ['ingred_test', 'gem'])
        for ident, name, held in (('test ghoul', 'Test Ghoul', 'random_many'), ('test spriggan', 'Test Spriggan', 'random_pair')):
            extra += pack_record('CREA', [('NAME', ident.encode()), ('FNAM', name.encode()),
                                          ('NPDT', struct.pack('<24i', 0, 3, *range(22))),
                                          ('NPCO', struct.pack('<i', 1) + held.encode().ljust(32, b'\0'))])
        town = [('RGNN', b'test region')]
        extra += cell('Testtown', town + reference(10, 'flora_test') + reference(11, 'flora_test'), exterior=(10, 10))
        extra += cell('', town + reference(12, 'flora_test'), exterior=(11, 10))
        extra += cell('', [('RGNN', b'far region')] + reference(13, 'flora_test') + reference(14, 'test spawn')
                      + reference(15, 'rock_test') + reference(16, 'barrel_test')
                      + reference(17, 'test ghoul') + reference(18, 'test spriggan'), exterior=(30, 30))
        extra += cell('Testtown, Shop', reference(20, 'test merchant')
                      + reference(21, 'crate_test', ('ANAM', b'test merchant')))
        extra += cell('Testtown, House', reference(22, 'test farmer') + reference(23, 'ingred_test', ('ANAM', b'test farmer')))
        extra += cell('Test Cave', reference(24, 'ingred_test') + reference(25, 'crate_test'))
        extra += cell('TR_Hold_Test', reference(26, 'test merchant'))
        source = test_world_catalog.WorldTests().fixture(root, extra)
        world = world_build(source, root/'world')
        index = index_build(world, root/'index')
        services = root/'services.sqlite'
        with contextlib.closing(sqlite3.connect(services)) as db:
            db.executescript((ROOT/'schemas'/'services_schema.sql').read_text(encoding='utf-8'))
            db.execute("INSERT INTO providers VALUES (1,'test merchant','NPC_','Test Merchant','mod.esp',NULL,16,0,'{}')")
            db.execute("INSERT INTO providers VALUES (2,'test farmer','NPC_','Test Farmer','mod.esp',NULL,0,0,'{}')")
            db.execute("INSERT INTO profiles VALUES ('tr','tamriel_rebuilt','test',0)")
            db.executemany("INSERT INTO profile_providers VALUES ('tr',?,?,'mod.esp')", [('test merchant', 1), ('test farmer', 2)])
            with contextlib.closing(sqlite3.connect(index)) as a:
                db.execute('INSERT INTO metadata VALUES (?,?)', ('snapshotId', json.dumps(metadata(a)['snapshotId'])))
            db.commit()
        return world, index, services

    def policy(self):
        policy = copy.deepcopy(load_policy(ROOT/'policy'/'early-game.json'))
        policy['earlyGame']['nearStart']['places'] = ['testtown']
        return policy

    def run_build(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        with contextlib.redirect_stdout(io.StringIO()):
            world, index, services = self.fixture(Path(directory.name))
        with contextlib.closing(sqlite3.connect(world)) as w, contextlib.closing(sqlite3.connect(index)) as a, \
                contextlib.closing(sqlite3.connect(services)) as s, contextlib.redirect_stdout(io.StringIO()):
            records, skipped = build(w, a, s, 'tr', self.policy())
        return {r['key']: r for r in records}, skipped

    def test_each_kind_of_source(self):
        records, skipped = self.run_build()
        root = records['ingred_test']
        self.assertEqual(root['name'], 'Test Root')
        # The merchant's own restocking stock and the crate they own where they trade are one
        # shop; their copy in a holding cell is not.
        [shop] = root['shops']
        self.assertEqual((shop['seller'], shop['name'], shop['quantity'], shop['restocks'], shop['near']),
                         ('test merchant', 'Test Merchant', 5, True, 'Testtown'))
        self.assertEqual(shop['cellKey'], 'interior:testtown, shop')
        [plant] = root['plants']
        self.assertEqual((plant['name'], plant['chance'], plant['quantity'], plant['regrows'], plant['count']),
                         ('Test Plant', 0.8, 1, True, 4))
        self.assertEqual(plant['near'], [['Testtown', 3]], 'two in town and one next to it')
        self.assertEqual(dict(map(tuple, plant['regions'])), {'test region': 3, 'far region': 1})
        creatures = {c['creature']: c for c in root['creatures']}
        self.assertEqual(set(creatures), {'test crab', 'test spriggan'}, 'not the ghoul and its random loot')
        crab = creatures['test crab']
        self.assertEqual((crab['level'], crab['chance'], crab['placed'], crab['spawnPoints']), (2, 1.0, 0, 1))
        self.assertEqual((creatures['test spriggan']['chance'], creatures['test spriggan']['placed']), (0.5, 1))
        finds = {f.get('name', 'loose'): f for f in root['finds']}
        self.assertEqual(set(finds), {'Test Deposit', 'loose', 'Crate'})
        self.assertEqual((finds['Test Deposit']['chance'], finds['Test Deposit']['quantity']), (0.8, 4))
        self.assertEqual(finds['Crate']['cells'], [['interior:test cave', 1]])
        self.assertTrue(finds['loose']['loose'])

    def test_theft_carriers_random_loot_and_holding_cells_are_left_out(self):
        records, skipped = self.run_build()
        self.assertEqual(skipped['theft'], 1, "the farmer's own root on his table")
        self.assertEqual(skipped['carried'], 1, 'the farmer carries one')
        self.assertEqual(skipped['random'], 3, 'the mixed barrel for each root, and the ghoul')
        self.assertEqual(skipped['unreachableCell'], 1, 'the merchant kept in a holding cell')
        other = records['ingred_other']
        self.assertEqual(other, {'key': 'ingred_other', 'name': 'Other Root'}, 'only random loot: no source at all')

    def test_the_published_payload_counts_and_carries_its_policy(self):
        records, skipped = self.run_build()
        payload = assemble(list(records.values()), skipped, 'tr', 'snap', self.policy())
        d = payload['derivation']
        self.assertEqual((d['ingredients'], d['withShop'], d['withPlant'], d['withCreature'],
                          d['withFind'], d['withoutSource']), (2, 1, 1, 1, 1, 1))
        self.assertEqual(d['leftOut'], {'carried': 1, 'random': 3, 'theft': 1, 'unreachableCell': 1})
        self.assertEqual(payload['snapshotId'], 'snap')
        self.assertTrue(all(isinstance(r['key'], str) and r['key'] for r in payload['records']), 'the bundle joins on key')

def copy_profile(paths, source, target):
    """Give `target` exactly `source`'s rows in every database: TR + ARCE as the extraction sees it."""
    for path in paths:
        with contextlib.closing(sqlite3.connect(path)) as db:
            for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
                columns = [c[1] for c in db.execute(f'PRAGMA table_info({table})')]
                key = 'profile_id' if 'profile_id' in columns else 'id' if table == 'profiles' else None
                if key is None:
                    continue
                chosen = ', '.join('?' if c == key else c for c in columns)
                db.execute(f'INSERT INTO {table} SELECT {chosen} FROM {table} WHERE {key}=?', (target, source))
            db.commit()


class FastPathTests(unittest.TestCase):
    """The one-pass reading and the reuse of identical profiles, on the same small world."""
    fixture = EndToEndTests.fixture
    policy = EndToEndTests.policy

    def databases(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        with contextlib.redirect_stdout(io.StringIO()):
            world, index, services = self.fixture(root)
        policy = root/'policy.json'
        policy.write_text(json.dumps(self.policy()), encoding='utf-8')
        return root, world, index, services, policy

    def test_the_in_memory_walk_agrees_with_query_item(self):
        _, world, index, _, _ = self.databases()
        with contextlib.closing(sqlite3.connect(world)) as w, contextlib.closing(sqlite3.connect(index)) as a:
            evidence = Evidence(w, a, 'tr', ['ingred_test', 'ingred_other'])
            edge = lambda e: (e['parentVersionId'], e['targetVersionId'], e['kind'], e['entryIndex'], repr(e['details']))
            place = lambda p: repr((p['nodeVersionId'], p['cellKey'], p['ownerKey'], p['factionKey'],
                                    p['countRaw'], p['directItemPlacement']))
            for key in ('ingred_test', 'ingred_other'):
                mine, theirs = evidence.static(key), query_item(a, w, 'tr', key, 'INGR', max_placements=10000)
                self.assertEqual(mine['rootVersionId'], theirs['rootVersionId'])
                self.assertEqual({n['versionId'] for n in mine['nodes']}, {n['versionId'] for n in theirs['nodes']}, key)
                self.assertEqual(sorted(map(edge, mine['edges'])), sorted(map(edge, theirs['edges'])), key)
                self.assertEqual(sorted(map(place, mine['placements'])), sorted(map(place, theirs['placements'])), key)
                self.assertFalse(mine['truncated'])
            shallow = Evidence(w, a, 'tr', ['ingred_test'], max_depth=1).static('ingred_test')
            self.assertEqual((shallow['truncated'], shallow['limitReasons']), (True, ['max_depth']), 'a cut is reported')

    def run_main(self, root, world, index, services, policy, *profiles):
        argv = ['--world-database', str(world), '--acquisition-database', str(index), '--services-database',
                str(services), '--policy', str(policy), '--output', str(root/'out')]
        for profile in profiles:
            argv += ['--profile', profile]
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            self.assertEqual(main(argv), 0, log.getvalue())
        return log.getvalue(), {path.name.split('-')[0]: json.loads(path.read_text(encoding='utf-8'))
                                for path in sorted((root/'out').glob('*.json'), key=lambda p: p.stat().st_mtime)}

    def test_an_identical_profile_is_built_once_and_reused_across_runs(self):
        root, world, index, services, policy = self.databases()
        copy_profile((world, index, services), 'tr', 'tr_arce')
        log, files = self.run_main(root, world, index, services, policy, 'tr', 'tr_arce')
        self.assertIn('tr_arce: the same inputs as tr; its records reused', log)
        self.assertEqual(log.count('reading its graph'), 1, 'one build for the two')
        tr, arce = files['tr'], files['tr_arce']
        self.assertEqual(arce['records'], tr['records'])
        self.assertEqual(arce['derivation']['reusedFrom'], 'tr')
        self.assertEqual(arce['derivation']['leftOut'], tr['derivation']['leftOut'])
        self.assertEqual(arce['derivation']['inputsFingerprint'], tr['derivation']['inputsFingerprint'])
        # A later run of TR + ARCE alone takes TR's published file.
        log, files = self.run_main(root, world, index, services, policy, 'tr_arce')
        self.assertIn('the same inputs as tr', log)
        self.assertNotIn('reading its graph', log)

    def test_any_difference_in_what_is_read_means_a_build(self):
        root, world, index, services, policy = self.databases()
        copy_profile((world, index, services), 'tr', 'tr_arce')
        with contextlib.closing(sqlite3.connect(world)) as w, contextlib.closing(sqlite3.connect(index)) as a, \
                contextlib.closing(sqlite3.connect(services)) as s:
            same = fingerprint(w, a, s, 'tr', self.policy()), fingerprint(w, a, s, 'tr_arce', self.policy())
            self.assertEqual(same[0], same[1])
            other_policy = self.policy()
            other_policy['earlyGame']['nearStart']['places'] = ['elsewhere']
            self.assertNotEqual(fingerprint(w, a, s, 'tr', other_policy), same[0], 'the policy counts')
            # One loose root fewer in TR + ARCE: no longer the same world.
            w.execute("""DELETE FROM profile_placements WHERE profile_id='tr_arce' AND version_id IN (
                SELECT version_id FROM placements WHERE object_key='ingred_test' AND cell_key='interior:test cave')""")
            w.commit()
            self.assertNotEqual(fingerprint(w, a, s, 'tr_arce', self.policy()), same[0])
        log, files = self.run_main(root, world, index, services, policy, 'tr', 'tr_arce')
        self.assertNotIn('reused', log)
        self.assertEqual(log.count('reading its graph'), 2)
        self.assertNotIn('reusedFrom', files['tr_arce']['derivation'])

    def test_a_partial_run_never_lands_where_the_bundler_looks(self):
        with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit):
            main(['--limit', '1'])
        self.assertIn('--output', err.getvalue())


class TranscriptionTests(unittest.TestCase):
    def test_another_engine_release_is_refused(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE profiles(id, world, version, arce)')
        db.execute("INSERT INTO profiles VALUES ('vanilla', 'vanilla', ?, 0)", (test_world_catalog.VERSIONS['vanilla'],))
        check_transcription(db)
        db.execute("UPDATE profiles SET version = 'OpenMW 0.52.0'")
        with self.assertRaisesRegex(ExportError, 'getLevelledItem'):
            check_transcription(db)
        db.execute('DELETE FROM profiles')
        with self.assertRaisesRegex(ExportError, 'transcribed'):
            check_transcription(db)


if __name__ == '__main__':
    unittest.main()
