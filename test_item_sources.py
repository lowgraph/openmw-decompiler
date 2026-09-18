import contextlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from query_item_sources import unified_sources,main
from build_acquisition_index import build as acquisition_build
from build_script_evidence import build as evidence_build
from build_journal_catalog import build as journal_build
from build_world_catalog import build as world_build
from export_items import ExportError
from test_export_items import pack_record
from test_journal_catalog import script,topic,info
from test_export_locations import cell,reference
import test_world_catalog


class SourceTests(unittest.TestCase):
    def fixture(self,root):
        body=pack_record('ACTI',[('NAME',b'shrine'),('SCRI',b'testscript')])
        body+=pack_record('NPC_',[('NAME',b'guard'),('NPDT',struct.pack('<h3B3xi',3,50,4,2,100))])
        body+=script('begin testscript\nif(x == 1)\nPlayer->AddItem gem 1\nendif\nPlayer->RemoveItem gem 1\nPlaceAtPC loot 1 0 0\nend')
        body+=topic('reward',0)+info('reward_info',kind=0,extra=[('ONAM',b'guard'),('BNAM',b'Player->AddItem gem 2')])
        body+=cell('Context',reference(3,'shrine')+reference(4,'guard'))
        source=test_world_catalog.WorldTests().fixture(root,body)
        world=world_build(source,root/'world');journal=journal_build(source,root/'journal')
        acquisition=acquisition_build(world,root/'acquisition');evidence=evidence_build(journal,world,root/'evidence')
        return acquisition,world,evidence

    def test_unified_graph_and_context_placements(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            paths=self.fixture(Path(tmp));before=[p.read_bytes() for p in paths]
            with contextlib.ExitStack() as stack:
                dbs=[stack.enter_context(contextlib.closing(sqlite3.connect(p))) for p in paths]
                result=unified_sources(*dbs,'tr','gem')
                self.assertFalse(result['truncated'])
                self.assertEqual(len(result['script']['events']),4)
                self.assertEqual({e['effectCategory'] for e in result['script']['events']},{'addition','removal','creation'})
                spawn=next(e for e in result['script']['events'] if e['command']=='placeatpc')
                self.assertEqual(spawn['relationToItem'],'static_ancestor_target')
                self.assertEqual({p['cellKey'] for p in result['static']['placements']},{'exterior:-3,2'})
                self.assertEqual({p['cellKey'] for p in result['script']['contextPlacements']},{'interior:context'})
                self.assertEqual(len(result['script']['contextPlacements']),2)
                self.assertTrue(all(v is None for v in result['assessment'].values()))
                vanilla=unified_sources(*dbs,'vanilla','gem')
                self.assertEqual(vanilla['script']['events'],[])
            self.assertEqual(before,[p.read_bytes() for p in paths])

    def test_caps_and_mismatches(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            paths=self.fixture(Path(tmp))
            with contextlib.ExitStack() as stack:
                dbs=[stack.enter_context(contextlib.closing(sqlite3.connect(p))) for p in paths]
                for kwargs,reason in [({'max_events':1},'script:events'),({'max_script_targets':1},'script:targets'),
                                     ({'max_anchors':1},'script:anchors'),({'max_anchor_placements':1},'script:anchor_placements'),
                                     ({'max_depth':0},'static:max_depth')]:
                    result=unified_sources(*dbs,'tr','gem',**kwargs)
                    self.assertTrue(result['truncated']);self.assertIn(reason,result['limitReasons'])
                with self.assertRaises(ExportError):unified_sources(*dbs,'tr','missing')
                with self.assertRaises(ExportError):unified_sources(*dbs,'tr_arce','gem')
                dbs[2].execute("UPDATE metadata SET value=? WHERE key='worldBuiltAtUnix'",(json.dumps(-1),));dbs[2].commit()
                with self.assertRaisesRegex(ExportError,'evidence/world mismatch'):unified_sources(*dbs,'tr','gem')

    def test_cli_json(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            a,w,e=self.fixture(Path(tmp))
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):
                status=main(['--item','gem','--acquisition-database',str(a),'--world-database',str(w),'--evidence-database',str(e)])
            self.assertEqual(status,0);self.assertEqual(json.loads(stream.getvalue())['item']['key'],'gem')


if __name__=='__main__':unittest.main()
