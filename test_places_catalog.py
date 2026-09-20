import sqlite3
import unittest

from build_places_catalog import assemble, place, regions, settlements
from export_items import ExportError

# (cell_key, name, interior, grid_x, grid_y, region_key, synthetic)
WILD = ('exterior:-1,-1', None, 0, -1, -1, 'west gash region', 0)
TOWN_A = ('exterior:41,15', 'Port Telvannis', 0, 41, 15, 'telvanni isles', 0)
TOWN_B = ('exterior:42,16', 'Port Telvannis', 0, 42, 16, 'telvanni isles', 0)
SHACK = ("interior:aalmu ouradas' shack", "Aalmu Ouradas' Shack", 1, None, None, None, 0)


class Fixture(unittest.TestCase):
    def services(self, rows, profile='tr'):
        db = sqlite3.connect(':memory:')
        db.executescript("""
          CREATE TABLE cells(profile_id,cell_key,name,interior,grid_x,grid_y,region_key,synthetic);
          CREATE TABLE metadata(key,value);""")
        db.execute("INSERT INTO metadata VALUES('snapshotId','\"snap\"')")
        for row in rows:
            db.execute('INSERT INTO cells VALUES(?,?,?,?,?,?,?,?)', (profile, *row))
        db.commit()
        return db


class RecordTests(Fixture):
    def test_an_interior_carries_its_name_and_no_grid(self):
        record = place(*SHACK)
        self.assertEqual(record['name'], "Aalmu Ouradas' Shack")
        self.assertTrue(record['interior'])
        self.assertNotIn('grid', record)

    def test_an_exterior_carries_its_grid(self):
        self.assertEqual(place(*WILD)['grid'], [-1, -1])

    def test_an_absent_name_is_left_out_rather_than_published_as_null(self):
        # 4,801 exterior cells in TR are unnamed wilderness; four nulls apiece would
        # cost more than every other field in the catalog.
        record = place(*WILD)
        self.assertNotIn('name', record)
        self.assertIn('region', record)

    def test_an_interior_with_no_region_omits_it(self):
        self.assertNotIn('region', place(*SHACK))

    def test_a_synthetic_cell_is_flagged_rather_than_passed_off_as_read(self):
        inferred = ('interior:somewhere', 'Somewhere', 1, None, None, None, 1)
        self.assertTrue(place(*inferred)['synthetic'])
        self.assertNotIn('synthetic', place(*SHACK))


class SettlementTests(unittest.TestCase):
    def test_exterior_cells_sharing_a_name_become_one_settlement(self):
        # Port Telvannis really is seven grid squares.
        found = settlements([TOWN_A, TOWN_B, WILD])
        self.assertEqual([t['name'] for t in found], ['Port Telvannis'])
        self.assertEqual(found[0]['cells'], ['exterior:41,15', 'exterior:42,16'])

    def test_a_settlement_reports_its_bounds_and_middle(self):
        found = settlements([TOWN_A, TOWN_B])[0]
        self.assertEqual(found['bounds'], {'minX': 41, 'maxX': 42, 'minY': 15, 'maxY': 16})
        self.assertEqual(found['centre'], [41, 15], 'the rounded middle of the bounds')

    def test_interiors_are_not_settlements_even_when_named(self):
        self.assertEqual(settlements([SHACK]), [])

    def test_unnamed_wilderness_is_not_a_settlement(self):
        self.assertEqual(settlements([WILD]), [])

    def test_a_one_cell_settlement_still_counts(self):
        self.assertEqual(len(settlements([TOWN_A])), 1)


class RegionTests(unittest.TestCase):
    def test_regions_are_counted_and_sorted(self):
        found = regions([WILD, TOWN_A, TOWN_B, SHACK])
        self.assertEqual(found, [{'key': 'telvanni isles', 'cells': 2},
                                 {'key': 'west gash region', 'cells': 1}])

    def test_a_cell_with_no_region_is_not_counted(self):
        self.assertEqual(regions([SHACK]), [])


class PayloadTests(Fixture):
    def test_the_payload_counts_what_a_reviewer_needs(self):
        payload = assemble(self.services([WILD, TOWN_A, TOWN_B, SHACK]), 'tr', 'snap')
        counts = payload['derivation']
        self.assertEqual(counts['places'], 4)
        self.assertEqual(counts['interiors'], 1)
        self.assertEqual(counts['exteriors'], 3)
        self.assertEqual(counts['named'], 3)
        self.assertEqual(counts['settlements'], 1)
        self.assertEqual(counts['settlementsSpanningSeveralCells'], 1)

    def test_records_are_ordered_by_key_so_the_hash_is_stable(self):
        payload = assemble(self.services([TOWN_B, SHACK, TOWN_A]), 'tr', 'snap')
        keys = [r['key'] for r in payload['records']]
        self.assertEqual(keys, sorted(keys))

    def test_every_record_has_the_key_the_bundle_joins_on(self):
        payload = assemble(self.services([WILD, SHACK]), 'tr', 'snap')
        self.assertTrue(all(isinstance(r.get('key'), str) and r['key']
                            for r in payload['records']))
        self.assertEqual(payload['snapshotId'], 'snap')

    def test_a_profile_with_no_cells_fails_rather_than_publishing_nothing(self):
        with self.assertRaises(ExportError) as caught:
            assemble(self.services([]), 'tr', 'snap')
        self.assertIn('services catalog', str(caught.exception))


class CellReferenceTests(unittest.TestCase):
    """The bundle refuses to publish a cellKey that Places cannot resolve."""
    def bundle(self, places, **catalogs):
        from build_app_bundle import check_cell_references
        extra = {'Places': {'tr': {'records': [{'key': k} for k in places]}}}
        extra.update({name: {'tr': payload} for name, payload in catalogs.items()})
        return check_cell_references(extra, 'tr')

    def test_a_resolvable_reference_passes(self):
        checked = self.bundle(['interior:shop'],
                              Merchants={'records': [{'cells': ['interior:shop']}]})
        self.assertEqual(checked, 1)

    def test_a_merchant_in_an_unknown_cell_is_refused(self):
        with self.assertRaises(ExportError) as caught:
            self.bundle(['interior:shop'],
                        Merchants={'records': [{'cells': ['interior:nowhere']}]})
        self.assertIn('interior:nowhere', str(caught.exception))

    def test_a_gear_row_pick_in_an_unknown_cell_is_refused(self):
        with self.assertRaises(ExportError) as caught:
            self.bundle(['interior:shop'], GearRows={'rows': [
                {'primary': {'cellKey': 'interior:shop'},
                 'beastPrimary': {'cellKey': 'interior:nowhere'}}]})
        self.assertIn('interior:nowhere', str(caught.exception))

    def test_a_travel_node_outside_places_is_refused(self):
        with self.assertRaises(ExportError):
            self.bundle(['interior:shop'], Travel={'nodes': {'exterior:9,9': {}}})

    def test_without_places_nothing_is_checked(self):
        from build_app_bundle import check_cell_references
        self.assertEqual(check_cell_references(
            {'Merchants': {'tr': {'records': [{'cells': ['anywhere']}]}}}, 'tr'), 0)

    def test_an_empty_row_side_is_skipped_rather_than_crashing(self):
        self.assertEqual(self.bundle(['interior:shop'], GearRows={'rows': [
            {'primary': None, 'alternative': None, 'beastPrimary': None}]}), 0)


if __name__ == '__main__':
    unittest.main()
