import json
import sqlite3
import unittest

from build_merchant_catalog import (BARTER_FORMULA, assemble, barter_stats, build,
                                    service_flags)

FLAGS = [(1, 'weapons', 'trade'), (2, 'armor', 'trade'), (2048, 'spells', 'service'),
         (16384, 'training', 'service')]
STATS = {'gold': 400, 'disposition': 50, 'level': 9, 'fatigue': 200, 'female': False,
         'autocalcFlag': False,
         'skills': {'mercantile': 40}, 'attributes': {'personality': 60, 'luck': 45}}
AUTOCALC = {'gold': 350, 'disposition': 50, 'level': 9, 'fatigue': None, 'female': True,
            'autocalcFlag': True, 'skills': None, 'attributes': None}


class Fixture(unittest.TestCase):
    def services(self, providers):
        """providers: [(actor, name, record_type, services_raw, stats, cell)]"""
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE service_flags(bit,code,kind);
          CREATE TABLE profile_providers(profile_id,actor_key,version_id,origin_plugin);
          CREATE TABLE providers(version_id,actor_key,record_type,name,plugin,script_key,
                                 services_raw,unknown_service_bits,stats_json);
          CREATE TABLE provider_locations(profile_id,reference_key,placement_version_id,
                                          provider_version_id,cell_key,x,y,z);
          CREATE TABLE metadata(key,value);""")
        db.execute("INSERT INTO metadata VALUES('snapshotId','\"snap\"')")
        db.executemany('INSERT INTO service_flags VALUES(?,?,?)', FLAGS)
        for index, (actor, name, kind, raw, stats, cell) in enumerate(providers, 1):
            db.execute('INSERT INTO profile_providers VALUES(?,?,?,?)', ('tr', actor, index, 'p'))
            db.execute('INSERT INTO providers VALUES(?,?,?,?,?,?,?,?,?)',
                       (index, actor, kind, name, 'p', None, raw, 0, json.dumps(stats)))
            if cell:
                db.execute('INSERT INTO provider_locations VALUES(?,?,?,?,?,?,?,?)',
                           ('tr', 'r', 1, index, cell, 0, 0, 0))
        db.commit()
        return db

    def game(self, actors):
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE resolved_records(profile_id,record_type,record_key,origin_plugin_id,winner_id);
          CREATE TABLE record_versions(id,plugin_id,ordinal,file_offset,record_type,record_key,
                                       display_id,deleted,header_unknown,header_flags,payload);""")
        for index, (actor, klass, race) in enumerate(actors, 1):
            payload = b'NAME\x04\x00\x00\x00xxx\x00'
            for tag, value in ((b'CNAM', klass), (b'RNAM', race)):
                if value is not None:
                    body = value.encode('cp1252')+b'\x00'
                    payload += tag+len(body).to_bytes(4, 'little')+body
            db.execute('INSERT INTO record_versions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (index, 1, 0, 0, 'NPC_', actor, actor, 0, 0, 0, payload))
            db.execute('INSERT INTO resolved_records VALUES(?,?,?,?,?)',
                       ('tr', 'NPC_', actor, 1, index))
        db.commit()
        return db

    def one(self, actor='m', name='Merchant', kind='NPC_', raw=1, stats=None, cell='interior:shop',
            actors=(('m', 'Trader Service', 'Dark Elf'),)):
        records = build(self.services([(actor, name, kind, raw, stats or STATS, cell)]),
                        self.game(actors), 'tr')
        return records[0]


class StatTests(Fixture):
    def test_a_stored_merchant_publishes_its_barter_stats(self):
        record = self.one()
        self.assertEqual((record['mercantile'], record['personality'], record['luck']),
                         (40, 60, 45))
        self.assertTrue(record['priceable'])
        self.assertFalse(record['autocalc'])

    def test_an_autocalculated_merchant_publishes_nulls_not_zeros(self):
        # Treating these as 0 would make every such merchant look maximally generous.
        record = self.one(stats=AUTOCALC)
        self.assertIsNone(record['mercantile'])
        self.assertIsNone(record['personality'])
        self.assertIsNone(record['luck'])
        self.assertTrue(record['autocalc'])
        self.assertFalse(record['priceable'])

    def test_null_skill_and_attribute_blocks_are_survived(self):
        self.assertEqual(barter_stats({'skills': None, 'attributes': None}),
                         {'mercantile': None, 'personality': None, 'luck': None})

    def test_gold_and_disposition_are_published_for_pricing(self):
        record = self.one()
        self.assertEqual(record['gold'], 400)
        self.assertEqual(record['disposition'], 50)

    def test_class_and_race_come_from_the_record_not_the_provider_table(self):
        record = self.one()
        self.assertEqual(record['class'], 'Trader Service')
        self.assertEqual(record['race'], 'Dark Elf')

    def test_an_actor_missing_from_the_records_leaves_class_null(self):
        record = self.one(actors=())
        self.assertIsNone(record['class'])
        self.assertIsNone(record['race'])


class CreatureTests(Fixture):
    def test_a_creature_does_not_haggle(self):
        # getBarterOffer returns basePrice unchanged for a creature, before it reads
        # any stat. Mudcrab and Creeper sell at face value.
        record = self.one(kind='CREA', stats=AUTOCALC)
        self.assertFalse(record['haggles'])

    def test_a_creature_is_priceable_without_any_stats(self):
        record = self.one(kind='CREA', stats=AUTOCALC)
        self.assertTrue(record['priceable'],
                        'its price is exactly the base value, which is knowable')

    def test_an_npc_still_needs_stats_to_be_priceable(self):
        record = self.one(kind='NPC_', stats=AUTOCALC)
        self.assertTrue(record['haggles'])
        self.assertFalse(record['priceable'])


class DerivationTests(Fixture):
    """An auto-calculated merchant gets its stats by rerunning the engine's own routines."""
    def reference(self):
        return {'races': {'imperial': {
                    'attributes': {'personality': {'male': 50, 'female': 50},
                                   'luck': {'male': 40, 'female': 40}},
                    'skillBonuses': [{'skill': 'mercantile', 'bonus': 10}]}},
                'classes': {'trader': {'specialization': 'stealth',
                                       'favoredAttributes': ['personality'],
                                       'majorSkills': ['mercantile'], 'minorSkills': []}},
                'skills': [{'skill': 'mercantile', 'governingAttribute': 'personality',
                            'specialization': 'stealth'}]}

    def test_without_a_reference_nothing_is_derived(self):
        record = self.one(stats=AUTOCALC, actors=(('m', 'Trader', 'Imperial'),))
        self.assertIsNone(record['mercantile'])
        self.assertIsNone(record['statsSource'])
        self.assertFalse(record['priceable'])

    def test_with_a_reference_the_stats_are_worked_out(self):
        records = build(self.services([('m', 'M', 'NPC_', 1, AUTOCALC, 'interior:shop')]),
                        self.game([('m', 'Trader', 'Imperial')]), 'tr', self.reference())
        record = records[0]
        self.assertEqual(record['statsSource'], 'derived')
        self.assertEqual(record['mercantile'], 57)  # level 9 major specialised skill
        self.assertTrue(record['priceable'])
        self.assertTrue(record['autocalc'], 'still flagged as auto-calculated')

    def test_a_stored_merchant_is_never_overwritten_by_derivation(self):
        records = build(self.services([('m', 'M', 'NPC_', 1, STATS, 'interior:shop')]),
                        self.game([('m', 'Trader', 'Imperial')]), 'tr', self.reference())
        self.assertEqual(records[0]['statsSource'], 'record')
        self.assertEqual(records[0]['mercantile'], 40, 'the record wins')

    def test_a_class_the_catalogs_do_not_carry_stays_unknown(self):
        records = build(self.services([('m', 'M', 'NPC_', 1, AUTOCALC, 'interior:shop')]),
                        self.game([('m', 'T_Glb_Jeweler', 'Imperial')]), 'tr', self.reference())
        self.assertIsNone(records[0]['statsSource'])
        self.assertIsNone(records[0]['mercantile'])
        self.assertFalse(records[0]['priceable'])

    def test_the_counts_separate_read_from_derived(self):
        db = self.services([('a', 'A', 'NPC_', 1, STATS, 'interior:shop'),
                            ('b', 'B', 'NPC_', 1, AUTOCALC, 'interior:shop')])
        payload = assemble(db, self.game([('a', 'Trader', 'Imperial'),
                                          ('b', 'Trader', 'Imperial')]),
                           'tr', 'snap', self.reference())
        counts = payload['derivation']
        self.assertEqual(counts['statsFromRecord'], 1)
        self.assertEqual(counts['statsDerived'], 1)
        self.assertEqual(counts['statsUnknown'], 0)


class ServiceTests(Fixture):
    def test_a_trade_flag_makes_a_trader(self):
        self.assertTrue(self.one(raw=1)['trades'])

    def test_a_service_only_provider_is_not_a_trader(self):
        # A spellmaker sells no goods, so barter gold and Mercantile do not apply.
        self.assertFalse(self.one(raw=2048)['trades'])

    def test_several_flags_are_kept_as_the_raw_bitfield(self):
        record = self.one(raw=1 | 2 | 16384)
        self.assertEqual(record['servicesRaw'], 1 | 2 | 16384)
        self.assertTrue(record['trades'])

    def test_the_flag_table_is_read_from_the_database(self):
        flags = service_flags(self.services([]))
        self.assertEqual(flags[2048], ('spells', 'service'))


class PayloadTests(Fixture):
    def test_the_flag_table_is_carried_once_rather_than_per_record(self):
        db = self.services([('a', 'A', 'NPC_', 1, STATS, 'interior:shop'),
                            ('b', 'B', 'NPC_', 2, STATS, 'interior:shop')])
        payload = assemble(db, self.game([('a', 'Trader', 'Nord'), ('b', 'Trader', 'Nord')]),
                           'tr', 'snap')
        self.assertEqual(len(payload['serviceFlags']), len(FLAGS))
        self.assertNotIn('services', payload['records'][0])

    def test_the_counts_separate_autocalc_from_creatures(self):
        db = self.services([('npc', 'N', 'NPC_', 1, STATS, 'interior:shop'),
                            ('auto', 'A', 'NPC_', 1, AUTOCALC, 'interior:shop'),
                            ('crab', 'C', 'CREA', 1, AUTOCALC, 'exterior:1,1')])
        payload = assemble(db, self.game([('npc', 'Trader', 'Nord')]), 'tr', 'snap')
        counts = payload['derivation']
        self.assertEqual(counts['traders'], 3)
        self.assertEqual(counts['autocalc'], 2, 'the creature is auto-calculated too')
        self.assertEqual(counts['creatures'], 1)
        self.assertEqual(counts['priceable'], 2, 'the stored NPC and the creature')

    def test_every_record_has_the_key_the_bundle_joins_on(self):
        db = self.services([('m', 'M', 'NPC_', 1, STATS, 'interior:shop')])
        payload = assemble(db, self.game([('m', 'Trader', 'Nord')]), 'tr', 'snap')
        self.assertTrue(all(isinstance(r.get('key'), str) and r['key']
                            for r in payload['records']))
        self.assertEqual(payload['snapshotId'], 'snap')


class FormulaTests(unittest.TestCase):
    """The formula is transcribed from the engine, so pin what it says."""
    def test_the_weights_are_the_engine_s_own(self):
        self.assertEqual(BARTER_FORMULA['luckWeight'], 0.1)
        self.assertEqual(BARTER_FORMULA['luckCap'], 10.0)
        self.assertEqual(BARTER_FORMULA['personalityWeight'], 0.2)
        self.assertEqual(BARTER_FORMULA['personalityCap'], 10.0)
        self.assertEqual(BARTER_FORMULA['mercantileCap'], 100.0)

    def test_the_two_cases_that_never_reach_the_arithmetic_are_recorded(self):
        self.assertTrue(BARTER_FORMULA['creaturesDoNotHaggle'])
        self.assertTrue(BARTER_FORMULA['zeroBasePriceStaysZero'])

    def test_it_names_the_settings_it_needs_rather_than_copying_them(self):
        self.assertIn('fFatigueBase', BARTER_FORMULA['gameSettings'])
        self.assertIn('fFatigueMult', BARTER_FORMULA['gameSettings'])
        self.assertEqual(BARTER_FORMULA['source'], 'authored')


if __name__ == '__main__':
    unittest.main()
