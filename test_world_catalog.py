import contextlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from build_world_catalog import build,actor_details,decode_placement,cell_header
from extract_foundation import build as foundation
from export_items import ExportError
from test_export_items import pack_record,plugin_file,VERSIONS
from test_export_locations import cell,reference,leveled,holder


class WorldTests(unittest.TestCase):
    def fixture(self,root,mod_extra=b''):
        base,mod=root/'base.esm',root/'mod.esp'
        body=pack_record('MISC',[('NAME',b'gem')])
        # Full container definition; negative inventory counts must not be lost.
        body+=pack_record('CONT',[('NAME',b'chest'),('CNDT',struct.pack('<f',100)),('FLAG',struct.pack('<I',3)),
               ('NPCO',struct.pack('<i',-2)+b'loot'.ljust(32,b'\0'))])
        body+=leveled('LEVI','loot','gem')
        body+=cell('Room',[('RGNN',b'region'),('WHGT',struct.pack('<f',12))]+reference(1,'chest',('ANAM',b'Owner'))+reference(2,'gem'))
        plugin_file(base,body)
        mod_body=cell('Room',[('FRMR',struct.pack('<I',0x01000002)),('DELE',b'\0'*4)])
        mod_body+=cell('Room',[('MVRF',struct.pack('<I',0x01000001)),('CNDT',struct.pack('<ii',-3,2))]+reference(0x01000001,'chest'))
        plugin_file(mod,mod_body+mod_extra,('base.esm',))
        config={'profiles':[{'id':'vanilla','world':'vanilla','version':VERSIONS['vanilla'],'arce':False,'plugins':[base.name]},
             {'id':'tr','world':'tamriel_rebuilt','version':VERSIONS['tamriel_rebuilt'],'arce':False,'plugins':[base.name,mod.name]}]}
        database=root/'source.sqlite'
        foundation(config,[base,mod],'cp1252',database)
        return database

    def test_normalized_build_profile_moves_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source=self.fixture(root);before=source.read_bytes()
            result=build(source,root/'output')
            self.assertEqual(source.read_bytes(),before)
            with contextlib.closing(sqlite3.connect(result)) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM inventories').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT count(*) FROM leveled_entries').fetchone()[0],1)
                self.assertEqual(db.execute('SELECT count_raw,quantity,restocking FROM inventories').fetchone(),(-2,2,1))
                self.assertEqual(db.execute("SELECT count(*) FROM profile_placements WHERE profile_id='vanilla'").fetchone()[0],2)
                self.assertEqual(db.execute("SELECT v.cell_key FROM profile_placements p JOIN placements v ON v.version_id=p.version_id WHERE p.profile_id='tr'").fetchone()[0],'exterior:-3,2')
                details=json.loads(db.execute("SELECT details FROM cells WHERE profile_id='tr' AND cell_key='interior:room'").fetchone()[0])
                self.assertEqual(details['waterHeight'],12)
                self.assertEqual(details['regionKey'],'region')
                self.assertEqual(details['fieldSources']['WHGT']['plugin'],'base.esm')
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_npc_both_layouts_and_creature(self):
        data={'NPDT':struct.pack('<h3B3xi',3,50,4,2,100),'FLAG':struct.pack('<I',0x16),
              'AIDT':struct.pack('<Bx3B3xI',30,90,20,0,0x10000)}
        level,respawn,essential,auto,detail=actor_details('NPC_',data)
        self.assertEqual((level,respawn,essential,auto),(3,True,True,True))
        self.assertIsNone(detail['skills']);self.assertEqual(detail['ai']['fight'],90)
        values=[5]+list(range(8))+list(range(27))+[100,200,300,50,2,3,1000]
        data['NPDT']=struct.pack('<h8B27Bx3H3Bxi',*values)
        detail=actor_details('NPC_',data)[4]
        self.assertEqual(detail['health'],100);self.assertEqual(detail['gold'],1000)
        self.assertEqual(detail['skills']['hand_to_hand'],26)
        data['NPDT']=struct.pack('<24i',*range(24))
        detail=actor_details('CREA',data)[4]
        self.assertEqual(detail['soulValue'],13)
        self.assertEqual(detail['attacks'][2],{'min':21,'max':22})

    def test_placement_condition_lock_and_door(self):
        payload=pack_record('CELL',reference(1,'gem',('NAM9',struct.pack('<i',4)),('FLTV',struct.pack('<i',20)),
                    ('INTV',struct.pack('<i',50)),('DODT',struct.pack('<6f',1,2,3,4,5,6)),('DNAM',b'Room')))[16:]
        values=decode_placement(payload,'cp1252');detail=json.loads(values[-1])
        self.assertEqual(values[3],4);self.assertEqual(detail['itemChargeOrConditionRaw'],50)
        self.assertEqual(detail['doorDestination']['cellName'],'Room')
        self.assertEqual(detail['lockLevelRaw'],20)

    def test_deleted_cell_excluded_and_bad_entry_reported(self):
        extra=cell('Room',[('DELE',b'\0'*4)])+leveled('LEVI','loot','missing')
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source=self.fixture(root,extra);result=build(source,root/'output')
            with contextlib.closing(sqlite3.connect(result)) as db:
                self.assertTrue(db.execute("SELECT 1 FROM warnings WHERE code='unresolved_leveled_entry' AND object_key='missing'").fetchone())

    def test_failed_build_preserves_previous_database(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source=self.fixture(root);result=build(source,root/'output');before=result.read_bytes()
            # Corrupt an archived container payload, not a game file.
            with contextlib.closing(sqlite3.connect(source)) as db:
                db.execute("UPDATE record_versions SET payload=? WHERE record_type='CONT'",(b'bad',));db.commit()
            with self.assertRaises(ExportError):build(source,root/'output')
            self.assertEqual(result.read_bytes(),before)
            self.assertEqual([p.name for p in result.parent.iterdir()],['world.sqlite'])

    def test_body_placements_and_invalid_inventory_targets(self):
        extra=pack_record('BODY',[('NAME',b'imperial cuirass'),('MODL',b'armor.nif')])
        extra+=cell('Parts',reference(1,'imperial cuirass')+reference(2,'absent'))
        extra+=leveled('LEVI','bad_item','imperial cuirass')
        extra+=leveled('LEVC','bad_creature','gem')
        extra+=leveled('LEVC','nested_creatures','bad_creature')
        extra+=pack_record('NPC_',[('NAME',b'assassin'),('NPDT',struct.pack('<h3B3xi',3,50,4,2,100))])
        extra+=leveled('LEVC','npc_spawns','assassin')
        extra+=leveled('LEVI','invalid_npc_item','assassin')
        extra+=leveled('LEVI','nested_items','loot')
        extra+=holder('CONT','bad_chest','imperial cuirass')
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source=self.fixture(root,extra);result=build(source,root/'output')
            with contextlib.closing(sqlite3.connect(result)) as db:
                self.assertEqual(db.execute("SELECT record_type,model FROM objects WHERE object_key='imperial cuirass'").fetchone(),('BODY','armor.nif'))
                warnings=db.execute("SELECT code,object_key,count,detail FROM warnings WHERE profile_id='tr'").fetchall()
                self.assertEqual({(code,key,count) for code,key,count,_ in warnings},{
                    ('invalid_inventory_target','imperial cuirass',1),
                    ('invalid_leveled_entry_target','imperial cuirass',1),
                    ('invalid_leveled_entry_target','gem',1),
                    ('invalid_leveled_entry_target','assassin',1),
                    ('unresolved_placement','absent',1)})
                self.assertTrue(all('BODY' in detail for _,key,_,detail in warnings if key=='imperial cuirass'))
                self.assertEqual(db.execute("SELECT e.object_key FROM leveled_entries e JOIN objects o ON o.version_id=e.list_version_id WHERE o.object_key='bad_item'").fetchone(),('imperial cuirass',))
                self.assertEqual(db.execute("SELECT count(*) FROM warnings WHERE profile_id='vanilla'").fetchone()[0],0)


if __name__=='__main__':unittest.main()
