import contextlib
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from extract_foundation import build, record_identity, fields, discover
from export_items import ExportError
from test_export_items import pack_record, plugin_file
from test_export_locations import cell, reference


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root/'base.esm'
        self.mod = self.root/'mod.esm'
        self.arce = self.root/'arce.esp'
        self.target = self.root/'out/game-data.sqlite'
        self.config = {'profiles': [
            {'id': 'vanilla', 'world': 'vanilla', 'version': 'OpenMW 0.51.0', 'arce': False, 'plugins': ['base.esm']},
            {'id': 'tr', 'world': 'tamriel_rebuilt', 'version': 'Tamriel Rebuilt 26.08.23', 'arce': False, 'plugins': ['base.esm','mod.esm']},
            {'id': 'tr_arce', 'world': 'tamriel_rebuilt', 'version': 'Tamriel Rebuilt 26.08.23', 'arce': True, 'plugins': ['base.esm','mod.esm','arce.esp']}]}
        base = pack_record('WEAP',[('NAME',b'Sword'),('FNAM',b'Original')])
        base += pack_record('MISC',[('NAME',b'Gem')])
        base += cell('Room',reference(1,'Sword') + reference(2,'Gem'))
        base += pack_record('DIAL',[('NAME',b'Topic')]) + pack_record('INFO',[('INAM',b'123'),('NAME',b'Dialogue')])
        base += pack_record('ZZZZ',[('DATA',b'opaque')])
        plugin_file(self.base,base)
        mod = pack_record('WEAP',[('NAME',b'SWORD'),('FNAM',b'Modified')])
        mod += pack_record('MISC',[('NAME',b'Gem'),('DELE',b'\0'*4)])
        mod += cell('Room',[('FRMR',struct.pack('<I',0x01000002)),('DELE',b'\0'*4)])
        mod += cell('Room',[('MVRF',struct.pack('<I',0x01000001)),('CNDT',struct.pack('<ii',2,-1))]+reference(0x01000001,'Sword'))
        plugin_file(self.mod,mod,('base.esm',))
        plugin_file(self.arce,pack_record('MISC',[('NAME',b'Gem'),('FNAM',b'Restored')]),('base.esm','mod.esm'))

    def run_build(self):
        with contextlib.redirect_stdout(io.StringIO()):
            build(self.config,[self.base,self.mod,self.arce],'cp1252',self.target)

    def test_profiles_deletions_undeletes_and_provenance(self):
        self.run_build()
        with contextlib.closing(sqlite3.connect(self.target)) as db:
            def winner(profile,tag,key):
                return db.execute('SELECT origin_plugin_id,winning_plugin_id FROM live_records WHERE profile_id=? AND record_type=? AND record_key=?',(profile,tag,key)).fetchone()
            self.assertEqual(winner('vanilla','WEAP','sword'),(1,1))
            self.assertEqual(winner('tr','WEAP','sword'),(1,2))
            self.assertIsNone(winner('tr','MISC','gem'))
            self.assertEqual(winner('tr_arce','MISC','gem'),(1,3))
            self.assertEqual(db.execute("SELECT count(*) FROM record_versions WHERE record_type='ZZZZ'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT count(*) FROM live_records WHERE record_type='ZZZZ'").fetchone()[0],0)

    def test_reference_move_delete_and_profile_isolation(self):
        self.run_build()
        with contextlib.closing(sqlite3.connect(self.target)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM live_references WHERE profile_id='vanilla'").fetchone()[0],2)
            rows = db.execute("SELECT reference_key,target_cell_key FROM live_references WHERE profile_id='tr'").fetchall()
            self.assertEqual(rows,[('base.esm:00000001','exterior:2,-1')])

    def test_archive_can_reconstruct_exact_original_files(self):
        self.run_build()
        with contextlib.closing(sqlite3.connect(self.target)) as db:
            for plugin_id,path in enumerate((self.base,self.mod,self.arce),1):
                restored = b''.join(tag.encode()+struct.pack('<III',len(payload),unknown,flags)+payload
                    for tag,unknown,flags,payload in db.execute('SELECT record_type,header_unknown,header_flags,payload FROM record_versions WHERE plugin_id=? ORDER BY ordinal',(plugin_id,)))
                self.assertEqual(restored,path.read_bytes())
                self.assertEqual(db.execute('SELECT sha256 FROM plugins WHERE id=?',(plugin_id,)).fetchone()[0],hashlib.sha256(restored).hexdigest())

    def test_failed_rebuild_preserves_published_database(self):
        self.run_build()
        before = self.target.read_bytes()
        self.mod.write_bytes(b'broken')
        with self.assertRaises(ExportError):
            self.run_build()
        self.assertEqual(before,self.target.read_bytes())
        self.assertEqual(sorted(p.name for p in self.target.parent.iterdir()),['game-data.sqlite'])

    def test_missing_master_fails_before_publication(self):
        plugin_file(self.mod,b'',('missing.esm',))
        with self.assertRaisesRegex(ExportError,'requires earlier masters'):
            self.run_build()
        self.assertFalse(self.target.exists())

    def test_snapshot_is_repeatable(self):
        self.run_build()
        def snapshot():
            with contextlib.closing(sqlite3.connect(self.target)) as db:
                return db.execute("SELECT value FROM metadata WHERE key='snapshotId'").fetchone()[0]
        previous = snapshot()
        self.run_build()
        self.assertEqual(previous,snapshot())

    def test_dialogue_identity_scoped_to_topic(self):
        payload = pack_record('INFO',[('INAM',b'123')])[16:]
        self.assertNotEqual(record_identity('INFO',payload,'cp1252','A')[0],record_identity('INFO',payload,'cp1252','B')[0])

    def test_truncated_subrecords_rejected(self):
        with self.assertRaises(ExportError):
            list(fields(b'NAME'+struct.pack('<I',10)+b'a'))

    def test_discovery_does_not_require_active_content(self):
        cfg = self.root/'openmw.cfg'
        cfg.write_text(f'data="{self.root}"\ncontent=base.esm\n')
        source = {'openmwConfig':str(cfg),'baseDataDirectory':str(self.root),
                  'modsDirectory':str(self.root/'mods'), 'allowedModPrefixes':[],
                  'allowedPlugins':['base.esm','mod.esm','arce.esp']}
        paths,encoding = discover(self.config,source)
        self.assertEqual(paths,[self.base,self.mod,self.arce])
        self.assertEqual(encoding,'cp1252')


if __name__ == '__main__':
    unittest.main()
