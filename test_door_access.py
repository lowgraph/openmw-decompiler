import json
import sqlite3
import struct
import unittest

from door_access import DoorAccess, door_access, parse_pathgrid

BANK = 'interior:bank'
VAULT = 'interior:bank: vault'


def subrecord(tag, body):
    return tag.encode('latin1') + struct.pack('<I', len(body)) + body


def pathgrid(name, points, links, grid=(0, 0)):
    """A PGRD record as the game stores it: points with connection counts, then targets."""
    neighbours = {i: sorted({b for a, b in links if a == i} | {a for a, b in links if b == i})
                  for i in range(len(points))}
    body = b''.join(struct.pack('<iiiBBh', x, y, z, 0, len(neighbours[i]), 0)
                    for i, (x, y, z) in enumerate(points))
    targets = b''.join(struct.pack('<i', t) for i in range(len(points)) for t in neighbours[i])
    return (subrecord('DATA', struct.pack('<iiHH', *grid, 128, len(points)))
            + subrecord('NAME', name.encode('cp1252') + b'\x00')
            + subrecord('PGRP', body) + subrecord('PGRC', targets))


def door(cell, at, lock=0, leads=None, arrival=None):
    return {'cell': cell, 'at': at, 'lock': lock, 'leads': leads, 'arrival': arrival}


# A bank: a hall from the street door (0,0) to a teller (0,800), and past a jail door
# at (0,1200) a vault at (0,1600). A storeroom off the hall has no pathgrid at all.
HALL = [(0, 0, 0), (0, 400, 0), (0, 800, 0), (0, 1600, 0)]
HALL_LINKS = {(0, 1), (1, 2), (2, 3)}


class PathgridTests(unittest.TestCase):
    def test_a_record_round_trips(self):
        name, grid, points, links = parse_pathgrid(pathgrid('Bank', HALL, HALL_LINKS))
        self.assertEqual((name, grid, points, links), ('Bank', (0, 0), HALL, HALL_LINKS))

    def test_connections_are_read_in_point_order(self):
        _, _, _, links = parse_pathgrid(pathgrid('X', [(0, 0, 0), (1, 0, 0), (2, 0, 0)], {(0, 2), (1, 2)}))
        self.assertEqual(links, {(0, 2), (1, 2)})

    def test_a_truncated_record_does_not_crash(self):
        record = pathgrid('Bank', HALL, HALL_LINKS)
        name, _, points, _ = parse_pathgrid(record[:-3])
        self.assertEqual(name, 'Bank')
        self.assertEqual(points, HALL)


class AccessTests(unittest.TestCase):
    def access(self, doors):
        return DoorAccess({BANK: (HALL, HALL_LINKS)}, doors)

    def street(self, lock=0):
        return door('exterior:0,0', (100, 100, 0), lock, BANK, (0, 0, 0))

    def test_the_open_part_of_a_room_needs_no_lock(self):
        access = self.access([self.street(), door(BANK, (0, 1200, 0), lock=100)])
        self.assertEqual(access.lock_to_reach(BANK, (10, 790, 0)), 0)

    def test_a_vault_past_a_locked_inner_door_needs_that_lock(self):
        access = self.access([self.street(), door(BANK, (0, 1200, 0), lock=100)])
        self.assertEqual(access.lock_to_reach(BANK, (0, 1590, 0)), 100)

    def test_a_locked_street_door_locks_the_whole_room(self):
        access = self.access([self.street(lock=30), door(BANK, (0, 1200, 0), lock=100)])
        self.assertEqual(access.lock_to_reach(BANK, (10, 790, 0)), 30)
        self.assertEqual(access.lock_to_reach(BANK, (0, 1590, 0)), 100, 'the harder door decides')

    def test_the_easier_of_two_ways_in_decides(self):
        side = door('exterior:0,0', (0, 2000, 0), 0, BANK, (0, 1600, 0))
        access = self.access([self.street(), door(BANK, (0, 1200, 0), lock=100), side])
        self.assertEqual(access.lock_to_reach(BANK, (0, 1590, 0)), 0, 'an open back door into the vault')

    def test_a_door_on_another_floor_blocks_nothing(self):
        access = self.access([self.street(), door(BANK, (0, 1200, 900), lock=100)])
        self.assertEqual(access.lock_to_reach(BANK, (0, 1590, 0)), 0)

    def test_a_storeroom_with_no_pathgrid_behind_a_locked_door(self):
        # A room off the hall at x=600 behind a door at (300, 800); no point enters it.
        access = self.access([self.street(), door(BANK, (300, 800, 0), lock=60)])
        self.assertEqual(access.lock_to_reach(BANK, (600, 820, 30)), 60)
        self.assertEqual(access.lock_to_reach(BANK, (120, 800, 0)), 0, 'beside the hall, not inside the room')
        self.assertEqual(access.lock_to_reach(BANK, (600, 820, 700)), 0, 'a floor above is not that room')

    def test_nested_cells_carry_the_lock_through(self):
        vault = ([(0, 0, 0), (0, 300, 0)], {(0, 1)})
        doors = [self.street(), door(BANK, (0, 800, 0), lock=0, leads=VAULT, arrival=(0, 0, 0)),
                 door(VAULT, (0, 150, 0), lock=50)]
        access = DoorAccess({BANK: (HALL, HALL_LINKS), VAULT: vault}, doors)
        self.assertEqual(access.lock_to_reach(VAULT, (0, 10, 0)), 0)
        self.assertEqual(access.lock_to_reach(VAULT, (0, 290, 0)), 50)

    def test_a_place_no_door_leads_to_is_unknown_not_locked(self):
        access = self.access([door(BANK, (0, 1200, 0), lock=100)])
        self.assertIsNone(access.lock_to_reach(BANK, (0, 0, 0)), 'Mournhold is reached by teleport')
        self.assertIsNone(access.lock_to_reach('interior:elsewhere', (0, 0, 0)))

    def test_the_outside_is_open(self):
        self.assertEqual(self.access([]).lock_to_reach('exterior:5,5', (1, 2, 3)), 0)

    def test_a_room_without_a_pathgrid_is_one_room(self):
        access = DoorAccess({}, [door('exterior:0,0', (0, 0, 0), 25, 'interior:hut', (0, 0, 0))])
        self.assertEqual(access.lock_to_reach('interior:hut', (400, 400, 0)), 25)


class DatabaseTests(unittest.TestCase):
    """door_access reads doors from the world catalog and pathgrids from the foundation."""

    def test_it_reads_both_databases_and_picks_the_winning_pathgrid(self):
        world = sqlite3.connect(':memory:')
        self.addCleanup(world.close)
        world.executescript('''
          CREATE TABLE cells(profile_id,cell_key,name,interior);
          CREATE TABLE objects(version_id,record_type,object_key);
          CREATE TABLE profile_objects(profile_id,object_key,version_id);
          CREATE TABLE placements(version_id,reference_key,object_key,cell_key,x,y,z,details);
          CREATE TABLE profile_placements(profile_id,reference_key,version_id);''')
        world.execute("INSERT INTO cells VALUES('p',?, 'Bank', 1)", (BANK,))
        world.execute("INSERT INTO objects VALUES(1,'DOOR','door')")
        world.execute("INSERT INTO profile_objects VALUES('p','door',1)")
        street = {'lockLevelRaw': 0, 'doorDestination': {'cellName': 'BANK', 'position': [0, 0, 0]}}
        jail = {'lockLevelRaw': 100, 'doorDestination': None}
        for n, (cell, at, details) in enumerate([('exterior:0,0', (100, 100, 0), street),
                                                (BANK, (0, 1200, 0), jail)], 1):
            world.execute('INSERT INTO placements VALUES(?,?,?,?,?,?,?,?)',
                          (n, f'r{n}', 'door', cell, *at, json.dumps(details)))
            world.execute("INSERT INTO profile_placements VALUES('p',?,?)", (f'r{n}', n))
        game = sqlite3.connect(':memory:')
        self.addCleanup(game.close)
        game.executescript('CREATE TABLE profile_plugins(profile_id,plugin_id,load_order);'
                           'CREATE TABLE record_versions(plugin_id,record_type,payload);')
        game.executemany('INSERT INTO profile_plugins VALUES(?,?,?)', [('p', 1, 0), ('p', 2, 1)])
        # The master has no vault on its pathgrid; the later plugin adds it.
        game.execute("INSERT INTO record_versions VALUES(1,'PGRD',?)", (pathgrid('Bank', HALL[:3], {(0, 1), (1, 2)}),))
        game.execute("INSERT INTO record_versions VALUES(2,'PGRD',?)", (pathgrid('Bank', HALL, HALL_LINKS),))
        game.execute("INSERT INTO record_versions VALUES(3,'PGRD',?)", (pathgrid('Bank', [(0, 0, 0)], set()),))
        access = door_access(world, game, 'p')
        self.assertEqual(len(access.pathgrids[BANK][0]), 4, 'the later plugin wins; plugin 3 is not in the profile')
        self.assertEqual(access.lock_to_reach(BANK, (0, 790, 0)), 0)
        self.assertEqual(access.lock_to_reach(BANK, (0, 1590, 0)), 100)


if __name__ == '__main__':
    unittest.main()
