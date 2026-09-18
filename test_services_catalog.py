import contextlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from build_services_catalog import actor_services,CellResolver,build
from build_world_catalog import build as world_build
import test_world_catalog
from test_export_items import pack_record
from test_export_locations import cell,reference
from export_items import ExportError


class ServiceTests(unittest.TestCase):
    def test_flags_and_ordered_destinations(self):
        raw=pack_record('NPC_',[
            ('DNAM',b'Orphan'),('AIDT',struct.pack('<H3B3xI',500,30,30,0,0x80010001)),
            ('DODT',struct.pack('<6f',-1,-8193,0,0,0,0)),
            ('DODT',struct.pack('<6f',1,2,3,0,0,0)),('DNAM',b'Room')])[16:]
        flags,destinations,warnings=actor_services(raw,'cp1252')
        self.assertEqual(flags,0x80010001)
        self.assertEqual([d[0] for d in destinations],[None,'Room'])
        self.assertEqual(warnings[0][0],'orphan_transport_name')

    def test_cell_resolution_negative_grid_and_names(self):
        resolver=CellResolver([('interior:room','Room',1),('exterior:-1,-2','Place',0),
            ('exterior:0,0','Shared',0),('exterior:1,0','Shared',0)])
        self.assertEqual(resolver.resolve(None,-1,-8193),('exterior:-1,-2','resolved'))
        self.assertEqual(resolver.resolve(None,-8192,0),('exterior:-1,0','implicit_exterior'))
        self.assertEqual(resolver.resolve('ROOM',0,0),('interior:room','resolved'))
        self.assertEqual(resolver.resolve('Place',0,0),('exterior:-1,-2','resolved'))
        self.assertEqual(resolver.resolve('Shared',0,0),(None,'ambiguous_name'))
        self.assertEqual(resolver.resolve('Missing',0,0),(None,'missing_cell'))

    def fixture(self,root):
        extra=pack_record('NPC_',[('NAME',b'guide'),('FNAM',b'Guide'),
            ('NPDT',struct.pack('<h3B3xi',3,50,4,2,100)),
            ('AIDT',struct.pack('<H3B3xI',500,30,30,0,0x10001)),
            ('DODT',struct.pack('<6f',1,2,3,0,0,0)),('DNAM',b'Room'),
            ('DODT',struct.pack('<6f',-1,-8193,0,0,0,0))])
        extra+=pack_record('CREA',[('NAME',b'creature_merchant'),('NPDT',struct.pack('<24i',*range(24))),
            ('AIDT',struct.pack('<H3B3xI',30,30,30,0,0x2000))])
        extra+=pack_record('DOOR',[('NAME',b'door')])
        extra+=pack_record('NPC_',[('NAME',b'unknown_bits_only'),
            ('NPDT',struct.pack('<h3B3xi',3,50,4,2,100)),
            ('AIDT',struct.pack('<H3B3xI',30,30,30,0,0x80000000))])
        extra+=cell('Start',reference(10,'guide')+reference(11,'guide')+
            reference(12,'door',('DODT',struct.pack('<6f',1,2,3,0,0,0)),('DNAM',b'Room'))+
            reference(13,'door'))
        source=test_world_catalog.WorldTests().fixture(root,extra)
        world=world_build(source,root/'world')
        return source,world

    def test_build_directed_routes_profiles_and_publication(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source,world=self.fixture(root)
            source_before=source.read_bytes();world_before=world.read_bytes()
            result=build(source,world,root/'services')
            self.assertEqual(source.read_bytes(),source_before)
            self.assertEqual(world.read_bytes(),world_before)
            with contextlib.closing(sqlite3.connect(result)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM providers').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM transport_destinations').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM provider_locations').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM travel_edges').fetchone()[0],5)
                self.assertEqual(db.execute("SELECT count(*) FROM travel_edges WHERE profile_id='vanilla'").fetchone()[0],0)
                self.assertEqual(db.execute('SELECT count(*) FROM door_links').fetchone()[0],1)
                self.assertEqual(db.execute("SELECT count(*) FROM warnings WHERE code='provider_without_direct_placement'").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT count(*) FROM warnings WHERE code='unknown_service_bits'").fetchone()[0],1)
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            before=result.read_bytes()
            with contextlib.closing(sqlite3.connect(world)) as db:
                db.execute("UPDATE metadata SET value=? WHERE key='snapshotId'",(json.dumps('wrong'),));db.commit()
            with self.assertRaisesRegex(ExportError,'snapshot mismatch'):build(source,world,root/'services')
            self.assertEqual(result.read_bytes(),before)
            self.assertEqual([p.name for p in result.parent.iterdir()],['services.sqlite'])


if __name__=='__main__':unittest.main()
