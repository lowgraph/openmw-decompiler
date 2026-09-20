import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from build_faction_catalog import (FADT_SIZE, RANKS, assemble, build, named, parse,
                                   reference)
from export_items import ExportError

REFERENCE = {'attributes': {0: 'strength', 1: 'intelligence', 2: 'willpower',
                            3: 'agility', 5: 'endurance', 6: 'personality'},
             'skills': {0: 'block', 5: 'conjuration', 10: 'destruction', 26: 'hand_to_hand'}}


def fadt(attributes=(1, 2), ranks=None, skills=(10, 5), flags=0):
    """A FADT subrecord body: 2 attributes, 10 ranks of 5, 7 skills, flags."""
    values = list(attributes)
    ranks = ranks or [(30, 30, 0, 0, 0)] * RANKS
    for row in ranks:
        values += list(row)
    padded = list(skills) + [-1] * (7 - len(skills))
    values += padded
    values.append(flags)
    return struct.pack(f'<{len(values)}i', *values)


def record(name='Mages Guild', rank_names=('Associate', 'Apprentice'), **kwargs):
    body = b''
    for tag, payload in [(b'NAME', name.encode('cp1252')+b'\0'),
                         (b'FNAM', name.encode('cp1252')+b'\0')]:
        body += tag + struct.pack('<I', len(payload)) + payload
    for rank in rank_names:
        padded = rank.encode('cp1252').ljust(32, b'\0')
        body += b'RNAM' + struct.pack('<I', 32) + padded
    data = fadt(**kwargs)
    body += b'FADT' + struct.pack('<I', len(data)) + data
    return body


def with_reactions(pairs, **kwargs):
    body = record(**kwargs)
    for faction, value in pairs:
        raw = faction.encode('cp1252')
        body += b'ANAM' + struct.pack('<I', len(raw)) + raw
        body += b'INTV' + struct.pack('<I', 4) + struct.pack('<i', value)
    return body


class ParseTests(unittest.TestCase):
    def test_the_name_and_named_ranks_are_read(self):
        parsed = parse(record(), 'cp1252', REFERENCE)
        self.assertEqual(parsed['name'], 'Mages Guild')
        self.assertEqual([r['name'] for r in parsed['ranks']], ['Associate', 'Apprentice'])
        self.assertEqual(parsed['rankCount'], 2)

    def test_unnamed_rank_slots_are_padding_not_ranks(self):
        # The record always reserves ten; a faction with two ranks has two.
        self.assertEqual(len(parse(record(), 'cp1252', REFERENCE)['ranks']), 2)

    def test_a_faction_with_no_named_ranks_cannot_be_joined(self):
        # Sixth House, Skaal, Talos Cult and the Hands of Almalexia are like this.
        parsed = parse(record(rank_names=()), 'cp1252', REFERENCE)
        self.assertEqual(parsed['ranks'], [])
        self.assertEqual(parsed['rankCount'], 0)

    def test_attributes_and_skills_resolve_from_their_indices(self):
        parsed = parse(record(attributes=(1, 2), skills=(10, 5)), 'cp1252', REFERENCE)
        self.assertEqual(parsed['favouredAttributes'], ['intelligence', 'willpower'])
        self.assertEqual(parsed['skills'], ['destruction', 'conjuration'])

    def test_unused_skill_slots_are_dropped_rather_than_published_as_minus_one(self):
        parsed = parse(record(skills=(0,)), 'cp1252', REFERENCE)
        self.assertEqual(parsed['skills'], ['block'])

    def test_rank_requirements_keep_their_five_numbers(self):
        ranks = [(30, 40, 50, 10, 20)] + [(0, 0, 0, 0, 0)] * (RANKS - 1)
        parsed = parse(record(rank_names=('Associate',), ranks=ranks), 'cp1252', REFERENCE)
        first = parsed['ranks'][0]
        self.assertEqual((first['attribute1'], first['attribute2']), (30, 40))
        self.assertEqual((first['primarySkill'], first['favouredSkill']), (50, 10))
        self.assertEqual(first['reputation'], 20)

    def test_the_hidden_flag_is_read(self):
        self.assertTrue(parse(record(flags=1), 'cp1252', REFERENCE)['hidden'])
        self.assertFalse(parse(record(flags=0), 'cp1252', REFERENCE)['hidden'])

    def test_reactions_pair_each_name_with_the_number_that_follows(self):
        parsed = parse(with_reactions([('Camonna Tong', -3), ('Blades', 1)]),
                       'cp1252', REFERENCE)
        self.assertEqual(parsed['reactions'],
                         [{'faction': 'blades', 'adjustment': 1},
                          {'faction': 'camonna tong', 'adjustment': -3}])

    def test_a_record_with_no_requirements_block_is_refused(self):
        with self.assertRaises(ExportError) as caught:
            parse(b'NAME' + struct.pack('<I', 4) + b'abc\0', 'cp1252', REFERENCE)
        self.assertIn('FADT', str(caught.exception))

    def test_a_requirements_block_of_the_wrong_size_is_refused(self):
        body = b'FADT' + struct.pack('<I', 8) + b'\0'*8
        with self.assertRaises(ExportError) as caught:
            parse(body, 'cp1252', REFERENCE)
        self.assertIn(str(FADT_SIZE), str(caught.exception))

    def test_an_unused_index_resolves_to_nothing(self):
        self.assertIsNone(named(-1, REFERENCE['attributes']))
        self.assertIsNone(named(None, REFERENCE['attributes']))


class Databases(unittest.TestCase):
    def game(self, factions):
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE resolved_records(profile_id,record_type,record_key,origin_plugin_id,winner_id);
          CREATE TABLE record_versions(id,plugin_id,ordinal,file_offset,record_type,record_key,
                                       display_id,deleted,header_unknown,header_flags,payload);""")
        for index, (key, payload) in enumerate(factions, 1):
            db.execute('INSERT INTO record_versions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (index, 1, 0, 0, 'FACT', key, key, 0, 0, 0, payload))
            db.execute('INSERT INTO resolved_records VALUES(?,?,?,?,?)',
                       ('tr', 'FACT', key, 1, index))
        db.commit()
        return db

    def world(self, owned):
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE placements(version_id,faction_key);
          CREATE TABLE profile_placements(profile_id,reference_key,version_id,origin_plugin);
          CREATE TABLE metadata(key,value);""")
        db.execute("INSERT INTO metadata VALUES('snapshotId','\"snap\"')")
        for index, (faction, count) in enumerate(owned.items(), 1):
            for n in range(count):
                version = index*1000 + n
                db.execute('INSERT INTO placements VALUES(?,?)', (version, faction))
                db.execute('INSERT INTO profile_placements VALUES(?,?,?,?)',
                           ('tr', f'r{version}', version, 'p'))
        db.commit()
        return db


class BuildTests(Databases):
    def test_owned_placements_are_counted_onto_the_faction(self):
        records, missing = build(self.game([('Mages Guild', record())]),
                                 self.world({'mages guild': 3}), 'tr', REFERENCE)
        self.assertEqual(records[0]['ownedPlacements'], 3)
        self.assertEqual(missing, [])

    def test_a_faction_owning_nothing_reports_zero_rather_than_absent(self):
        records, _ = build(self.game([('Mages Guild', record())]), self.world({}), 'tr',
                           REFERENCE)
        self.assertEqual(records[0]['ownedPlacements'], 0)

    def test_an_owner_with_no_record_fails_the_build(self):
        # The world and the foundation would then disagree about what exists.
        with self.assertRaises(ExportError) as caught:
            assemble(self.game([('Mages Guild', record())]),
                     self.world({'mages guild': 1, 'ghost guild': 2}), 'tr', REFERENCE, 'snap')
        self.assertIn('ghost guild', str(caught.exception))

    def test_the_payload_counts_what_a_reviewer_needs(self):
        payload = assemble(
            self.game([('Mages Guild', record()),
                       ('Sixth House', record(name='Sixth House', rank_names=(), flags=1))]),
            self.world({'mages guild': 2}), 'tr', REFERENCE, 'snap')
        counts = payload['derivation']
        self.assertEqual(counts['factions'], 2)
        self.assertEqual(counts['joinable'], 1)
        self.assertEqual(counts['hidden'], 1)
        self.assertEqual(counts['owningPlacements'], 1)

    def test_every_record_has_the_key_the_bundle_joins_on(self):
        payload = assemble(self.game([('Mages Guild', record())]), self.world({}), 'tr',
                           REFERENCE, 'snap')
        self.assertTrue(all(isinstance(r.get('key'), str) and r['key']
                            for r in payload['records']))
        self.assertEqual(payload['snapshotId'], 'snap')


class ReferenceTests(unittest.TestCase):
    def test_a_missing_catalog_fails_loudly(self):
        with self.assertRaises(ExportError) as caught:
            reference(Path(tempfile.mkdtemp()), 'vanilla')
        self.assertIn('factions', str(caught.exception))

    def test_indices_are_keyed_as_integers(self):
        root = Path(tempfile.mkdtemp())
        (root/'vanilla').mkdir()
        (root/'vanilla'/'Attributes.json').write_text(json.dumps(
            {'records': [{'index': 0, 'id': 'strength'}]}), encoding='utf-8')
        (root/'vanilla'/'Skills.json').write_text(json.dumps(
            {'records': [{'key': '5', 'skill': 'conjuration'}]}), encoding='utf-8')
        loaded = reference(root, 'vanilla')
        self.assertEqual(loaded['attributes'][0], 'strength')
        self.assertEqual(loaded['skills'][5], 'conjuration')


if __name__ == '__main__':
    unittest.main()
