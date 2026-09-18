import contextlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from build_acquisition_index import build
from inspect_acquisition_index import query_item
from build_world_catalog import build as world_build
from export_items import ExportError
import test_world_catalog
from test_export_items import pack_record
from test_export_locations import cell,reference,leveled,holder


class AcquisitionTests(unittest.TestCase):
    def fixture(self,root):
        # loot -> gem + inventory carrier; carrier is itself in a creature list.
        extra=pack_record('NPC_',[('NAME',b'carrier'),('NPDT',struct.pack('<h3B3xi',3,50,4,2,100)),
            ('NPCO',struct.pack('<i',1)+b'loot'.ljust(32,b'\0'))])
        extra+=leveled('LEVC','spawn','carrier')+cell('Spawn',reference(4,'spawn'))
        extra+=leveled('LEVI','cycle_a','cycle_b')+leveled('LEVI','cycle_b','cycle_a')
        extra+=holder('CONT','bad','missing')
        extra+=pack_record('BODY',[('NAME',b'part')])+leveled('LEVI','wrong','part')
        source=test_world_catalog.WorldTests().fixture(root,extra)
        world=world_build(source,root/'world');index=build(world,root/'index');return world,index

    def test_nested_spawn_evidence_and_profile_move(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            world,index=self.fixture(Path(tmp));before=world.read_bytes()
            with contextlib.closing(sqlite3.connect(world)) as w,contextlib.closing(sqlite3.connect(index)) as db:
                result=query_item(db,w,'tr','gem')
                self.assertFalse(result['truncated'])
                self.assertEqual({n['key'] for n in result['nodes']},{'gem','loot','chest','carrier','spawn'})
                self.assertEqual({p['cellKey'] for p in result['placements']},{'exterior:-3,2','interior:spawn'})
                self.assertFalse(any(p['directItemPlacement'] for p in result['placements']))
                self.assertTrue(any(e['details'].get('restocking') for e in result['edges']))
                vanilla=query_item(db,w,'vanilla','gem')
                self.assertTrue(any(p['directItemPlacement'] for p in vanilla['placements']))
                self.assertEqual({n['key'] for n in vanilla['nodes']},{'gem','loot','chest'})
                warnings=db.execute("SELECT code,target_key FROM warnings WHERE profile_id='tr'").fetchall()
                self.assertEqual(set(warnings),{('missing_target','missing'),('invalid_target_type','part')})
            self.assertEqual(world.read_bytes(),before)

    def test_cycles_and_explicit_limits(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            world,index=self.fixture(Path(tmp))
            with contextlib.closing(sqlite3.connect(world)) as w,contextlib.closing(sqlite3.connect(index)) as db:
                cycle=query_item(db,w,'tr','cycle_a')
                self.assertEqual(len(cycle['edges']),2);self.assertFalse(cycle['truncated'])
                for kwargs,reason in [({'max_depth':0},'max_depth'),({'max_nodes':1},'max_nodes'),({'max_edges':1},'max_edges'),({'max_placements':1},'max_placements')]:
                    result=query_item(db,w,'tr','gem',**kwargs)
                    self.assertTrue(result['truncated']);self.assertIn(reason,result['limitReasons'])
                w.execute("UPDATE metadata SET value=? WHERE key='builtAtUnix'",(json.dumps(0),));w.commit()
                with self.assertRaisesRegex(ExportError,'mismatch'):query_item(db,w,'tr','gem')

    def test_failed_rebuild_preserves_output(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);world,index=self.fixture(root);before=index.read_bytes()
            with contextlib.closing(sqlite3.connect(world)) as w:
                w.execute("UPDATE metadata SET value=? WHERE key='schemaVersion'",(json.dumps('bad'),));w.commit()
            with self.assertRaises(ExportError):build(world,root/'index')
            self.assertEqual(index.read_bytes(),before)
            self.assertEqual([p.name for p in index.parent.iterdir()],['acquisition.sqlite'])


if __name__=='__main__':unittest.main()
