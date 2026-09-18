import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from evaluate_policy import (assess, cell_danger, effective_value, load_policy, reachability,
                             resolve_limits, with_obstacle, within_limits,
                             DIRECT, INVENTORY, RESTOCKING, RANDOM)
from export_items import ExportError

POLICY = {
    'schemaVersion': '1.0.0', 'policyVersion': 'test', 'name': 'test policy',
    'hostileFightThreshold': 70,
    'earlyGame': {'characterLevel': 1, 'maxGoldPerItem': 500, 'allowTheft': False,
                  'assumeFactionAccess': True, 'requireGuaranteedSource': True,
                  'countRestockingMerchantsAsGuaranteed': True,
                  'vendorOwnedPlacementsArePurchasable': True, 'allowBrokenItems': False,
                  'danger': {'benchmark': {'profile': 'p', 'cellKey': 'tomb'}, 'limits': None}}}

WORLD_SQL = '''
CREATE TABLE objects(version_id INTEGER PRIMARY KEY,record_type TEXT,object_key TEXT,name TEXT);
CREATE TABLE profile_objects(profile_id TEXT,object_key TEXT,version_id INTEGER);
CREATE TABLE actors(version_id INTEGER PRIMARY KEY,level INTEGER,details TEXT);
CREATE TABLE leveled_lists(version_id INTEGER PRIMARY KEY,chance_none INTEGER);
CREATE TABLE leveled_entries(list_version_id INTEGER,object_key TEXT,minimum_level INTEGER);
CREATE TABLE placements(version_id INTEGER PRIMARY KEY,reference_key TEXT,object_key TEXT,cell_key TEXT);
CREATE TABLE profile_placements(profile_id TEXT,reference_key TEXT,version_id INTEGER);
CREATE INDEX placement_cell ON placements(cell_key,version_id);
CREATE INDEX object_lookup ON profile_objects(profile_id,object_key);
'''
SERVICES_SQL = '''
CREATE TABLE providers(version_id INTEGER PRIMARY KEY,services_raw INTEGER);
CREATE TABLE profile_providers(profile_id TEXT,actor_key TEXT,version_id INTEGER);
'''


class World:
    """A minimal world holding only what the policy evaluator reads."""
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript(WORLD_SQL)
        self.services = sqlite3.connect(':memory:')
        self.services.executescript(SERVICES_SQL)
        self.next = 1

    def close(self):
        self.db.close()
        self.services.close()

    def object(self, key, record_type, name=None, **kind):
        version = self.next
        self.next += 1
        self.db.execute('INSERT INTO objects VALUES(?,?,?,?)', (version, record_type, key, name or key))
        self.db.execute('INSERT INTO profile_objects VALUES(?,?,?)', ('p', key, version))
        if 'level' in kind:
            self.db.execute('INSERT INTO actors VALUES(?,?,?)', (version, kind['level'], json.dumps(
                {'health': kind.get('health', 10), 'ai': {'fight': kind.get('fight', 30)}})))
        if 'entries' in kind:
            self.db.execute('INSERT INTO leveled_lists VALUES(?,0)', (version,))
            for target, minimum in kind['entries']:
                self.db.execute('INSERT INTO leveled_entries VALUES(?,?,?)', (version, target, minimum))
        return version

    def place(self, key, cell):
        version = self.next
        self.next += 1
        self.db.execute('INSERT INTO placements VALUES(?,?,?,?)', (version, f'ref{version}', key, cell))
        self.db.execute('INSERT INTO profile_placements VALUES(?,?,?)', ('p', f'ref{version}', version))
        return version

    def merchant(self, key, services_raw):
        version = self.db.execute('SELECT version_id FROM profile_objects WHERE object_key=?', (key,)).fetchone()[0]
        self.services.execute('INSERT INTO providers VALUES(?,?)', (version, services_raw))
        self.services.execute('INSERT INTO profile_providers VALUES(?,?,?)', ('p', key, version))


def static(nodes, edges, placements):
    return {'nodes': nodes, 'edges': edges, 'placements': placements,
            'truncated': False, 'limitReasons': []}


def node(version, key, record_type, name=None):
    return {'versionId': version, 'key': key, 'recordType': record_type, 'name': name or key, 'depth': 0}


def edge(parent, target, kind='inventory', **details):
    return {'parentVersionId': parent, 'targetVersionId': target, 'kind': kind, 'details': details}


def placement(node_version, cell, **extra):
    return {'nodeVersionId': node_version, 'placementVersionId': 1, 'referenceKey': 'r',
            'cellKey': cell, 'ownerKey': extra.get('owner'), 'factionKey': extra.get('faction'),
            'details': {'lockLevelRaw': 0, 'trapId': None,
                        'itemChargeOrConditionRaw': extra.get('condition', -1)}}


class PolicyDocumentTests(unittest.TestCase):
    def write(self, policy):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(policy, handle)
        handle.close()
        self.addCleanup(lambda: Path(handle.name).unlink(missing_ok=True))
        return handle.name

    def test_shipped_policy_loads(self):
        policy = load_policy(Path(__file__).parent/'policy/early-game.json')
        self.assertEqual(policy['earlyGame']['maxGoldPerItem'], 500)
        self.assertFalse(policy['earlyGame']['allowTheft'])

    def test_schema_and_field_validation(self):
        for broken, message in [
                ({'schemaVersion': '9.9.9'}, 'schema'),
                (POLICY | {'earlyGame': None}, 'earlyGame'),
                (POLICY | {'hostileFightThreshold': 'high'}, 'hostileFightThreshold')]:
            with self.assertRaises(ExportError):
                load_policy(self.write(broken))

    def test_booleans_are_not_accepted_as_numbers(self):
        policy = copy.deepcopy(POLICY)
        policy['earlyGame']['maxGoldPerItem'] = True
        with self.assertRaises(ExportError):
            load_policy(self.write(policy))

    def test_danger_needs_limits_or_a_benchmark(self):
        policy = copy.deepcopy(POLICY)
        policy['earlyGame']['danger'] = {}
        with self.assertRaises(ExportError):
            load_policy(self.write(policy))


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.world.object('ghost', 'CREA', level=1, health=23, fight=90)
        self.world.object('bonewalker', 'CREA', level=4, health=60, fight=90)
        self.world.object('champion', 'CREA', level=10, health=150, fight=90)
        self.world.object('lev_low', 'LEVC', entries=[('ghost', 1), ('bonewalker', 1), ('champion', 7)])
        self.world.object('lev_high', 'LEVC', entries=[('champion', 5)])
        self.world.object('shopkeeper', 'NPC_', level=6, health=90, fight=30)
        self.world.place('lev_low', 'tomb')
        self.world.place('lev_high', 'tomb')
        self.world.place('shopkeeper', 'shop')

    def test_level_gating_excludes_lists_with_no_qualifying_entry(self):
        danger = cell_danger(self.world.db, 'p', 'tomb', 1, 70)
        self.assertEqual(danger['hostiles'], 1)
        self.assertEqual((danger['maxActorLevel'], danger['totalHealth']), (4, 60))

    def test_worst_qualifying_candidate_is_chosen(self):
        danger = cell_danger(self.world.db, 'p', 'tomb', 7, 70)
        self.assertEqual(danger['hostiles'], 2)
        self.assertEqual(danger['maxActorLevel'], 10)

    def test_peaceful_actors_are_not_danger(self):
        self.assertEqual(cell_danger(self.world.db, 'p', 'shop', 1, 70)['hostiles'], 0)

    def test_limits_are_measured_from_the_benchmark_cell(self):
        limits = resolve_limits(self.world.db, POLICY)
        self.assertEqual(limits['source'], 'benchmark')
        self.assertEqual((limits['maxHostiles'], limits['maxActorLevel'], limits['maxTotalHealth']), (1, 4, 60))

    def test_authored_limits_win_and_are_labelled(self):
        policy = copy.deepcopy(POLICY)
        policy['earlyGame']['danger']['limits'] = {'maxHostiles': 9, 'maxActorLevel': 9, 'maxTotalHealth': 9}
        limits = resolve_limits(self.world.db, policy)
        self.assertEqual((limits['source'], limits['maxHostiles']), ('authored', 9))

    def test_an_empty_benchmark_cell_is_refused(self):
        policy = copy.deepcopy(POLICY)
        policy['earlyGame']['danger']['benchmark']['cellKey'] = 'shop'
        with self.assertRaises(ExportError):
            resolve_limits(self.world.db, policy)

    def test_a_holder_adds_itself_without_mutating_the_cached_cell(self):
        danger = cell_danger(self.world.db, 'p', 'tomb', 1, 70)
        combined = with_obstacle(danger, {'key': 'guard', 'level': 20, 'health': 200, 'fight': 30})
        self.assertEqual((combined['hostiles'], combined['maxActorLevel'], combined['totalHealth']), (2, 20, 260))
        self.assertEqual(danger['hostiles'], 1)
        self.assertIs(with_obstacle(danger, None), danger)


class ConditionValueTests(unittest.TestCase):
    def test_worth_scales_with_remaining_condition(self):
        # The Glass Dagger case: 4000 gold at 2 of 300 condition is 27 gold.
        worth, condition = effective_value(4000, 300, 2)
        self.assertEqual(worth, 27)
        self.assertTrue(condition['worn'])
        self.assertEqual((condition['raw'], condition['maximum']), (2, 300))

    def test_undamaged_and_unknown_keep_the_base_value(self):
        for raw in (-1, None):
            self.assertEqual(effective_value(4000, 300, raw), (4000, None))
        self.assertEqual(effective_value(4000, None, 2), (4000, None), 'no maximum, no scaling')
        self.assertEqual(effective_value(None, 300, 2), (None, None))

    def test_condition_above_maximum_is_clamped(self):
        self.assertEqual(effective_value(4000, 300, 900)[0], 4000)

    def test_a_broken_item_is_worth_nothing(self):
        worth, condition = effective_value(4000, 300, 0)
        self.assertEqual(worth, 0)
        self.assertEqual(condition['ratio'], 0.0)


class ReachabilityTests(unittest.TestCase):
    def test_quality_ranks_and_leveled_absorption(self):
        rank = reachability(static(
            [node(1, 'item', 'WEAP'), node(2, 'chest', 'CONT'), node(3, 'list', 'LEVI'),
             node(4, 'room', 'CONT'), node(5, 'trader', 'NPC_')],
            [edge(2, 1), edge(3, 1, 'leveled'), edge(4, 3), edge(5, 1, restocking=True)], []))
        self.assertEqual(rank[1], DIRECT)
        self.assertEqual(rank[2], INVENTORY)
        self.assertEqual(rank[3], RANDOM)
        self.assertEqual(rank[4], RANDOM, 'a leveled hop anywhere below makes the whole path random')
        self.assertEqual(rank[5], RESTOCKING)

    def test_the_best_of_several_paths_wins(self):
        rank = reachability(static(
            [node(1, 'item', 'WEAP'), node(2, 'holder', 'CONT'), node(3, 'list', 'LEVI')],
            [edge(3, 1, 'leveled'), edge(2, 3), edge(2, 1)], []))
        self.assertEqual(rank[2], INVENTORY)

    def test_within_limits_checks_every_dimension(self):
        limits = {'maxHostiles': 2, 'maxActorLevel': 4, 'maxTotalHealth': 83}
        self.assertTrue(within_limits({'hostiles': 2, 'maxActorLevel': 4, 'totalHealth': 83}, limits))
        self.assertFalse(within_limits({'hostiles': 3, 'maxActorLevel': 1, 'totalHealth': 1}, limits))
        self.assertFalse(within_limits({'hostiles': 1, 'maxActorLevel': 5, 'totalHealth': 1}, limits))
        self.assertFalse(within_limits({'hostiles': 1, 'maxActorLevel': 1, 'totalHealth': 84}, limits))


class AssessmentTests(unittest.TestCase):
    def setUp(self):
        self.world = World()
        self.addCleanup(self.world.close)
        self.world.object('ghost', 'CREA', level=1, health=23, fight=90)
        self.world.object('lev', 'LEVC', entries=[('ghost', 1)])
        self.world.place('lev', 'tomb')
        self.limits = {'maxHostiles': 2, 'maxActorLevel': 4, 'maxTotalHealth': 83, 'source': 'authored'}

    def assess(self, graph, policy=None, catalogs=None, truncated=False, events=()):
        return assess(self.world.db, self.world.services, catalogs, 'p', graph,
                      {'events': list(events)}, policy or POLICY, self.limits, truncated)

    def test_free_container_in_a_safe_cell_is_eligible(self):
        self.world.object('sword', 'WEAP')
        self.world.object('urn', 'CONT')
        result = self.assess(static([node(1, 'sword', 'WEAP'), node(2, 'urn', 'CONT')],
                                    [edge(2, 1)], [placement(2, 'tomb')]))
        self.assertEqual(result['obtainable'], 'guaranteed')
        self.assertTrue(result['earlyGameEligible'])
        self.assertFalse(result['theftRequired'])
        self.assertEqual(result['routes'][0]['acquisition'], 'take')

    def test_a_carried_item_needs_the_holder_dealt_with(self):
        self.world.object('sword', 'WEAP')
        self.world.object('lord', 'NPC_', name='Lord', level=20, health=200, fight=30)
        result = self.assess(static([node(1, 'sword', 'WEAP'), node(2, 'lord', 'NPC_')],
                                    [edge(2, 1)], [placement(2, 'manor')]))
        route = result['routes'][0]
        self.assertEqual(route['acquisition'], 'pickpocket')
        self.assertTrue(route['theftRequired'])
        self.assertEqual(route['heldBy']['level'], 20)
        self.assertEqual(route['danger']['hostiles'], 1, 'a placid holder is still an obstacle')
        self.assertFalse(result['earlyGameEligible'])
        self.assertTrue(result['theftRequired'])

    def test_a_restocking_merchant_is_a_purchase_under_the_cap(self):
        self.world.object('sword', 'WEAP')
        self.world.object('trader', 'NPC_', level=5, health=50, fight=30)
        self.world.merchant('trader', 1)
        with tempfile.TemporaryDirectory() as tmp:
            catalogs = Path(tmp)
            (catalogs/'p').mkdir()
            (catalogs/'p/Weapons.json').write_text(json.dumps(
                {'records': [{'key': 'sword', 'value': 120}]}), encoding='utf-8')
            result = self.assess(static([node(1, 'sword', 'WEAP'), node(2, 'trader', 'NPC_')],
                                        [edge(2, 1, restocking=True)], [placement(2, 'shop')]),
                                 catalogs=catalogs)
        self.assertEqual(result['saleStatus'], 'restocking')
        self.assertEqual(result['price'], 120)
        self.assertEqual(result['routes'][0]['acquisition'], 'purchase')
        self.assertFalse(result['routes'][0]['theftRequired'])
        self.assertTrue(result['earlyGameEligible'])

    def test_a_price_above_the_cap_fails_with_a_reason(self):
        self.world.object('sword', 'WEAP')
        self.world.object('trader', 'NPC_', level=5, health=50, fight=30)
        self.world.merchant('trader', 1)
        with tempfile.TemporaryDirectory() as tmp:
            catalogs = Path(tmp)
            (catalogs/'p').mkdir()
            (catalogs/'p/Weapons.json').write_text(json.dumps(
                {'records': [{'key': 'sword', 'value': 9000}]}), encoding='utf-8')
            result = self.assess(static([node(1, 'sword', 'WEAP'), node(2, 'trader', 'NPC_')],
                                        [edge(2, 1, restocking=True)], [placement(2, 'shop')]),
                                 catalogs=catalogs)
        self.assertFalse(result['earlyGameEligible'])
        self.assertIn('above the 500 gold cap', ' '.join(result['routes'][0]['reasons']))

    def test_leveled_only_items_are_random_not_guaranteed(self):
        self.world.object('sword', 'WEAP')
        self.world.object('list', 'LEVI')
        result = self.assess(static([node(1, 'sword', 'WEAP'), node(2, 'list', 'LEVI')],
                                    [edge(2, 1, 'leveled')], [placement(2, 'tomb')]))
        self.assertEqual(result['obtainable'], 'random')
        self.assertFalse(result['earlyGameEligible'])
        self.assertIn('leveled list', ' '.join(result['routes'][0]['reasons']))

    def test_theft_toggle_flips_an_owned_route(self):
        self.world.object('sword', 'WEAP')
        self.world.object('crate', 'CONT')
        graph = static([node(1, 'sword', 'WEAP'), node(2, 'crate', 'CONT')],
                       [edge(2, 1)], [placement(2, 'tomb', owner='someone')])
        self.assertFalse(self.assess(graph)['earlyGameEligible'])
        permissive = copy.deepcopy(POLICY)
        permissive['earlyGame']['allowTheft'] = True
        self.assertTrue(self.assess(graph, policy=permissive)['earlyGameEligible'])

    def test_faction_ownership_is_waived_when_access_is_assumed(self):
        self.world.object('sword', 'WEAP')
        self.world.object('crate', 'CONT')
        graph = static([node(1, 'sword', 'WEAP'), node(2, 'crate', 'CONT')],
                       [edge(2, 1)], [placement(2, 'tomb', faction='fighters guild')])
        self.assertTrue(self.assess(graph)['earlyGameEligible'])
        strict = copy.deepcopy(POLICY)
        strict['earlyGame']['assumeFactionAccess'] = False
        self.assertFalse(self.assess(graph, policy=strict)['earlyGameEligible'])

    def test_a_dangerous_cell_fails_with_the_measured_numbers(self):
        self.world.object('sword', 'WEAP')
        self.world.object('urn', 'CONT')
        self.world.object('dragon', 'CREA', level=40, health=900, fight=90)
        self.world.place('dragon', 'lair')
        result = self.assess(static([node(1, 'sword', 'WEAP'), node(2, 'urn', 'CONT')],
                                    [edge(2, 1)], [placement(2, 'lair')]))
        self.assertFalse(result['earlyGameEligible'])
        self.assertIn('danger above the benchmark', ' '.join(result['routes'][0]['reasons']))
        self.assertFalse(result['routes'][0]['dangerWithinBenchmark'])

    def test_script_only_items_are_conditional_and_never_eligible(self):
        self.world.object('sword', 'WEAP')
        result = self.assess(static([node(1, 'sword', 'WEAP')], [], []),
                             events=[{'effectCategory': 'addition'}])
        self.assertEqual(result['obtainable'], 'script_conditional')
        self.assertFalse(result['earlyGameEligible'])
        self.assertIsNone(result['theftRequired'])
        self.assertEqual(result['counts']['scriptGrants'], 1)

    def test_removals_are_not_grants(self):
        self.world.object('sword', 'WEAP')
        result = self.assess(static([node(1, 'sword', 'WEAP')], [], []),
                             events=[{'effectCategory': 'removal'}])
        self.assertEqual(result['obtainable'], 'none')

    def test_truncated_evidence_cannot_prove_a_negative(self):
        self.world.object('sword', 'WEAP')
        self.world.object('dragon', 'CREA', level=40, health=900, fight=90)
        self.world.object('urn', 'CONT')
        self.world.place('dragon', 'lair')
        graph = static([node(1, 'sword', 'WEAP'), node(2, 'urn', 'CONT')],
                       [edge(2, 1)], [placement(2, 'lair')])
        self.assertIsNone(self.assess(graph, truncated=True)['earlyGameEligible'])
        self.assertFalse(self.assess(graph)['earlyGameEligible'])
        self.assertEqual(self.assess(static([node(1, 'sword', 'WEAP')], [], []),
                                     truncated=True)['obtainable'], 'unknown')

    def test_a_single_eligible_route_still_decides_under_truncation(self):
        self.world.object('sword', 'WEAP')
        self.world.object('urn', 'CONT')
        result = self.assess(static([node(1, 'sword', 'WEAP'), node(2, 'urn', 'CONT')],
                                    [edge(2, 1)], [placement(2, 'tomb')]), truncated=True)
        self.assertTrue(result['earlyGameEligible'])

    def shop(self, value, health, condition, policy=None):
        """One worn weapon lying in a weapon merchant's shop, in its own world."""
        world = World()
        self.addCleanup(world.close)
        world.object('dagger', 'WEAP')
        world.object('trader', 'NPC_', level=5, health=50, fight=30)
        world.merchant('trader', 1)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        catalogs = Path(directory.name)
        (catalogs/'p').mkdir()
        (catalogs/'p/Weapons.json').write_text(json.dumps(
            {'records': [{'key': 'dagger', 'value': value, 'health': health}]}), encoding='utf-8')
        graph = static([node(1, 'dagger', 'WEAP')], [],
                       [placement(1, 'shop', owner='trader', condition=condition)])
        return assess(world.db, world.services, catalogs, 'p', graph, {'events': []},
                      policy or POLICY, self.limits, False)

    def test_worn_shop_stock_is_a_purchase_at_its_worn_price(self):
        result = self.shop(4000, 300, 2)
        route = result['routes'][0]
        self.assertEqual(route['acquisition'], 'purchase')
        self.assertFalse(route['theftRequired'])
        self.assertEqual((route['value'], route['price']), (27, 27))
        self.assertEqual(result['basisValue'], 4000, 'the base value stays visible')
        self.assertTrue(result['earlyGameEligible'], 'over the cap at 4000, under it at 27')

    def test_an_undamaged_copy_of_the_same_item_fails_the_cap(self):
        result = self.shop(4000, 300, -1)
        self.assertEqual(result['routes'][0]['value'], 4000)
        self.assertFalse(result['earlyGameEligible'])
        self.assertIn('above the 500 gold cap', ' '.join(result['routes'][0]['reasons']))

    def test_vendor_ownership_can_be_treated_as_theft_instead(self):
        strict = copy.deepcopy(POLICY)
        strict['earlyGame']['vendorOwnedPlacementsArePurchasable'] = False
        route = self.shop(4000, 300, 2, policy=strict)['routes'][0]
        self.assertEqual(route['acquisition'], 'theft')
        self.assertTrue(route['theftRequired'])
        self.assertIsNone(route['price'])

    def test_a_broken_item_is_refused_until_the_policy_allows_it(self):
        result = self.shop(4000, 300, 0)
        self.assertFalse(result['earlyGameEligible'])
        self.assertIn('unusable until repaired', ' '.join(result['routes'][0]['reasons']))
        self.assertIsNone(result['price'], 'broken stock sets no headline price')
        self.assertEqual(result['saleStatus'], 'stocked', 'it is still stocked, just broken')
        permissive = copy.deepcopy(POLICY)
        permissive['earlyGame']['allowBrokenItems'] = True
        allowed = self.shop(4000, 300, 0, policy=permissive)
        self.assertTrue(allowed['earlyGameEligible'])
        self.assertEqual(allowed['price'], 0)

    def test_categories_without_condition_ignore_the_charge_field(self):
        self.world.object('ring', 'CLOT')
        self.world.object('urn', 'CONT')
        result = self.assess(static([node(1, 'ring', 'CLOT'), node(2, 'urn', 'CONT')],
                                    [edge(2, 1)], [placement(2, 'tomb', condition=5)]))
        self.assertIsNone(result['routes'][0]['condition'])

    def test_the_verdict_cites_its_policy(self):
        self.world.object('sword', 'WEAP')
        result = self.assess(static([node(1, 'sword', 'WEAP')], [], []))
        self.assertEqual(result['policy']['version'], 'test')
        self.assertEqual(result['limits']['source'], 'authored')


if __name__ == '__main__':
    unittest.main()
