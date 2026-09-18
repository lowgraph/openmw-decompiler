import contextlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from build_catalogs import CatalogDecoder, Store, build
from extract_foundation import build as build_foundation
from export_items import Record, Plugin, ExportError
from test_export_items import pack_record, plugin_file, VERSIONS, NAMES
from effect_names import EFFECT_GMSTS


class MemoryStore(dict):
    def keys_for(self, tag):
        return (key for kind,key in self if kind==tag)


class CatalogTests(unittest.TestCase):
    def decoder(self, tag, payload, key='test'):
        source=Plugin(Path('Morrowind.esm'),'vanilla')
        store=MemoryStore({(tag,key):Record(tag,payload,source,'vanilla')})
        return CatalogDecoder(store,VERSIONS,'cp1252')

    def test_race_attributes_are_interleaved_by_gender(self):
        values=[-1,0]*7 + list(range(16)) + [1.1,1.2,1.3,1.4,3]
        decoder=self.decoder('RACE',[('NAME',b'test'),('RADT',struct.pack('<30i4fI',*values)),('NPCS',b'POWER')])
        row=decoder.parse('RACE','test')
        self.assertEqual(row['attributes']['strength'],{'male':0,'female':1})
        self.assertEqual(row['attributes']['luck'],{'male':14,'female':15})
        self.assertTrue(row['playable'] and row['beast'])
        self.assertEqual(row['spellIds'],['power'])

    def test_class_minor_major_interleaving_and_padding(self):
        values=[0,1,2]+list(range(10))+[1,123]
        payload=bytearray(struct.pack('<13iB3xI',*values))
        payload[53:56]=b'XYZ'
        row=self.decoder('CLAS',[('CLDT',payload)]).parse('CLAS','test')
        self.assertEqual(row['minorSkills'],['block','medium_armor','blunt_weapon','axe','athletics'])
        self.assertEqual(row['majorSkills'],['armorer','heavy_armor','long_blade','spear','enchant'])
        self.assertTrue(row['playable'])
        self.assertEqual(row['servicesRaw'],123)

    def test_skills_and_magic_effect_layouts(self):
        row=self.decoder('SKIL',[('SKDT',struct.pack('<ii4f',1,1,1,2,3,4))],key='10').parse('SKIL','10')
        self.assertEqual(row['skill'],'destruction')
        self.assertEqual(row['useValues'],[1,2,3,4])
        row=self.decoder('MGEF',[('MEDT',struct.pack('<ifIiii3f',2,5.5,0x600,1,2,3,4,5,6))],key='14').parse('MGEF','14')
        self.assertEqual(row['school'],'destruction')
        self.assertTrue(row['allowEnchanting'] and row['allowSpellmaking'])
        self.assertEqual(row['baseCost'],5.5)

    def test_gmst_values_and_unset(self):
        for field,value,expected,kind in [('STRV',b'Hello','Hello','string'),('INTV',struct.pack('<i',-12),-12,'integer'),('FLTV',struct.pack('<f',0.5),0.5,'float')]:
            row=self.decoder('GMST',[(field,value)]).parse('GMST','test')
            self.assertEqual((row['value'],row['valueType']),(expected,kind))
        self.assertIsNone(self.decoder('GMST',[]).parse('GMST','test')['value'])

    def test_malformed_layout_fails(self):
        with self.assertRaises(ExportError):
            self.decoder('RACE',[('RADT',b'bad')]).parse('RACE','test')

    def test_build_publication_profile_isolation_and_references(self):
        raw=json.loads((Path(__file__).parent/'items/examples/sample-records.raw.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            base,mod=root/'Morrowind.esm',root/'mod.esp'
            body=b''
            for tag,sample in raw.items():
                body+=pack_record(tag,[(f['tag'],bytes.fromhex(f['hex'])) for f in sample['fields']])
            for ident,name in NAMES.items():
                body+=pack_record('GMST',[('NAME',EFFECT_GMSTS[ident].encode()),('STRV',name.encode())])
            plugin_file(base,body)
            plugin_file(mod,pack_record('WEAP',[('NAME',b'katana_goldbrand_unique'),('DELE',b'\0'*4)]),('Morrowind.esm',))
            config={'profiles':[
                {'id':'vanilla','world':'vanilla','version':VERSIONS['vanilla'],'arce':False,'plugins':[base.name]},
                {'id':'tr','world':'tamriel_rebuilt','version':VERSIONS['tamriel_rebuilt'],'arce':False,'plugins':[base.name,mod.name]}]}
            database=root/'foundation.sqlite'
            with contextlib.redirect_stdout(io.StringIO()):
                build_foundation(config,[base,mod],'cp1252',database)
                release=build(database,root/'catalogs')
            weapons=json.loads((release/'vanilla/Weapons.json').read_text())['records']
            self.assertEqual(weapons[0]['enchantmentId'],'goldbrand')
            self.assertNotIn('enchantment',weapons[0])
            self.assertEqual(weapons[0]['provenance']['originPlugin'],'Morrowind.esm')
            self.assertEqual(json.loads((release/'tr/Weapons.json').read_text())['records'],[])
            ench=json.loads((release/'vanilla/Enchantments.json').read_text())['records'][0]
            self.assertEqual(ench['effects'][0]['effectKey'],'14')
            before=(root/'catalogs/current.json').read_bytes()
            with self.assertRaises(ExportError):
                build(database,root/'catalogs')
            self.assertEqual(before,(root/'catalogs/current.json').read_bytes())
            self.assertFalse((root/'catalogs/build.lock').exists())


if __name__=='__main__':
    unittest.main()
