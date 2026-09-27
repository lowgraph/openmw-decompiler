import sqlite3
import struct
import unittest

from build_access_catalog import (LAND_SIZE, access, assemble, exits_of, heights, land_mask,
                                  subrecord)
from export_items import ExportError


def vhgt(offset=0.0, first_column=(), rest=0):
    """A VHGT body: each row starts from the previous row's first vertex, as the engine reads it."""
    deltas = [0] * (LAND_SIZE * LAND_SIZE)
    for y, delta in enumerate(first_column):
        deltas[y * LAND_SIZE] = delta
    if rest:
        for y in range(LAND_SIZE):
            for x in range(1, LAND_SIZE):
                deltas[y * LAND_SIZE + x] = rest
    return struct.pack('<f', offset) + struct.pack(f'<{len(deltas)}b', *deltas) + b'\x00' * 3


class HeightTests(unittest.TestCase):
    """ESM::Land::loadData, components/esm3/loadland.cpp."""

    def test_heights_accumulate_down_the_first_column_then_along_each_row(self):
        grid = heights(vhgt(offset=1.0, first_column=[2, 3], rest=1))
        self.assertEqual(grid[0], (1 + 2) * 8, 'the first vertex adds its delta to the offset')
        self.assertEqual(grid[1], (1 + 2 + 1) * 8)
        self.assertEqual(grid[LAND_SIZE], (1 + 2 + 3) * 8, 'the next row starts from the one before')
        self.assertEqual(grid[LAND_SIZE * LAND_SIZE - 1], (1 + 2 + 3 + 64) * 8)

    def test_a_short_body_is_no_heights(self):
        self.assertIsNone(heights(b'\x00' * 10))

    def test_subrecords_are_found_by_tag(self):
        payload = b'DATA' + (4).to_bytes(4, 'little') + b'abcd' + b'VHGT' + (2).to_bytes(4, 'little') + b'xy'
        self.assertEqual(subrecord(payload, b'VHGT'), b'xy')
        self.assertIsNone(subrecord(payload, b'WNAM'))


class MaskTests(unittest.TestCase):
    def test_all_land_and_all_sea(self):
        self.assertEqual(land_mask([10.0] * LAND_SIZE ** 2), 'f' * 16)
        self.assertIsNone(land_mask([-100.0] * LAND_SIZE ** 2), 'nothing above the water line')

    def test_the_water_line_itself_is_water(self):
        self.assertIsNone(land_mask([0.0] * LAND_SIZE ** 2))

    def test_one_high_vertex_makes_its_blocks_land(self):
        grid = [-100.0] * LAND_SIZE ** 2
        grid[0] = 50.0  # the south-west corner vertex
        self.assertEqual(land_mask(grid), f'{1:016x}', 'only block (0, 0)')
        grid = [-100.0] * LAND_SIZE ** 2
        grid[8] = 50.0  # on the border of blocks (0, 0) and (1, 0)
        self.assertEqual(land_mask(grid), f'{0b11:016x}', 'a shared edge counts for both')

    def test_the_north_east_block_is_the_top_bit(self):
        grid = [-100.0] * LAND_SIZE ** 2
        grid[-1] = 50.0
        self.assertEqual(land_mask(grid), f'{1 << 63:016x}')


def doors(**links):
    return {origin.replace('_', ' '): targets for origin, targets in links.items()}


class AccessTests(unittest.TestCase):
    def test_a_room_with_a_door_outdoors_is_depth_zero_with_its_exits(self):
        d = {'interior:shack': [('exterior:1,1', 9000.4, 9100.6)]}
        self.assertEqual(access(['interior:shack'], d), [{'key': 'interior:shack', 'depth': 0, 'exits': [[9000, 9101]]}])

    def test_deeper_rooms_point_to_the_room_nearer_the_outside(self):
        d = {'interior:tomb': [('exterior:1,1', 100, 100), ('interior:tomb, crypt', 0, 0)],
             'interior:tomb, crypt': [('interior:tomb', 0, 0), ('interior:tomb, vault', 0, 0)],
             'interior:tomb, vault': [('interior:tomb, crypt', 0, 0)]}
        records = {r['key']: r for r in access(sorted(d), d)}
        self.assertEqual((records['interior:tomb, vault']['depth'], records['interior:tomb, vault']['via']),
                         (2, 'interior:tomb, crypt'))
        self.assertEqual(records['interior:tomb, vault']['exits'], [[100, 100]], 'the exits of the room the chain ends in')
        self.assertNotIn('via', records['interior:tomb'])

    def test_the_shorter_chain_wins_whatever_the_order(self):
        d = {'interior:a': [('interior:long1', 0, 0), ('interior:short', 0, 0)],
             'interior:long1': [('interior:a', 0, 0), ('interior:long2', 0, 0)],
             'interior:long2': [('interior:long1', 0, 0), ('exterior:0,0', 1, 1)],
             'interior:short': [('interior:a', 0, 0), ('exterior:5,5', 2, 2)]}
        records = {r['key']: r for r in access(sorted(d), d)}
        self.assertEqual((records['interior:a']['depth'], records['interior:a']['via']), (1, 'interior:short'))

    def test_a_sealed_room_has_no_depth_and_no_exits(self):
        d = {'interior:vault': [('interior:annex', 0, 0)], 'interior:annex': [('interior:vault', 0, 0)]}
        records = access(['interior:annex', 'interior:vault'], d)
        self.assertEqual([r['depth'] for r in records], [None, None])
        self.assertTrue(all(r['exits'] == [] and 'via' not in r for r in records))

    def test_a_room_only_entered_one_way_still_counts_the_door_that_leads_out(self):
        d = {'interior:cellar': [('interior:house', 0, 0)], 'interior:house': [('exterior:0,0', 5, 5)]}
        records = {r['key']: r for r in access(sorted(d), d)}
        self.assertEqual(records['interior:cellar']['via'], 'interior:house')

    def test_exits_close_together_count_once_and_are_capped(self):
        many = [('exterior:0,0', x * 1000, 0) for x in range(6)] + [('exterior:0,0', 10, 10)]
        self.assertEqual(len(exits_of('interior:hall', {'interior:hall': many})), 4)
        self.assertEqual(exits_of('interior:hall', {'interior:hall': [('exterior:0,0', 10, 10), ('exterior:0,0', 20, 20)]}),
                         [[10, 10]], 'within 256 units is the same exit')
        self.assertEqual(exits_of('interior:hall', {'interior:hall': [('exterior:0,0', None, 5)]}), [])


class Databases(unittest.TestCase):
    def dbs(self, interiors, land=()):
        services = sqlite3.connect(':memory:')
        game = sqlite3.connect(':memory:')
        self.addCleanup(services.close)
        self.addCleanup(game.close)
        services.executescript("""
          CREATE TABLE cells(profile_id,cell_key,name,interior,grid_x,grid_y,region_key,synthetic);
          CREATE TABLE door_links(placement_version_id,reference_key,door_key,plugin,from_cell_key,
                                  cell_name,x,y,z,rx,ry,rz,source_x,source_y,source_z,details_json);
          CREATE TABLE profile_door_links(profile_id,placement_version_id,to_cell_key,status);""")
        for key in interiors:
            services.execute('INSERT INTO cells VALUES(?,?,?,?,?,?,?,?)', ('vanilla', key, key, 1, None, None, None, 0))
        game.executescript("""
          CREATE TABLE resolved_records(profile_id,record_type,record_key,origin_plugin_id,winner_id);
          CREATE TABLE record_versions(id,plugin_id,ordinal,file_offset,record_type,record_key,
                                       display_id,deleted,header_unknown,header_flags,payload);""")
        for index, (key, body, deleted) in enumerate(land, 1):
            payload = b'VHGT' + len(body).to_bytes(4, 'little') + body
            game.execute('INSERT INTO record_versions VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                         (index, 1, 0, 0, 'LAND', key, key, deleted, 0, 0, payload))
            game.execute('INSERT INTO resolved_records VALUES(?,?,?,?,?)', ('vanilla', 'LAND', key, 1, index))
        return services, game

    def test_the_payload_carries_land_and_every_interior(self):
        services, game = self.dbs(['interior:shack'], land=[('exterior:0,0', vhgt(offset=10.0), 0),
                                                             ('exterior:1,0', vhgt(offset=-50.0), 0),
                                                             ('exterior:2,0', vhgt(offset=10.0), 1)])
        payload = assemble(services, game, 'vanilla', 'snap')
        self.assertEqual(payload['land'], {'exterior:0,0': 'f' * 16}, 'sea and deleted land are left out')
        self.assertEqual(payload['derivation']['sealed'], 1)
        self.assertEqual(payload['walking']['source'], 'authored')

    def test_a_profile_without_land_is_refused(self):
        services, game = self.dbs(['interior:shack'])
        with self.assertRaises(ExportError):
            assemble(services, game, 'vanilla', 'snap')

    def test_a_profile_without_interiors_is_refused(self):
        services, game = self.dbs([], land=[('exterior:0,0', vhgt(offset=10.0), 0)])
        with self.assertRaises(ExportError):
            assemble(services, game, 'vanilla', 'snap')


if __name__ == '__main__':
    unittest.main()
