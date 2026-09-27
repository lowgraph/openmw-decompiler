import sqlite3
import unittest

from build_intervention_catalog import (CELL_SIZE, TRANSCRIBED_FROM, assemble, build, cell_of,
                                        check_transcription, closest_from_exterior,
                                        closest_from_interior, exterior_candidates)
from export_items import ExportError


def ring(*cells):
    """Candidates as getExteriorPtrs yields them: one per cell, in grid order."""
    markers = [{'reference': f'm{i}', 'cell': f'exterior:{x},{y}', 'pos': [0, 0, 0]}
               for i, (x, y) in enumerate(cells)]
    return exterior_candidates(markers)[0]


def centre(x, y):
    return (x * CELL_SIZE + CELL_SIZE / 2, y * CELL_SIZE + CELL_SIZE / 2)


class CellTests(unittest.TestCase):
    def test_positions_floor_into_cells_as_the_engine_does(self):
        self.assertEqual(cell_of(0, 0), (0, 0))
        self.assertEqual(cell_of(8191.9, 8192), (0, 1))
        self.assertEqual(cell_of(-0.5, -8192), (-1, -1), 'floor, not truncation towards zero')
        self.assertEqual(cell_of(-8192.5, 0), (-2, 0))


class ExteriorTests(unittest.TestCase):
    """getClosestMarkerFromExteriorPosition, openmw-0.51.0."""

    def test_a_marker_in_your_own_cell_wins_outright(self):
        self.assertEqual(closest_from_exterior((5, 5), ring((0, 0), (5, 5))), 1)

    def test_the_smallest_ring_wins_even_when_it_is_farther_in_a_straight_line(self):
        # (3, 3) is 4.24 cells away on ring 3; (4, 0) is 4 cells away on ring 4.
        self.assertEqual(closest_from_exterior((0, 0), ring((4, 0), (3, 3))), 1)

    def test_ties_on_a_ring_go_round_from_the_south_west_corner(self):
        south, east, north, west, sw = (0, -1), (1, 0), (0, 1), (-1, 0), (-1, -1)
        self.assertEqual(closest_from_exterior((0, 0), ring(east, north)), 0, 'east before north')
        self.assertEqual(closest_from_exterior((0, 0), ring(north, west)), 0, 'north before west')
        self.assertEqual(closest_from_exterior((0, 0), ring(south, west)), 0, 'south before all')
        self.assertEqual(closest_from_exterior((0, 0), ring(south, sw)), 1, 'the corner starts the walk')

    def test_equal_places_on_the_walk_keep_the_first_in_grid_order(self):
        # (1, 1) is the NE corner: east edge, distance 2 + 2 = 4, same as nothing else;
        # two markers can only tie when they share a cell, and then only one counts.
        markers = [{'reference': 'a', 'cell': 'exterior:1,1', 'pos': [0, 0, 0]},
                   {'reference': 'b', 'cell': 'exterior:1,1', 'pos': [0, 0, 0]}]
        candidates, shared = exterior_candidates(markers)
        self.assertEqual(candidates, [(1, 1, 0)])
        self.assertEqual(shared, ['b'], 'the second marker in a cell is never chosen')

    def test_no_exterior_marker_means_no_answer(self):
        self.assertIsNone(closest_from_exterior((0, 0), []))


class InteriorTests(unittest.TestCase):
    """getClosestMarker from an interior: doors, a cell at a time."""
    far = ring((10, 0), (0, 10))

    def test_the_first_door_outdoors_decides_by_the_ring_around_where_it_lands(self):
        doors = {'interior:hall': [('interior:cellar', 0, 0), ('exterior:9,0', *centre(9, 0))]}
        self.assertEqual(closest_from_interior('interior:hall', doors, {}, self.far), (0, []))

    def test_a_marker_inside_a_reachable_cell_wins(self):
        doors = {'interior:hall': [('interior:shrine', 0, 0)]}
        self.assertEqual(closest_from_interior('interior:hall', doors, {'interior:shrine': 7}, self.far),
                         (7, []))

    def test_a_shallower_door_outdoors_beats_a_deeper_marker(self):
        doors = {'interior:hall': [('interior:passage', 0, 0), ('exterior:0,9', *centre(0, 9))],
                 'interior:passage': [('interior:shrine', 0, 0)]}
        chosen, _ = closest_from_interior('interior:hall', doors, {'interior:shrine': 7}, self.far)
        self.assertEqual(chosen, 1)

    def test_depth_counts_cells_not_distance(self):
        doors = {'interior:a': [('interior:b', 0, 0)], 'interior:b': [('interior:c', 0, 0)],
                 'interior:c': [('exterior:10,0', *centre(10, 0))]}
        self.assertEqual(closest_from_interior('interior:a', doors, {}, self.far), (0, []))

    def test_a_sealed_interior_has_no_answer(self):
        doors = {'interior:vault': [('interior:annex', 0, 0)], 'interior:annex': [('interior:vault', 0, 0)]}
        self.assertEqual(closest_from_interior('interior:vault', doors, {}, self.far), (None, []),
                         'a loop of doors ends, with nothing found')

    def test_cells_at_one_depth_disagreeing_are_reported(self):
        doors = {'interior:hub': [('interior:west wing', 0, 0), ('interior:East wing', 0, 0)],
                 'interior:west wing': [('exterior:0,9', *centre(0, 9))],
                 'interior:East wing': [('exterior:9,0', *centre(9, 0))]}
        chosen, others = closest_from_interior('interior:hub', doors, {}, self.far)
        self.assertEqual(chosen, 0, 'cells go in case-insensitive name order: East wing first')
        self.assertEqual(others, [1])

    def test_two_exits_that_agree_are_not_ambiguous(self):
        doors = {'interior:hall': [('exterior:9,0', *centre(9, 0)), ('exterior:9,1', *centre(9, 1))]}
        self.assertEqual(closest_from_interior('interior:hall', doors, {}, self.far), (0, []))


class Databases(unittest.TestCase):
    def services(self, cells, doors=()):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript("""
          CREATE TABLE metadata(key,value);
          CREATE TABLE cells(profile_id,cell_key,name,interior,grid_x,grid_y,region_key,synthetic);
          CREATE TABLE door_links(placement_version_id,reference_key,door_key,plugin,from_cell_key,
                                  cell_name,x,y,z,rx,ry,rz,source_x,source_y,source_z,details_json);
          CREATE TABLE profile_door_links(profile_id,placement_version_id,to_cell_key,status);""")
        for key, name in cells:
            grid = key.split(':')[1].split(',') if key.startswith('exterior:') else (None, None)
            db.execute('INSERT INTO cells VALUES(?,?,?,?,?,?,?,?)',
                       ('vanilla', key, name, int(key.startswith('interior:')), *grid, None, 0))
        for index, (origin, destination, x, y) in enumerate(doors, 1):
            db.execute('INSERT INTO door_links VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (index, f'd{index}', 'door', 'p', origin, None, x, y, 0, 0, 0, 0, 0, 0, 0, '{}'))
            db.execute('INSERT INTO profile_door_links VALUES(?,?,?,?)', ('vanilla', index, destination, 'resolved'))
        return db

    def world(self, markers):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript("""
          CREATE TABLE placements(version_id,reference_key,object_key,cell_key,x,y,z);
          CREATE TABLE profile_placements(profile_id,reference_key,version_id,origin_plugin);""")
        for index, (kind, cell, x, y) in enumerate(markers, 1):
            db.execute('INSERT INTO placements VALUES(?,?,?,?,?,?,?)', (index, f'r{index}', kind, cell, x, y, 0))
            db.execute('INSERT INTO profile_placements VALUES(?,?,?,?)', ('vanilla', f'r{index}', index, 'p'))
        return db


class BuildTests(Databases):
    CELLS = [('exterior:-2,-9', 'Seyda Neen'), ('exterior:0,-7', 'Pelagiad'),
             ('exterior:4,-13', 'Vivec, Temple'), ('interior:census office', 'Census Office'),
             ('interior:test cell', 'Test Cell')]

    def network(self):
        services = self.services(self.CELLS, doors=[
            ('interior:census office', 'exterior:-2,-9', *centre(-2, -9))])
        world = self.world([('divinemarker', 'exterior:0,-7', *centre(0, -7)),
                            ('templemarker', 'exterior:4,-13', *centre(4, -13))])
        return services, world

    def test_every_place_gets_both_answers(self):
        records, markers, derivation = build(*self.network(), 'vanilla')
        by_key = {r['key']: r for r in records}
        self.assertEqual(len(records), 5)
        self.assertEqual((by_key['exterior:-2,-9']['divine'], by_key['exterior:-2,-9']['almsivi']), (0, 0))
        self.assertEqual(by_key['interior:census office']['divine'], 0, 'out through the door to Seyda Neen')
        self.assertIsNone(by_key['interior:test cell']['divine'], 'no door out: the spell fails')
        self.assertEqual(derivation['divine']['placesWithNoAnswer'], 1)

    def test_markers_carry_their_town(self):
        _, markers, _ = build(*self.network(), 'vanilla', {'radius': 1, 'overrides': {}})
        self.assertEqual(markers['almsivi'][0]['town'], 'Vivec', "'Vivec, Temple' is in Vivec")
        self.assertEqual(markers['divine'][0]['cell'], 'exterior:0,-7')

    def test_a_profile_with_no_marker_of_a_kind_is_refused(self):
        services = self.services(self.CELLS)
        world = self.world([('divinemarker', 'exterior:0,-7', *centre(0, -7))])
        with self.assertRaises(ExportError) as caught:
            build(services, world, 'vanilla')
        self.assertIn('templemarker', str(caught.exception))

    def test_a_profile_with_no_cells_is_refused(self):
        with self.assertRaises(ExportError):
            build(self.services([]), self.world([]), 'vanilla')

    def test_the_payload_carries_the_rule_and_records_keyed_for_the_bundle(self):
        payload = assemble(*self.network(), 'vanilla', 'snap')
        self.assertEqual(payload['rule']['source'], 'authored')
        self.assertEqual(payload['snapshotId'], 'snap')
        keys = [r['key'] for r in payload['records']]
        self.assertEqual(len(keys), len(set(keys)))


class TranscriptionTests(unittest.TestCase):
    def test_the_rule_is_pinned_to_one_engine_release(self):
        check_transcription({'vanilla': f'OpenMW {TRANSCRIBED_FROM}'})
        with self.assertRaises(ExportError) as caught:
            check_transcription({'vanilla': 'OpenMW 0.52.0'})
        self.assertIn('getClosestMarker', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
