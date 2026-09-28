import sqlite3
import struct
import unittest

import base64
import json
import math
from pathlib import Path
import tempfile

from build_access_catalog import (BLOCKED, LAND, LAND_SIZE, SEA, SWIM, access, assemble,
                                  barrier_squares, encode, exits_of, grade_cell, heights,
                                  land_mask, load_walking_policy, opening_squares, placed,
                                  subrecord, walkable, walls_for)
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

    def test_with_a_policy_the_payload_carries_the_walkable_grid(self):
        services, game = self.dbs(['interior:shack'], land=[('exterior:0,0', vhgt(offset=10.0), 0)])
        world = world_db([('vanilla', 'ex_fence_01', 'exterior:0,0', 100.0, 100.0)])
        self.addCleanup(world.close)
        payload = assemble(services, game, 'vanilla', 'snap', world, POLICY | {'barriers': [WallTests.FENCE]})
        walk = payload['walkable']
        self.assertEqual(payload['schemaVersion'], '1.1.0')
        self.assertEqual((walk['squaresPerCell'], walk['squareSize'], walk['maxSlopeDegrees']), (16, 512, 46.0))
        self.assertEqual(walk['barriers'][0]['pieces'], 1)
        self.assertIn('exterior:0,0', walk['cells'])
        self.assertIn('exterior:1,0', walk['cells'], 'the shore beyond is swum')
        self.assertEqual(payload['derivation']['landSquares'], 256 - 1, 'one square is the fence')
        self.assertIn('fSwimRunBase', payload['walking']['gameSettings'])
        self.assertNotIn('walkable', assemble(services, game, 'vanilla', 'snap'), 'no policy, no grid')

    def test_a_profile_without_land_is_refused(self):
        services, game = self.dbs(['interior:shack'])
        with self.assertRaises(ExportError):
            assemble(services, game, 'vanilla', 'snap')

    def test_a_profile_without_interiors_is_refused(self):
        services, game = self.dbs([], land=[('exterior:0,0', vhgt(offset=10.0), 0)])
        with self.assertRaises(ExportError):
            assemble(services, game, 'vanilla', 'snap')


FLAT = [10.0] * LAND_SIZE ** 2
POLICY = {'schemaVersion': '1.0.0', 'policyVersion': 'test', 'squaresPerCell': 16, 'steepShare': 0.6,
          'swimReach': 2, 'barriers': []}


def ramp(rise):
    """Heights climbing `rise` units a vertex eastward."""
    return [10.0 + rise * (i % LAND_SIZE) for i in range(LAND_SIZE ** 2)]


class GradeTests(unittest.TestCase):
    """A square is too steep past OpenMW 0.51.0's 46 degrees, Constants::sMaxSlope."""

    def test_flat_land_and_open_sea(self):
        self.assertEqual(set(grade_cell(FLAT, 16, 0.6)), {LAND})
        self.assertEqual(set(grade_cell([-50.0] * LAND_SIZE ** 2, 16, 0.6)), {SEA})

    def test_the_limit_is_forty_six_degrees(self):
        steepest = math.tan(math.radians(46)) * 128  # about 132.5 units a vertex
        self.assertEqual(set(grade_cell(ramp(steepest - 1), 16, 0.6)), {LAND}, 'just walkable')
        self.assertEqual(set(grade_cell(ramp(steepest + 1), 16, 0.6)), {BLOCKED}, 'just too steep')

    def test_a_cliff_blocks_only_where_enough_of_the_square_is_steep(self):
        grid = list(FLAT)
        for y in range(LAND_SIZE):  # a 400-unit step between vertex columns 1 and 2
            for x in range(2, LAND_SIZE):
                grid[y * LAND_SIZE + x] += 400
        # Square 0 spans vertex columns 0 to 4: one of its four quad columns is steep.
        self.assertEqual(grade_cell(grid, 16, 0.2)[0], BLOCKED, 'a quarter steep blocks at 0.2')
        self.assertEqual(grade_cell(grid, 16, 0.6)[0], LAND, 'but not at 0.6')
        self.assertEqual(grade_cell(grid, 16, 0.2)[1], LAND, 'the square beyond the cliff is flat')

    def test_squares_run_west_to_east_then_south_to_north(self):
        grid = [-50.0] * LAND_SIZE ** 2
        grid[LAND_SIZE * LAND_SIZE - 1] = 50.0  # the north-east corner vertex
        codes = grade_cell(grid, 16, 0.6)
        self.assertEqual(codes[-1], LAND)
        self.assertEqual(sum(1 for c in codes if c == LAND), 1)


class GridTests(unittest.TestCase):
    def test_water_near_land_is_swum_across_cell_borders(self):
        grid = walkable({(0, 0): FLAT}, POLICY)
        self.assertEqual(set(grid[(0, 0)]), {LAND})
        east = grid[(1, 0)]
        self.assertEqual([east[c] for c in (0, 1, 2)], [SWIM, SWIM, SEA], 'two squares out from the shore')
        self.assertEqual(east[15 * 16 + 1], SWIM, 'along the whole shore')
        self.assertIn((1, 1), grid, 'the diagonal neighbour has its corner swum')
        self.assertNotIn((3, 0), grid, 'a cell all open sea is left out')

    def test_walls_block_and_gates_open_whatever_the_terrain(self):
        grid = walkable({(0, 0): FLAT, (1, 0): ramp(200)}, POLICY, walls={(3, 3), (99, 99)}, gates={(17, 0)})
        self.assertEqual(grid[(0, 0)][3 * 16 + 3], BLOCKED)
        self.assertEqual(grid[(1, 0)][1], LAND, 'a gate is built: it is walked however steep')
        self.assertEqual(grid[(1, 0)][2], BLOCKED)

    def test_squares_encode_two_bits_each_first_in_the_low_bits(self):
        self.assertEqual(base64.b64decode(encode([LAND, BLOCKED, SWIM, SEA, LAND])),
                         bytes([0b00111001, 0b01]))


class BarrierTests(unittest.TestCase):
    BARRIER = {'name': 'Fence', 'openingRadius': 600, 'maxGap': 3000}

    def ring(self, radius=8000, pieces=24):
        return [(radius * math.cos(2 * math.pi * i / pieces), radius * math.sin(2 * math.pi * i / pieces))
                for i in reversed(range(pieces))]

    def test_pieces_are_joined_round_the_ring_in_order(self):
        squares, report = barrier_squares(self.ring(), [], self.BARRIER, 512)
        self.assertEqual((report['pieces'], report['joined'], report['unjoined']), (24, 24, 0))
        self.assertIn((15, 0), squares, 'east of the middle')
        self.assertIn((-16, 0), squares, 'west of it')
        self.assertNotIn((0, 0), squares, 'the middle is not a wall')

    def test_a_gap_wider_than_max_gap_is_left_and_counted(self):
        pieces = [p for p in self.ring() if not (p[0] > 7000 and abs(p[1]) < 2500)]
        _, report = barrier_squares(pieces, [], self.BARRIER, 512)
        self.assertEqual(report['unjoined'], 1)

    def test_an_opening_clears_the_squares_around_it(self):
        gate = (8000.0, 0.0)
        squares, _ = barrier_squares(self.ring(), [gate], self.BARRIER, 512)
        self.assertNotIn((15, 0), squares)
        self.assertEqual(opening_squares([gate], 600, 512) & squares, set())
        self.assertIn((15, 0), opening_squares([gate], 600, 512))


class PolicyTests(unittest.TestCase):
    def load(self, policy):
        handle = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        json.dump(policy, handle)
        handle.close()
        path = Path(handle.name)
        self.addCleanup(path.unlink)
        return load_walking_policy(path)

    def test_the_shipped_policy_loads(self):
        policy = load_walking_policy(Path(__file__).parent/'policy/walking.json')
        self.assertEqual(policy['barriers'][0]['name'], 'Ghostfence')

    def test_malformed_policies_are_refused(self):
        fence = {'name': 'Fence', 'objects': ['ex_'], 'openings': [], 'openingRadius': 1, 'maxGap': 1, 'why': 'x'}
        for broken in (POLICY | {'schemaVersion': '2.0.0'}, POLICY | {'squaresPerCell': 10},
                       POLICY | {'squaresPerCell': True}, POLICY | {'steepShare': 0},
                       POLICY | {'steepShare': 1.5}, POLICY | {'swimReach': -1}, POLICY | {'swimReach': 2.5},
                       POLICY | {'barriers': {}}, POLICY | {'barriers': [fence | {'objects': []}]},
                       POLICY | {'barriers': [fence | {'maxGap': 0}]},
                       POLICY | {'barriers': [fence | {'profiles': ['morrowind']}]},
                       POLICY | {'barriers': [fence, fence | {'name': 'fence'}]}):
            with self.assertRaises(ExportError, msg=repr(broken)):
                self.load(broken)
        self.assertEqual(self.load(POLICY | {'barriers': [fence]})['barriers'][0]['name'], 'Fence')


def world_db(rows):
    world = sqlite3.connect(':memory:')
    world.executescript("""
      CREATE TABLE placements(version_id INTEGER PRIMARY KEY, reference_key, object_key, cell_key, x, y);
      CREATE TABLE profile_placements(profile_id, reference_key, version_id);""")
    for i, (profile, obj, cell, x, y) in enumerate(rows, 1):
        world.execute('INSERT INTO placements VALUES(?,?,?,?,?,?)', (i, f'ref{i}', obj, cell, x, y))
        world.execute('INSERT INTO profile_placements VALUES(?,?,?)', (profile, f'ref{i}', i))
    return world


class WallTests(unittest.TestCase):
    FENCE = {'name': 'Fence', 'objects': ['ex_fence_'], 'openings': ['ex_gate_'], 'openingRadius': 600,
             'maxGap': 3000, 'why': 'x'}

    def test_placements_are_found_by_prefix_outdoors_in_the_profile(self):
        world = world_db([('vanilla', 'ex_fence_01', 'exterior:0,0', 1.0, 2.0),
                          ('vanilla', 'ex_fence_02', 'exterior:0,0', 3.0, 4.0),
                          ('vanilla', 'ex_fencepost', 'exterior:0,0', 5.0, 6.0),
                          ('vanilla', 'ex_fence_03', 'interior:hall', 7.0, 8.0),
                          ('tr', 'ex_fence_04', 'exterior:0,0', 9.0, 9.0)])
        self.addCleanup(world.close)
        self.assertEqual(placed(world, 'vanilla', 'EX_FENCE_'), [(1.0, 2.0), (3.0, 4.0)])

    def test_a_barrier_with_no_pieces_fails_unless_it_is_for_another_profile(self):
        world = world_db([('vanilla', 'ex_fence_01', 'exterior:0,0', 0.0, 0.0)])
        self.addCleanup(world.close)
        policy = POLICY | {'barriers': [self.FENCE]}
        _walls, _gates, report = walls_for(world, 'vanilla', policy)
        self.assertEqual(report[0]['pieces'], 1)
        with self.assertRaises(ExportError):
            walls_for(world, 'tr', policy)
        self.assertEqual(walls_for(world, 'tr', POLICY | {'barriers': [self.FENCE | {'profiles': ['vanilla']}]}),
                         (set(), set(), []))


if __name__ == '__main__':
    unittest.main()
