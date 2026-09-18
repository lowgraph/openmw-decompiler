"""Synthetic location records only; no installed game files are read."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from export_items import Plugin
from export_locations import (ref_key, split_cell, load_definitions, load_placements,
                              build_locations, script_leads, validate_output, write_output, main,
                              LocationSpool, write_spooled_output)
from test_export_items import pack_record, plugin_file, VERSIONS


def catalog():
    return {'gem': {'itemId': 'Gem', 'gameDataVersion': {'world': 'vanilla', 'version': VERSIONS['vanilla']},
                    'locations': [], 'scriptReferences': []}}


def cell(name, references, exterior=None):
    return pack_record('CELL', [('NAME', name.encode()),
        ('DATA', struct.pack('<Iii', 0 if exterior else 1, *(exterior or (0, 0))))] + references)


def reference(index, name, *extra):
    return [('FRMR', struct.pack('<I', index)), ('NAME', name.encode()),
            ('DATA', struct.pack('<6f', 1, 2, 3, 0, 0, 0)), *extra]


def holder(kind, ident, target, count=1):
    return pack_record(kind, [('NAME', ident.encode()), ('FNAM', ident.encode()),
                             ('NPCO', struct.pack('<i', count) + target.encode().ljust(32, b'\0'))])


def leveled(kind, ident, target, level=5, none=20):
    return pack_record(kind, [('NAME', ident.encode()), ('DATA', struct.pack('<I', 3)),
                             ('NNAM', bytes([none])), ('INDX', struct.pack('<I', 1)),
                             ('INAM' if kind == 'LEVI' else 'CNAM', target.encode()),
                             ('INTV', struct.pack('<h', level))])


class LocationTests(unittest.TestCase):
    def run_fixture(self, base_body, mod_body=b''):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base, mod = Path(directory.name) / 'base.esm', Path(directory.name) / 'mod.esp'
        plugin_file(base, base_body)
        plugin_file(mod, mod_body, ('base.esm',))
        plugins = [Plugin(base, 'vanilla'), Plugin(mod, 'tamriel_rebuilt')]
        items = catalog()
        definitions, _ = load_definitions(plugins, 'cp1252', items)
        cells, refs = load_placements(plugins, 'cp1252', definitions, items)
        warnings = build_locations(items, definitions, cells, refs, VERSIONS)
        return items, warnings

    def test_placed_and_owned_container_counts(self):
        body = holder('CONT', 'chest', 'gem', 3)
        body += cell('Guild', reference(1, 'Gem') + reference(2, 'chest', ('ANAM', b'owner'),
                     ('CNAM', b'mages guild'), ('FLTV', struct.pack('<i', 25)), ('KNAM', b'key')))
        items, _ = self.run_fixture(body)
        placed, chest = items['gem']['locations']
        self.assertEqual(placed['sourceType'], 'placed')
        self.assertEqual(chest['count'], 3)
        self.assertEqual(chest['access']['takingIsTheft'], 'conditional')
        self.assertEqual(chest['access']['lockLevel'], 25)

    def test_ref_override_retains_siblings_and_deletion(self):
        base = cell('Room', reference(1, 'Gem') + reference(2, 'Gem') + reference(3, 'Gem'))
        mod = cell('Room', reference(0x01000001, 'Gem', ('NAM9', struct.pack('<i', 7))) +
                   [('FRMR', struct.pack('<I', 0x01000002)), ('DELE', b'\0'*4)])
        items, _ = self.run_fixture(base, mod)
        rows = items['gem']['locations']
        self.assertEqual([r['count'] for r in rows], [7, 1])
        self.assertEqual(rows[0]['referenceId'], 'base.esm:00000001')

    def test_moved_reference_has_destination_cell(self):
        base = cell('', reference(1, 'Gem'), (0, 0))
        mod = cell('', [('MVRF', struct.pack('<I', 0x01000001)), ('CNDT', struct.pack('<ii', -2, 8))] +
                   reference(0x01000001, 'Gem'), (0, 0))
        items, _ = self.run_fixture(base, mod)
        self.assertEqual(len(items['gem']['locations']), 1)
        self.assertEqual(items['gem']['locations'][0]['cell']['grid'], {'x': -2, 'y': 8})

    def test_nested_leveled_creature_inventory(self):
        body = leveled('LEVC', 'spawn', 'rat') + holder('CREA', 'rat', 'loot') + leveled('LEVI', 'loot', 'gem')
        body += cell('Cave', reference(1, 'spawn'))
        items, _ = self.run_fixture(body)
        row = items['gem']['locations'][0]
        self.assertEqual(row['availability'], 'leveled_chance')
        self.assertEqual(row['actorId'], 'rat')
        self.assertEqual([p['kind'] for p in row['path']], ['LEVC', 'CREA', 'LEVI'])
        self.assertEqual(row['path'][0]['chanceNone'], 20)

    def test_inventory_override_restock_and_no_sale_claim(self):
        base = holder('NPC_', 'merchant', 'gem') + cell('Shop', reference(1, 'merchant'))
        mod = holder('NPC_', 'merchant', 'gem', -5)
        items, _ = self.run_fixture(base, mod)
        row = items['gem']['locations'][0]
        self.assertTrue(row['restocking'])
        self.assertEqual(row['count'], 5)
        self.assertEqual(row['access']['saleStatus'], 'not_determined')

    def test_cycle_warns_without_infinite_recursion(self):
        body = leveled('LEVI', 'loop', 'loop') + cell('Room', reference(1, 'loop'))
        items, warnings = self.run_fixture(body)
        self.assertEqual(items['gem']['locations'], [])
        self.assertTrue(any('cycle' in w for w in warnings))

    def test_chance_none_100_excluded(self):
        items, _ = self.run_fixture(leveled('LEVI', 'never', 'gem', none=100) + cell('Room', reference(1, 'never')))
        self.assertEqual(items['gem']['locations'], [])

    def test_deleted_cell_and_replaced_reference(self):
        base = cell('Deleted', reference(1, 'Gem')) + cell('Room', reference(2, 'Gem'))
        mod = cell('Deleted', [('DELE', b'\0'*4)]) + cell('Room', reference(0x01000002, 'unrelated_static'))
        items, _ = self.run_fixture(base, mod)
        self.assertEqual(items['gem']['locations'], [])

    def test_script_mentions_not_locations(self):
        source = '; AddItem "Gem" 1\nplayer->AddItem "gEm", 2\nMessageBox "gem"'
        self.assertEqual(len(script_leads(source, catalog())['gem']), 2)
        body = pack_record('SCPT', [('SCHD', b'reward'.ljust(52, b'\0')), ('SCTX', source.encode())])
        items, _ = self.run_fixture(body)
        self.assertEqual(items['gem']['locations'], [])
        self.assertEqual(items['gem']['scriptReferences'][0]['interpretation'], 'unverified_text_reference')

    def test_master_index_not_global_load_index(self):
        self.assertEqual(ref_key(struct.pack('<I', 0x02000005), 'mod.esp', ['one.esm', 'two.esm']), 'two.esm:00000005')
        self.assertNotEqual(ref_key(struct.pack('<I', 5), 'one.esm', []), ref_key(struct.pack('<I', 5), 'two.esm', []))

    def test_schema_and_atomic_json_output(self):
        items, warnings = self.run_fixture(cell('Room', reference(1, 'Gem')))
        result = {'schemaVersion': '1.0.0', 'coverage': {'mode': 'static_plugin_analysis',
                  'plugins': [], 'excludedContent': [], 'warnings': warnings,
                  'scriptsWithoutSource': [], 'limitations': []}, 'items': list(items.values())}
        validate_output(result)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'locations.json'
            write_output(target, result)
            before = target.read_bytes()
            bad = deepcopy(result)
            bad['items'][0]['locations'][0]['position']['x'] = float('nan')
            with self.assertRaises(ValueError):
                write_output(target, bad)
            self.assertEqual(target.read_bytes(), before)
            self.assertEqual(json.loads(before), result)

    def test_cli_end_to_end_preserves_item_tables(self):
        from export_items import CATEGORIES
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, items = root / 'base', root / 'items'
            base.mkdir()
            items.mkdir()
            plugins = ['Morrowind.esm', 'Tribunal.esm', 'Bloodmoon.esm']
            for i, name in enumerate(plugins):
                plugin_file(base / name, cell('Room', reference(1, 'Gem')) if i == 0 else b'')
            cfg = root / 'openmw.cfg'
            cfg.write_text(f'data="{base}"\n' + '\n'.join('content=' + p for p in plugins))
            settings = {'openmwConfig': str(cfg), 'baseDataDirectory': str(base), 'modsDirectory': str(root / 'mods'),
                        'allowedModPrefixes': [], 'allowedPlugins': plugins, 'versions': VERSIONS, 'outputDirectory': 'items',
                        'locationCacheDirectory': str(root / 'cache'), 'locationOutputDirectory': str(root / 'output')}
            config = root / 'settings.json'
            config.write_text(json.dumps(settings))
            for name in CATEGORIES.values():
                rows = [{'id': 'Gem', 'gameDataVersion': {'world': 'vanilla', 'version': VERSIONS['vanilla']}}] if name == 'Miscellaneous' else []
                (items / f'{name}.json').write_text(json.dumps({'items': rows}))
            (items / 'export-report.json').write_text(json.dumps({'versions': VERSIONS,
                'plugins': [{'path': str(base / p)} for p in plugins]}))
            before = {p.name: p.read_bytes() for p in items.glob('*.json')}
            self.assertEqual(main(['--config', str(config)]), 0)
            result = json.loads((root / 'output/ItemLocations.json').read_text(encoding='utf-8'))
            self.assertEqual(result['items'][0]['locations'][0]['cell']['name'], 'Room')
            self.assertTrue(all((items / name).read_bytes() == data for name, data in before.items()))
            self.assertTrue((root / 'cache').is_dir())
            self.assertEqual(list((root / 'cache').iterdir()), [])
            self.assertFalse((items / 'ItemLocations.json').exists())

    def test_disk_spool_streams_rows_without_populating_catalog(self):
        items, warnings = self.run_fixture(cell('Room', reference(1, 'Gem')))
        location = items['gem']['locations'].pop()
        result = {'schemaVersion': '1.0.0', 'coverage': {'mode': 'static_plugin_analysis',
                  'plugins': [], 'excludedContent': [], 'warnings': warnings,
                  'scriptsWithoutSource': [], 'limitations': []}, 'items': list(items.values())}
        with tempfile.TemporaryDirectory() as tmp:
            spool = LocationSpool(Path(tmp) / 'spool.sqlite')
            try:
                for _ in range(200):
                    spool.add('gem', location)
                self.assertEqual(items['gem']['locations'], [])
                self.assertEqual(spool.count, 200)
                target = Path(tmp) / 'locations.json'
                write_spooled_output(target, result, spool)
                saved = json.loads(target.read_text(encoding='utf-8'))
                self.assertEqual(saved['items'][0]['locations'], [location] * 200)
                validate_output(saved)
                before = target.read_bytes()
                # A spool/catalog mismatch must not replace an existing export.
                spool.add('missing_id', location)
                with self.assertRaisesRegex(ValueError, 'count mismatch'):
                    write_spooled_output(target, result, spool)
                self.assertEqual(target.read_bytes(), before)
            finally:
                spool.close()


if __name__ == '__main__':
    unittest.main()
