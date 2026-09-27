import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from build_travel_catalog import (TRANSCRIBED_FROM, assemble, assign_towns, build,
                                  check_travel_transcription, classify, collect,
                                  conjurer_edges, guild_cell, journey, load_travel_policy,
                                  split_town)
from export_items import ExportError
from testing_support import scratch_dir

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
    def services(self, providers, cells=(), points=None, stats=None):
        """`points` maps an actor to its (x, y, z) and a destination cell to where it lands."""
        points = points or {}
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript("""
          CREATE TABLE profile_providers(profile_id,actor_key,version_id,origin_plugin);
          CREATE TABLE providers(version_id,actor_key,record_type,name,plugin,script_key,
                                 services_raw,unknown_service_bits,stats_json);
          CREATE TABLE provider_locations(profile_id,reference_key,placement_version_id,
                                          provider_version_id,cell_key,x,y,z);
          CREATE TABLE profile_destinations(profile_id,provider_version_id,entry_index,
                                            cell_key,status);
          CREATE TABLE transport_destinations(provider_version_id,entry_index,cell_name,
                                              x,y,z,rx,ry,rz);
          CREATE TABLE cells(profile_id,cell_key,name,interior,grid_x,grid_y,region_key,synthetic);
          CREATE TABLE metadata(key,value);""")
        db.execute("INSERT INTO metadata VALUES('snapshotId','\"snap\"')")
        for index, (actor, name, record_type, home, destinations) in enumerate(providers, 1):
            db.execute('INSERT INTO profile_providers VALUES(?,?,?,?)', ('tr', actor, index, 'p'))
            db.execute('INSERT INTO providers VALUES(?,?,?,?,?,?,?,?,?)',
                       (index, actor, record_type, name, 'p', None, 0, 0,
                        json.dumps((stats or {}).get(actor, {}))))
            if home:
                db.execute('INSERT INTO provider_locations VALUES(?,?,?,?,?,?,?,?)',
                           ('tr', 'r', 1, index, home, *points.get(actor, (0, 0, 0))))
            for entry, destination in enumerate(destinations):
                db.execute('INSERT INTO profile_destinations VALUES(?,?,?,?,?)',
                           ('tr', index, entry, destination, 'resolved'))
                if destination in points:
                    db.execute('INSERT INTO transport_destinations VALUES(?,?,?,?,?,?,?,?,?)',
                               (index, entry, None, *points[destination], 0, 0, 0))
        for cell in cells:
            key, name, interior, region = cell[:4]
            grid = cell[4] if len(cell) > 4 else (0, 0)
            db.execute('INSERT INTO cells VALUES(?,?,?,?,?,?,?,?)',
                       ('tr', key, name, interior, *grid, region, 0))
        db.commit()
        return db

    def game(self, classes):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
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
        path = Path(scratch_dir())/'travel.json'
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


VEHICLES = {'classes': ['Caravaner'], 'radius': 2500, 'markers': [
    {'mode': 'sky_lamp', 'models': ['skylamp']},
    {'mode': 'silt_strider', 'models': ['siltstrider.nif']},
    {'mode': 'pack_guar', 'models': ['guar_withpack.nif', 'guar_harness.nif']}]}


class VehicleTests(Databases):
    """Tamriel Rebuilt calls every overland operator a Caravaner; the vehicle says what they drive."""

    def world(self, placed):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript("""
          CREATE TABLE objects(version_id,record_type,object_key,editor_id,name,plugin,script_key,model);
          CREATE TABLE profile_objects(profile_id,object_key,version_id);
          CREATE TABLE placements(version_id,reference_key,object_key,source_cell_key,cell_key,plugin,
                                  record_id,payload_offset,payload_length,moved,x,y,z,count_raw,
                                  owner_key,faction_key,details);
          CREATE TABLE profile_placements(profile_id,reference_key,version_id,origin_plugin);""")
        models = {}
        for index, (key, model, cell, x, y) in enumerate(placed, 1):
            if key not in models:
                models[key] = len(models) + 1
                db.execute('INSERT INTO objects VALUES(?,?,?,?,?,?,?,?)',
                           (models[key], 'STAT', key, key, key, 'p', None, model))
                db.execute('INSERT INTO profile_objects VALUES(?,?,?)', ('tr', key, models[key]))
            db.execute('INSERT INTO placements VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (index, f'ref{index}', key, cell, cell, 'p', index, 0, 0, 0, x, y, 0, 1, None, None, None))
            db.execute('INSERT INTO profile_placements VALUES(?,?,?,?)', ('tr', f'ref{index}', index, 'p'))
        db.commit()
        return db

    def modes(self, placed, klass='Caravaner'):
        services = self.services([('op', 'Operator', 'NPC_', TOWN, ['exterior:9,9'])])
        network = build(services, self.game({'op': klass}), 'tr',
                        policy(modes={'byClass': {'Caravaner': 'silt_strider'}, 'byVehicle': VEHICLES}),
                        self.world(placed))
        return network['edges'][0]['mode'], network

    def test_a_sky_lamp_at_the_stop_makes_it_a_sky_lamp(self):
        mode, network = self.modes([('op', None, TOWN, 100, 100),
                                    ('lamp', r'tr\cr\tr_SkyLamp_03.nif', TOWN, 900, 100)])
        self.assertEqual(mode, 'sky_lamp')
        self.assertEqual(network['providers']['op']['vehicle'], r'tr\cr\tr_skylamp_03.nif')
        self.assertEqual(network['verification']['vehicleModes'], {'sky_lamp': 1})

    def test_a_pack_guar_with_no_strider_makes_it_a_caravan(self):
        mode, _ = self.modes([('op', None, TOWN, 0, 0), ('guar', r'r\Guar_withpack.NIF', TOWN, 400, 0)])
        self.assertEqual(mode, 'pack_guar')

    def test_a_strider_port_with_a_guar_beside_it_is_still_a_strider_port(self):
        mode, _ = self.modes([('op', None, TOWN, 0, 0), ('guar', r'r\Guar_withpack.NIF', TOWN, 300, 0),
                              ('strider', r'r\Siltstrider.NIF', TOWN, 600, 0)])
        self.assertEqual(mode, 'silt_strider', 'markers are tried in the order listed')

    def test_a_vehicle_across_the_cell_border_counts(self):
        mode, _ = self.modes([('op', None, 'exterior:-2,-9', -8190, -73700),
                              ('lamp', 'skylamp.nif', 'exterior:-1,-9', -8000, -73700)])
        self.assertEqual(mode, 'sky_lamp')

    def test_a_vehicle_out_of_reach_does_not(self):
        mode, network = self.modes([('op', None, TOWN, 0, 0), ('lamp', 'skylamp.nif', TOWN, 4000, 0)])
        self.assertEqual(mode, 'silt_strider', 'the class mode stands')
        self.assertEqual(network['verification']['operatorsWithoutVehicle'], ['op'])

    def test_other_classes_keep_their_class_mode(self):
        mode, network = self.modes([('op', None, TOWN, 0, 0), ('lamp', 'skylamp.nif', TOWN, 100, 0)],
                                   klass='Shipmaster')
        self.assertIsNone(mode, 'a Shipmaster is not reclassified, and has no mode in this policy')
        self.assertEqual(network['verification']['operatorsWithoutVehicle'], [])

    def test_without_a_world_the_class_decides_as_before(self):
        services = self.services([('op', 'Operator', 'NPC_', TOWN, ['exterior:9,9'])])
        network = build(services, self.game({'op': 'Caravaner'}), 'tr',
                        policy(modes={'byClass': {'Caravaner': 'silt_strider'}, 'byVehicle': VEHICLES}))
        self.assertEqual(network['edges'][0]['mode'], 'silt_strider')


class VehiclePolicyTests(unittest.TestCase):
    def write(self, payload):
        path = Path(scratch_dir())/'travel.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_a_malformed_vehicle_rule_is_refused(self):
        for broken in ({'classes': ['Caravaner'], 'radius': 0, 'markers': VEHICLES['markers']},
                       {'classes': ['Caravaner'], 'radius': 2500, 'markers': []},
                       {'classes': ['Caravaner'], 'radius': 2500, 'markers': [{'mode': 'x', 'models': []}]},
                       {'radius': 2500, 'markers': VEHICLES['markers']}):
            with self.assertRaises(ExportError, msg=repr(broken)):
                load_travel_policy(self.write(policy(modes={'byClass': {}, 'byVehicle': broken})))

    def test_the_shipped_policy_reads_vehicles_for_caravaners(self):
        loaded = load_travel_policy(Path(__file__).parent/'policy/travel.json')
        rule = loaded['modes']['byVehicle']
        self.assertEqual(rule['classes'], ['Caravaner'])
        self.assertEqual([m['mode'] for m in rule['markers']], ['sky_lamp', 'silt_strider', 'pack_guar', 'carriage'])


SETTINGS = {'fTravelMult': 4000.0, 'fTravelTimeMult': 16000.0, 'fMagesGuildTravel': 10.0}


class JourneyTests(unittest.TestCase):
    """TravelWindow::addDestination and onTravelButtonClick, openmw-0.51.0."""

    def test_price_is_the_distance_over_ftravelmult_truncated(self):
        cost = journey([((0, 0, 0), (0, 53999, 0))], False, SETTINGS)
        self.assertEqual(cost['price'], 13, '53999 / 4000 = 13.49..., truncated')
        self.assertEqual(cost['hours'], 3, '53999 / 16000 = 3.37..., truncated')
        self.assertEqual(cost['distance'], 53999)

    def test_price_counts_height_but_time_does_not(self):
        cost = journey([((0, 0, 0), (0, 15999, 16000))], False, SETTINGS)
        self.assertEqual(cost['price'], 5, 'three-dimensional distance 22626')
        self.assertEqual(cost['hours'], 0, 'flat distance 15999 is under an hour')

    def test_a_short_hop_still_costs_one_gold(self):
        self.assertEqual(journey([((0, 0, 0), (10, 0, 0))], False, SETTINGS)['price'], 1)

    def test_a_provider_indoors_charges_the_flat_guild_fee_and_takes_no_time(self):
        cost = journey([((0, 0, 0), (900000, 0, 0))], True, SETTINGS)
        self.assertEqual((cost['price'], cost['hours']), (10, 0))

    def test_a_zero_travel_mult_charges_the_raw_distance_as_the_engine_does(self):
        cost = journey([((0, 0, 0), (250.9, 0, 0))], False, SETTINGS | {'fTravelMult': 0})
        self.assertEqual(cost['price'], 250)

    def test_a_zero_time_mult_does_not_divide_by_zero(self):
        cost = journey([((0, 0, 0), (50000, 0, 0))], False, SETTINGS | {'fTravelTimeMult': 0})
        self.assertEqual(cost['hours'], 0)

    def test_the_shortest_of_several_placements_decides(self):
        cost = journey([((0, 0, 0), (0, 40000, 0)), ((0, 20000, 0), (0, 40000, 0))], False, SETTINGS)
        self.assertEqual((cost['price'], cost['fromPos']), (5, [0, 20000]))

    def test_no_position_or_no_settings_gives_nothing_rather_than_a_guess(self):
        self.assertIsNone(journey([], False, SETTINGS))
        self.assertIsNone(journey(None, False, SETTINGS))
        self.assertIsNone(journey([((0, 0, 0), (1, 1, 1))], False, None))

    def test_a_missing_or_non_numeric_setting_is_refused(self):
        for broken in ({'fTravelMult': 4000.0}, SETTINGS | {'fTravelMult': None},
                       SETTINGS | {'fMagesGuildTravel': True}):
            with self.assertRaises(ExportError, msg=repr(broken)):
                journey([((0, 0, 0), (1, 1, 1))], False, broken)

    def test_the_transcription_is_pinned_to_one_engine_release(self):
        check_travel_transcription({'vanilla': f'OpenMW {TRANSCRIBED_FROM}'})
        with self.assertRaises(ExportError) as caught:
            check_travel_transcription({'vanilla': 'OpenMW 0.52.0'})
        self.assertIn('travelwindow.cpp', str(caught.exception))


class PricedNetworkTests(Databases):
    def network(self, record_type='NPC_', stats=None, reference=None):
        services = self.services([('driver', 'Driver', record_type, TOWN, ['exterior:1,1', 'exterior:2,2'])],
                                 points={'driver': (0, 0, 0), 'exterior:1,1': (0, 8000, 0)},
                                 stats={'driver': stats or {}})
        return build(services, self.game({'driver': 'Caravaner'}), 'tr', policy(),
                     settings=SETTINGS, reference=reference)

    def test_each_edge_carries_its_price_hours_and_both_ends(self):
        edge = next(e for e in self.network()['edges'] if e['to'] == 'exterior:1,1')
        self.assertEqual((edge['price'], edge['hours'], edge['toPos']), (2, 0, [0, 8000]))

    def test_an_edge_with_no_destination_position_is_null_and_listed(self):
        network = self.network()
        edge = next(e for e in network['edges'] if e['to'] == 'exterior:2,2')
        self.assertIsNone(edge['price'])
        self.assertEqual(network['verification']['edgesWithoutPrice'], [edge['key']])

    def test_stored_barter_stats_are_read_from_the_record(self):
        barter = self.network(stats={'skills': {'mercantile': 30}, 'level': 5, 'disposition': 60,
                                     'attributes': {'personality': 40, 'luck': 45}})['providers']['driver']['barter']
        self.assertEqual((barter['mercantile'], barter['statsSource'], barter['disposition']), (30, 'record', 60))
        self.assertTrue(barter['priceable'])

    def test_an_autocalculated_driver_with_nothing_to_derive_from_is_unpriceable(self):
        network = self.network(stats={'level': 5, 'autocalcFlag': True})
        barter = network['providers']['driver']['barter']
        self.assertIsNone(barter['statsSource'])
        self.assertFalse(barter['priceable'])
        self.assertEqual(network['verification']['providersWithoutBarterStats'], ['driver'])

    def test_a_creature_is_priceable_because_it_never_haggles(self):
        barter = self.network(record_type='CREA')['providers']['driver']['barter']
        self.assertFalse(barter['haggles'])
        self.assertTrue(barter['priceable'])

    def test_without_settings_nothing_is_priced(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, ['exterior:1,1'])])
        network = build(services, self.game({'driver': 'Caravaner'}), 'tr', policy())
        self.assertNotIn('price', network['edges'][0])
        self.assertNotIn('barter', network['providers']['driver'])

    def test_the_payload_publishes_the_formula_with_this_profiles_settings(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, ['exterior:1,1'])])
        payload = assemble(services, self.game({'driver': 'Caravaner'}), 'tr', policy(), 'snap',
                           settings=SETTINGS | {'fUnrelated': 1.0})
        self.assertEqual(payload['travelFormula']['settings'], SETTINGS)
        self.assertEqual(payload['travelFormula']['source'], 'authored')
        self.assertEqual(payload['barterFormula']['source'], 'authored')


class TownTests(Databases):
    def towns(self, nodes, cells=(), rule=None):
        services = self.services([], cells=cells)
        table = {key: {'key': key, 'name': name, 'interior': key.startswith('interior:'), 'region': None}
                 for key, name in nodes.items()}
        left = assign_towns(services, 'tr', table, rule or {'radius': 1, 'overrides': {}})
        return table, left

    def test_a_name_splits_into_town_and_district_at_the_first_comma(self):
        self.assertEqual(split_town('Old Ebonheart, Docks'), ('Old Ebonheart', 'Docks'))
        self.assertEqual(split_town("Sadrith Mora, Wolverine Hall: Mage's Guild"),
                         ('Sadrith Mora', "Wolverine Hall: Mage's Guild"))
        self.assertEqual(split_town('Balmora'), ('Balmora', None))
        self.assertEqual(split_town('Balmora,'), ('Balmora', None), 'a trailing comma names no district')

    def test_a_town_s_docks_and_guild_hall_share_the_town(self):
        table, left = self.towns({'exterior:7,-18': 'Old Ebonheart, Docks',
                                  'interior:old ebonheart, guild of mages': 'Old Ebonheart, Guild of Mages'})
        self.assertEqual({n['town'] for n in table.values()}, {'Old Ebonheart'})
        self.assertEqual(table['exterior:7,-18']['district'], 'Docks')
        self.assertEqual(left, [])

    def test_an_unnamed_stop_joins_the_only_town_beside_it(self):
        table, _ = self.towns({'exterior:15,4': None},
                              cells=[('exterior:15,5', 'Tel Aruhn', 0, None, (15, 5)),
                                     ('exterior:17,4', 'Sadrith Mora', 0, None, (17, 4))])
        self.assertEqual((table['exterior:15,4']['town'], table['exterior:15,4']['townRule']),
                         ('Tel Aruhn', 'nearest'), 'Sadrith Mora is two cells off, out of radius 1')

    def test_the_majority_of_the_nearest_cells_wins(self):
        table, _ = self.towns({'exterior:8,-51': None},
                              cells=[('exterior:7,-51', 'Narsis, Old Quarter', 0, None, (7, -51)),
                                     ('exterior:7,-50', 'Narsis, Waterfront', 0, None, (7, -50)),
                                     ('exterior:9,-51', 'Vedas Plantation', 0, None, (9, -51))])
        self.assertEqual(table['exterior:8,-51']['town'], 'Narsis')

    def test_a_tie_joins_no_town_and_is_listed(self):
        table, left = self.towns({'exterior:-3,-14': None},
                                 cells=[('exterior:-4,-14', 'Teyn', 0, None, (-4, -14)),
                                        ('exterior:-2,-14', 'Fort Ancylis', 0, None, (-2, -14))])
        self.assertIsNone(table['exterior:-3,-14']['town'])
        self.assertIsNone(table['exterior:-3,-14']['townRule'])
        self.assertEqual(left, ['exterior:-3,-14'])

    def test_nothing_within_the_radius_joins_nothing(self):
        _, left = self.towns({'exterior:0,0': None},
                             cells=[('exterior:5,5', 'Far Away', 0, None, (5, 5))])
        self.assertEqual(left, ['exterior:0,0'])

    def test_radius_zero_never_guesses(self):
        _, left = self.towns({'exterior:15,4': None},
                             cells=[('exterior:15,5', 'Tel Aruhn', 0, None, (15, 5))],
                             rule={'radius': 0, 'overrides': {}})
        self.assertEqual(left, ['exterior:15,4'])

    def test_an_override_decides_before_the_name_and_keeps_the_district(self):
        table, _ = self.towns({'exterior:1,1': 'Kaushasiralis, Pier', 'exterior:2,2': 'Somewhere'},
                              rule={'radius': 1, 'overrides': {'EXTERIOR:1,1': 'Othrenis',
                                                               'exterior:2,2': None}})
        self.assertEqual((table['exterior:1,1']['town'], table['exterior:1,1']['district'],
                          table['exterior:1,1']['townRule']), ('Othrenis', 'Pier', 'override'))
        self.assertIsNone(table['exterior:2,2']['town'], 'null keeps a stop out of every town')

    def test_the_network_reports_its_towns(self):
        services = self.services([('driver', 'Driver', 'NPC_', TOWN, [GUILD])],
                                 cells=[(TOWN, 'Seyda Neen', 0, None, (-2, -9)),
                                        (GUILD, 'Vivec, Guild of Mages', 1, None, (None, None))])
        network = build(services, self.game({'driver': 'Caravaner'}), 'tr',
                        policy(towns={'radius': 1, 'overrides': {}}))
        self.assertEqual(network['verification']['towns'], 2)
        self.assertEqual(network['nodes'][GUILD]['town'], 'Vivec')


class TownPolicyTests(unittest.TestCase):
    def write(self, payload):
        path = Path(scratch_dir())/'travel.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        return path

    def test_a_malformed_town_rule_is_refused(self):
        for broken in ({'radius': -1, 'overrides': {}}, {'radius': 1.5, 'overrides': {}},
                       {'radius': True, 'overrides': {}}, {'radius': 1},
                       {'radius': 1, 'overrides': {'balmora': 'Balmora'}},
                       {'radius': 1, 'overrides': {'exterior:1,1': ' '}}, 'towns'):
            with self.assertRaises(ExportError, msg=repr(broken)):
                load_travel_policy(self.write(policy(towns=broken)))

    def test_the_shipped_policy_merges_towns_within_one_cell(self):
        loaded = load_travel_policy(Path(__file__).parent/'policy/travel.json')
        self.assertEqual(loaded['towns']['radius'], 1)


if __name__ == '__main__':
    unittest.main()
