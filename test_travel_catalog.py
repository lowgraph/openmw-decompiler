import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from build_travel_catalog import (assemble, build, classify, collect, conjurer_edges,
                                  guild_cell, load_travel_policy)
from export_items import ExportError

GUILD = 'interior:vivec, guild of mages'
OTHER_GUILD = 'interior:narsis, guild of mages: commons'
TOWN = 'exterior:-2,-9'


def policy(conjurer=False, **overrides):
    """Gate nothing unless a test says so; the builder refuses an edge it cannot find."""
    base = {
        'schemaVersion': '1.0.0', 'policyVersion': 'test',
        'guildGuide': {'cellMarkers': ['guild of mages'], 'npcClass': 'Guild Guide'},
        'conjurerRank': {'profiles': ['tr'],
                         'cities': {'vivec': GUILD, 'narsis': OTHER_GUILD},
                         'edges': [{'from': 'vivec', 'to': 'narsis'}] if conjurer else []},
        'modes': {'byClass': {'Caravaner': 'silt_strider', 'Guild Guide': 'guild_guide'}},
        'excludedCells': []}
    return base | overrides


class Databases(unittest.TestCase):
    """The builder reads two databases, so the fixtures are two databases."""
    def services(self, providers, cells=()):
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE profile_providers(profile_id,actor_key,version_id,origin_plugin);
          CREATE TABLE providers(version_id,actor_key,record_type,name,plugin,script_key,
                                 services_raw,unknown_service_bits,stats_json);
          CREATE TABLE provider_locations(profile_id,reference_key,placement_version_id,
                                          provider_version_id,cell_key,x,y,z);
          CREATE TABLE profile_destinations(profile_id,provider_version_id,entry_index,
                                            cell_key,status);
          CREATE TABLE cells(profile_id,cell_key,name,interior,grid_x,grid_y,region_key,synthetic);
          CREATE TABLE metadata(key,value);""")
        db.execute("INSERT INTO metadata VALUES('snapshotId','\"snap\"')")
        for index, (actor, name, record_type, home, destinations) in enumerate(providers, 1):
            db.execute('INSERT INTO profile_providers VALUES(?,?,?,?)', ('tr', actor, index, 'p'))
            db.execute('INSERT INTO providers VALUES(?,?,?,?,?,?,?,?,?)',
                       (index, actor, record_type, name, 'p', None, 0, 0, '{}'))
            if home:
                db.execute('INSERT INTO provider_locations VALUES(?,?,?,?,?,?,?,?)',
                           ('tr', 'r', 1, index, home, 0, 0, 0))
            for entry, destination in enumerate(destinations):
                db.execute('INSERT INTO profile_destinations VALUES(?,?,?,?,?)',
                           ('tr', index, entry, destination, 'resolved'))
        for key, name, interior, region in cells:
            db.execute('INSERT INTO cells VALUES(?,?,?,?,?,?,?,?)',
                       ('tr', key, name, interior, 0, 0, region, 0))
        db.commit()
        return db

    def game(self, classes):
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE resolved_records(profile_id,record_type,record_key,origin_plugin_id,winner_id);
          CREATE TABLE record_versions(id,plugin_id,ordinal,file_offset,record_type,record_key,
                                       display_id,deleted,header_unknown,header_flags,payload);""")
        for index, (actor, klass) in enumerate(classes.items(), 1):
            payload = b'NAME\x04\x00\x00\x00xxx\x00'
            if klass is not None:
                body = klass.encode('cp1252')+b'\x00'
                payload += b'CNAM'+len(body).to_bytes(4, 'little')+body
            db.execute('INSERT INTO record_versions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (index, 1, 0, 0, 'NPC_', actor, actor, 0, 0, 0, payload))
            db.execute('INSERT INTO resolved_records VALUES(?,?,?,?,?)',
                       ('tr', 'NPC_', actor, 1, index))
        db.commit()
        return db


class GuildGuideTests(Databases):
    def test_a_provider_whose_every_stop_is_a_mages_guild_is_a_guide(self):
        services = self.services([('guide', 'Guide', 'NPC_', TOWN, [GUILD, OTHER_GUILD])])
        providers, _, _ = collect(services, 'tr', policy())
        classify(providers, {'guide': 'Guild Guide'}, policy())
        self.assertTrue(providers['guide']['guildGuide'])

    def test_a_caravaner_is_not(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, ['exterior:1,1'])])
        providers, _, _ = collect(services, 'tr', policy())
        classify(providers, {'driver': 'Caravaner'}, policy())
        self.assertFalse(providers['driver']['guildGuide'])

    def test_a_creature_with_no_class_is_still_a_guide(self):
        # Thazlorakis, the bound Daedroth who serves Firewatch. Keying on the NPC class
        # loses her and with her every Firewatch Conjurer route.
        services = self.services([('daedroth', 'Thazlorakis', 'CREA', TOWN, [GUILD])])
        providers, _, _ = collect(services, 'tr', policy())
        disagreement = classify(providers, {'daedroth': None}, policy())
        self.assertTrue(providers['daedroth']['guildGuide'])
        self.assertEqual(providers['daedroth']['mode'], 'guild_guide',
                         'a classless guide still travels by guild teleport')
        self.assertEqual([d['key'] for d in disagreement], ['daedroth'])

    def test_a_provider_that_mixes_guild_and_other_stops_is_refused(self):
        # The whole rule rests on this never happening; if it does, say so loudly.
        services = self.services([('mixed', 'Mixed', 'NPC_', TOWN, [GUILD, 'exterior:1,1'])])
        providers, _, _ = collect(services, 'tr', policy())
        with self.assertRaises(ExportError) as caught:
            classify(providers, {'mixed': 'Guild Guide'}, policy())
        self.assertIn('mixed', str(caught.exception))

    def test_the_two_rules_agreeing_reports_nothing(self):
        services = self.services([('guide', 'Guide', 'NPC_', TOWN, [GUILD]),
                                  ('driver', 'Driver', 'NPC_', TOWN, ['exterior:1,1'])])
        providers, _, _ = collect(services, 'tr', policy())
        self.assertEqual(classify(providers, {'guide': 'Guild Guide',
                                              'driver': 'Caravaner'}, policy()), [])

    def test_cell_markers_are_case_insensitive(self):
        self.assertTrue(guild_cell('interior:VIVEC, Guild of Mages', ['guild of mages']))


class EdgeTests(Databases):
    def test_an_edge_is_published_per_origin_and_destination(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, ['exterior:1,1', 'exterior:2,2'])])
        network = build(services, self.game({'driver': 'Caravaner'}), 'tr', policy())
        self.assertEqual(len(network['edges']), 2)
        self.assertEqual({e['mode'] for e in network['edges']}, {'silt_strider'})

    def test_a_provider_standing_where_they_would_send_you_makes_no_edge(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, [TOWN, 'exterior:1,1'])])
        network = build(services, self.game({'driver': 'Caravaner'}), 'tr', policy())
        self.assertEqual([e['to'] for e in network['edges']], ['exterior:1,1'])

    def test_an_unplaced_provider_contributes_no_edge_but_is_named(self):
        services = self.services([('ghost', 'Ghost', 'NPC_', None, ['exterior:1,1'])])
        network = build(services, self.game({'ghost': 'Caravaner'}), 'tr', policy())
        self.assertEqual(network['edges'], [])
        self.assertEqual(network['verification']['unplacedProviders'], ['ghost'])

    def test_an_excluded_cell_is_dropped(self):
        # Todd's Super Tester Guy really does sell travel to a developer test cell.
        services = self.services([('todd', 'Todd', 'NPC_', TOWN, ['interior:toddtest'])])
        rules = policy(excludedCells=['interior:toddtest'])
        network = build(services, self.game({'todd': 'Caravaner'}), 'tr', rules)
        self.assertEqual(network['edges'], [])
        self.assertEqual(network['verification']['destinationsSkipped'], 1)

    def test_edge_keys_are_unique_because_the_bundle_requires_it(self):
        services = self.services([('a', 'A', 'NPC_', TOWN, ['exterior:1,1', 'exterior:2,2']),
                                  ('b', 'B', 'NPC_', TOWN, ['exterior:1,1'])])
        network = build(services, self.game({'a': 'Caravaner', 'b': 'Caravaner'}), 'tr', policy())
        keys = [e['key'] for e in network['edges']]
        self.assertEqual(len(keys), len(set(keys)))

    def test_an_unknown_class_publishes_a_null_mode_rather_than_a_guess(self):
        services = self.services([('slave', 'Slave', 'NPC_', TOWN, ['exterior:1,1'])])
        network = build(services, self.game({'slave': 'Slave'}), 'tr', policy())
        self.assertIsNone(network['edges'][0]['mode'])
        self.assertEqual(network['verification']['providersWithUnknownMode'], ['slave'])


class ConjurerTests(Databases):
    def guide_pair(self):
        return [('ohmonir', 'Ohmonir', 'NPC_', GUILD, [OTHER_GUILD]),
                ('lissinia', 'Lissinia', 'NPC_', OTHER_GUILD, [GUILD])]

    def test_an_authored_edge_that_exists_is_marked(self):
        services = self.services(self.guide_pair())
        network = build(services, self.game({'ohmonir': 'Guild Guide', 'lissinia': 'Guild Guide'}),
                        'tr', policy(conjurer=True))
        gated = [e for e in network['edges'] if e['requiresConjurer']]
        self.assertEqual([(e['from'], e['to']) for e in gated], [(GUILD, OTHER_GUILD)])
        self.assertTrue(all(e['requiresMageGuild'] for e in gated),
                        'a rank-gated route is still a guild route')

    def test_the_reverse_direction_is_not_gated_unless_authored(self):
        services = self.services(self.guide_pair())
        network = build(services, self.game({'ohmonir': 'Guild Guide', 'lissinia': 'Guild Guide'}),
                        'tr', policy(conjurer=True))
        back = next(e for e in network['edges'] if e['from'] == OTHER_GUILD)
        self.assertFalse(back['requiresConjurer'], 'edges are directed, as authored')

    def test_an_authored_edge_that_matches_nothing_fails_the_build(self):
        # A renamed cell would otherwise empty the toggle in silence.
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, ['exterior:1,1'])])
        with self.assertRaises(ExportError) as caught:
            build(services, self.game({'driver': 'Caravaner'}), 'tr', policy(conjurer=True))
        self.assertIn('vivec -> narsis', str(caught.exception))

    def test_vanilla_gates_nothing(self):
        self.assertEqual(conjurer_edges(policy(conjurer=True), 'vanilla'), {})

    def test_the_profiles_list_decides_which_profiles_are_gated(self):
        rules = policy(conjurer=True)
        rules['conjurerRank'] = rules['conjurerRank'] | {'profiles': ['tr', 'tr_arce']}
        self.assertEqual(len(conjurer_edges(rules, 'tr_arce')), 1)


class NodeTests(Databases):
    def test_a_named_cell_carries_its_name_and_region(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, [GUILD])],
                                 cells=[(TOWN, 'Seyda Neen', 0, 'bitter coast region'),
                                        (GUILD, 'Guild of Mages', 1, None)])
        network = build(services, self.game({'driver': 'Caravaner'}), 'tr', policy())
        self.assertEqual(network['nodes'][TOWN]['name'], 'Seyda Neen')
        self.assertEqual(network['nodes'][TOWN]['region'], 'bitter coast region')
        self.assertTrue(network['nodes'][GUILD]['interior'])

    def test_an_endpoint_with_no_cell_row_is_kept_rather_than_dropped(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, [GUILD])])
        network = build(services, self.game({'driver': 'Caravaner'}), 'tr', policy())
        self.assertEqual(sorted(network['nodes']), sorted([TOWN, GUILD]))
        self.assertIsNone(network['nodes'][TOWN]['name'])

    def test_only_cells_the_network_touches_are_published(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, [GUILD])],
                                 cells=[('exterior:99,99', 'Somewhere Else', 0, None)])
        network = build(services, self.game({'driver': 'Caravaner'}), 'tr', policy())
        self.assertNotIn('exterior:99,99', network['nodes'])


class PolicyTests(unittest.TestCase):
    def write(self, payload):
        path = Path(tempfile.mkdtemp())/'travel.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_an_unreadable_schema_is_refused(self):
        with self.assertRaises(ExportError):
            load_travel_policy(self.write(policy(schemaVersion='9.9.9')))

    def test_an_edge_naming_an_unknown_city_is_refused(self):
        rules = policy(conjurer=True)
        rules['conjurerRank'] = rules['conjurerRank'] | {
            'edges': [{'from': 'vivec', 'to': 'atlantis'}]}
        with self.assertRaises(ExportError) as caught:
            load_travel_policy(self.write(rules))
        self.assertIn('atlantis', str(caught.exception))

    def test_the_shipped_policy_loads(self):
        loaded = load_travel_policy(Path(__file__).parent/'policy/travel.json')
        self.assertEqual(len(loaded['conjurerRank']['edges']), 12, 'four cities, three each')
        self.assertEqual(len(loaded['conjurerRank']['cities']), 4)

    def test_the_shipped_policy_gates_only_tamriel_rebuilt(self):
        loaded = load_travel_policy(Path(__file__).parent/'policy/travel.json')
        self.assertNotIn('vanilla', loaded['conjurerRank']['profiles'])


class PayloadTests(Databases):
    def test_the_payload_carries_the_toggles_and_their_defaults(self):
        services = self.services([('guide', 'Guide', 'NPC_', GUILD, [OTHER_GUILD])])
        payload = assemble(services, self.game({'guide': 'Guild Guide'}), 'tr', policy(), 'snap')
        self.assertTrue(payload['toggles']['mageGuildMember']['default'])
        self.assertFalse(payload['toggles']['conjurerRank']['default'])
        self.assertEqual(payload['snapshotId'], 'snap')
        self.assertEqual(payload['authored']['source'], 'authored')

    def test_every_edge_has_the_key_the_bundle_joins_on(self):
        services = self.services([('guide', 'Guide', 'NPC_', GUILD, [OTHER_GUILD])])
        payload = assemble(services, self.game({'guide': 'Guild Guide'}), 'tr', policy(), 'snap')
        self.assertTrue(all(isinstance(e.get('key'), str) and e['key'] for e in payload['edges']))


if __name__ == '__main__':
    unittest.main()
