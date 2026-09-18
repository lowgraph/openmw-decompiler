"""Saved samples and synthetic plugins only; never reads installed game data."""
import json
from pathlib import Path
import struct
import tempfile
import unittest

from export_items import (ROOT, Plugin, Record, Formatter, ExportError, CATEGORIES,
                          records, load_plugins, build_datasets, validators,
                          select_plugins, config_value, publish, main)

VERSIONS = {'vanilla': 'OpenMW 0.51.0', 'tamriel_rebuilt': 'Tamriel Rebuilt 26.08.23'}
NAMES = {14: 'Fire Damage', 17: 'Drain Attribute', 74: 'Restore Attribute', 79: 'Fortify Attribute'}


def pack_record(tag, fields):
    data = b''.join(k.encode('ascii') + struct.pack('<I', len(v)) + v for k, v in fields)
    return tag.encode('ascii') + struct.pack('<III', len(data), 0, 0) + data


def plugin_file(path, body, masters=()):
    path.write_bytes(pack_record('TES3', [('MAST', m.encode() + b'\0') for m in masters]) + body)


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from effect_names import EFFECT_GMSTS
        raw = json.loads((ROOT / 'items/examples/sample-records.raw.json').read_text())
        cls.base = Plugin(Path('Morrowind.esm'), 'vanilla')
        cls.winners = {}
        for tag, sample in raw.items():
            cls.winners[(tag, sample['id'].casefold())] = Record(tag,
                [(v['tag'], bytes.fromhex(v['hex'])) for v in sample['fields']], cls.base, 'vanilla')
        for ident, name in NAMES.items():
            gmst = EFFECT_GMSTS[ident]
            cls.winners[('GMST', gmst)] = Record('GMST', [('NAME', gmst.encode()), ('STRV', name.encode())], cls.base, 'vanilla')

    def test_all_twelve_saved_samples_validate_and_match(self):
        datasets = build_datasets(self.winners, VERSIONS, 'cp1252')
        checks = validators()
        self.assertEqual(len(datasets), 12)
        for tag, dataset in datasets.items():
            checks[tag].validate(dataset)
            self.assertEqual(len(dataset['items']), 1)
            filename = 'Goldbrand.json' if tag == 'WEAP' else CATEGORIES[tag] + '.sample.json'
            expected = json.loads((ROOT / 'items/examples' / filename).read_text())
            for key, value in expected.items():
                self.assertEqual(dataset['items'][0][key], value, (tag, key))

    def test_enchantment_override_case_insensitive_and_origin_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, mod = Path(tmp) / 'base.esm', Path(tmp) / 'mod.esp'
            enchant = [('NAME', b'goldbrand'), ('ENDT', struct.pack('<4i', 1, 5, 50, 0))]
            weapon = self.winners[('WEAP', 'katana_goldbrand_unique')].fields
            plugin_file(base, pack_record('ENCH', enchant) + pack_record('WEAP', weapon))
            plugin_file(mod, pack_record('ENCH', [('NAME', b'GOLDBRAND'), ('ENDT', struct.pack('<4i', 1, 7, 90, 1))])
                        + pack_record('WEAP', weapon), masters=('base.esm',))
            winners = load_plugins([Plugin(base, 'vanilla'), Plugin(mod, 'tamriel_rebuilt')], 'cp1252')
            item = Formatter(winners, VERSIONS).item(winners[('WEAP', 'katana_goldbrand_unique')])
            self.assertEqual(item['enchantment']['charges'], 90)
            self.assertEqual(item['enchantment']['cost'], 7)
            self.assertEqual(item['sourcePlugin'], 'mod.esp')
            self.assertEqual(item['gameDataVersion']['world'], 'vanilla')

    def test_deleted_item_removed_and_missing_master_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base, mod = Path(tmp) / 'base.esm', Path(tmp) / 'mod.esp'
            plugin_file(base, pack_record('MISC', [('NAME', b'item')]))
            plugin_file(mod, pack_record('MISC', [('NAME', b'ITEM'), ('DELE', b'\0'*4)]), ('base.esm',))
            with self.assertRaises(ExportError):
                load_plugins([Plugin(mod, 'tamriel_rebuilt')], 'cp1252')
            winners = load_plugins([Plugin(base, 'vanilla'), Plugin(mod, 'tamriel_rebuilt')], 'cp1252')
            self.assertNotIn(('MISC', 'item'), winners)

    def test_missing_enchantment_fails(self):
        winners = {k: v for k, v in self.winners.items() if k[0] != 'ENCH'}
        with self.assertRaisesRegex(ExportError, 'Unresolved enchantment'):
            build_datasets(winners, VERSIONS, 'cp1252')

    def test_bloodmoon_shadowstrike_reversed_magnitude_is_preserved(self):
        from effect_names import EFFECT_GMSTS
        winners = dict(self.winners)
        gmst = EFFECT_GMSTS[40]
        winners[('GMST', gmst)] = Record('GMST', [('NAME', gmst.encode()), ('STRV', b'Chameleon')], self.base, 'vanilla')
        # Exact ENAM values inspected in Bloodmoon.esm's shadowstrike_en.
        effect = Formatter(winners, VERSIONS).effect(struct.pack('<Hbb5i', 40, -1, -1, 2, 0, 20, 200, 100))
        self.assertEqual(effect['magnitude'], {'min': 200, 'max': 100})
        self.assertEqual(effect['durationSeconds'], 20)
        dataset = build_datasets(winners, VERSIONS, 'cp1252')['WEAP']
        dataset['items'][0]['enchantment']['effects'] = [effect]
        validators()['WEAP'].validate(dataset)

    def test_reversed_weapon_damage_is_preserved(self):
        original = self.winners[('WEAP', 'katana_goldbrand_unique')]
        fields = []
        for key, value in original.fields:
            if key == 'WPDT':
                value = bytearray(value)
                value[22:24] = bytes((50, 10))
                value = bytes(value)
            fields.append((key, value))
        item = Formatter(self.winners, VERSIONS).item(Record('WEAP', fields, self.base, 'vanilla'))
        self.assertEqual(item['chop'], {'min': 50, 'max': 10})

    def test_static_lights_excluded(self):
        original = next(v for k, v in self.winners.items() if k[0] == 'LIGH')
        fields = []
        for key, value in original.fields:
            if key == 'LHDT':
                value = value[:20] + struct.pack('<I', 1)
            fields.append((key, value))
        self.assertIsNone(Formatter(self.winners, VERSIONS).item(Record('LIGH', fields, self.base, 'vanilla')))

    def test_truncated_plugin_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'broken.esm'
            path.write_bytes(b'TES3' + struct.pack('<III', 100, 0, 0) + b'x')
            with self.assertRaisesRegex(ExportError, 'truncated'):
                list(records(path))

    def test_plugin_allowlist_and_directory_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base, mods = root / 'base', root / 'mods'
            allowed, later, excluded = mods / 'Tamriel Rebuilt test', mods / 'Tamriel Rebuilt later', mods / 'Other'
            for folder in (base, allowed, later, excluded):
                folder.mkdir(parents=True)
            for name in ('Morrowind.esm', 'Tribunal.esm', 'Bloodmoon.esm'):
                (base / name).touch()
            for folder in (allowed, later, excluded):
                (folder / 'TR_Mainland.esm').touch()
            (excluded / 'Other.esp').touch()
            cfg = root / 'openmw.cfg'
            cfg.write_text('\n'.join(f'data="{p}"' for p in (base, allowed, later, excluded)) +
                           '\ncontent=Morrowind.esm\ncontent=Tribunal.esm\ncontent=Bloodmoon.esm\ncontent=TR_Mainland.esm\ncontent=Other.esp')
            settings = {'openmwConfig': str(cfg), 'baseDataDirectory': str(base), 'modsDirectory': str(mods),
                        'allowedModPrefixes': ['Tamriel Rebuilt'],
                        'allowedPlugins': ['Morrowind.esm', 'Tribunal.esm', 'Bloodmoon.esm', 'TR_Mainland.esm']}
            selected, ignored, _ = select_plugins(settings)
            self.assertEqual(selected[-1].path.parent, later)
            self.assertEqual(ignored, ['Other.esp'])
            (later / 'TR_Mainland.esm').unlink()
            (allowed / 'TR_Mainland.esm').unlink()
            with self.assertRaisesRegex(ExportError, 'Approved active plugin missing'):
                select_plugins(settings)

    def test_publication_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            datasets = build_datasets(self.winners, VERSIONS, 'cp1252')
            publish(datasets, Path(tmp), {'sampleOnly': True})
            for tag, name in CATEGORIES.items():
                self.assertEqual(json.loads((Path(tmp) / f'{name}.json').read_text(encoding='utf-8')), datasets[tag])

    def test_cli_exports_fixture_plugins_and_preserves_output_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / 'base'
            base.mkdir()
            body = b''.join(pack_record(record.tag, record.fields) for record in self.winners.values())
            plugin_file(base / 'Morrowind.esm', body)
            plugin_file(base / 'Tribunal.esm', b'', ('Morrowind.esm',))
            plugin_file(base / 'Bloodmoon.esm', b'', ('Morrowind.esm',))
            cfg = root / 'openmw.cfg'
            cfg.write_text(f'data="{base}"\ncontent=Morrowind.esm\ncontent=Tribunal.esm\ncontent=Bloodmoon.esm')
            settings = {'openmwConfig': str(cfg), 'baseDataDirectory': str(base),
                        'modsDirectory': str(root / 'mods'), 'allowedModPrefixes': [],
                        'allowedPlugins': ['Morrowind.esm', 'Tribunal.esm', 'Bloodmoon.esm'],
                        'versions': VERSIONS, 'outputDirectory': 'output'}
            settings_path = root / 'settings.json'
            settings_path.write_text(json.dumps(settings))
            self.assertEqual(main(['--config', str(settings_path)]), 0)
            result = root / 'output/Weapons.json'
            before = result.read_bytes()
            exported = json.loads(before)
            self.assertEqual(exported['items'][0]['enchantment']['charges'], 50)
            # Remove a referenced enchantment and ensure an unsuccessful second
            # run leaves the previously published table byte-for-byte unchanged.
            body = b''.join(pack_record(record.tag, record.fields) for record in self.winners.values() if record.tag != 'ENCH')
            plugin_file(base / 'Morrowind.esm', body)
            self.assertEqual(main(['--config', str(settings_path)]), 1)
            self.assertEqual(result.read_bytes(), before)

    def test_config_quotes(self):
        self.assertEqual(config_value('"A:/Mods &"Special&" && Stuff" # comment'), 'A:/Mods "Special" & Stuff')


if __name__ == '__main__':
    unittest.main()
