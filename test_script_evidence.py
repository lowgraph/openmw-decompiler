import contextlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from script_evidence_parser import scan
from build_script_evidence import build
from inspect_script_evidence import item_evidence
from build_journal_catalog import build as journal_build
from build_world_catalog import build as world_build
from export_items import ExportError
from test_export_items import pack_record
from test_journal_catalog import script,topic,info
import test_world_catalog


class EvidenceTests(unittest.TestCase):
    def test_compact_control_keywords_preserve_context(self):
        source='''IF(x == 1)
Player->AddItem gem 1
ElseIf(x == 2)
WHILE(x < 3)
Player->AddItem gem amount
endwhile
else
Player->RemoveItem gem 1
endif'''
        events,warnings=scan(source)
        self.assertFalse(warnings)
        self.assertEqual(len(events),3)
        self.assertEqual(events[0]['context']['blocks'][0]['branches'][0]['text'],'IF(x == 1)')
        self.assertEqual(len(events[1]['context']['blocks']),2)
        self.assertEqual(len(events[1]['context']['blocks'][0]['branches']),2)
        self.assertEqual(len(events[2]['context']['blocks'][0]['branches']),3)
        self.assertFalse(any(e['context']['sourceHasStructuralWarnings'] for e in events))

    def test_command_named_variables_do_not_hide_real_commands(self):
        events,warnings=scan('''short journal
set journal to 1
set other to journal
Journal "quest" 30
set journal to 2''')
        self.assertFalse(warnings)
        self.assertEqual([e['command'] for e in events],['journal'])
        self.assertEqual(events[0]['targetKey'],'quest')
        # Dialogue results may assign an actor local without declaring it here.
        self.assertFalse(scan('set journal to 1')[1])
        self.assertFalse(scan('Set Journal To 1')[1])
        self.assertTrue(scan('unexpected AddItem gem 1')[1])
        self.assertTrue(scan('endif')[1])

    def test_comments_strings_and_receivers(self):
        events,warnings=scan('''; player->AddItem fake 1
MessageBox "AddItem fake 1; still text"
Player->AdDiTeM, "real;id", 2 ; comment
"named actor"->RemoveItem "real;id" 1
PlaceAtPC "real;id" 1 0 0''')
        self.assertFalse(warnings);self.assertEqual(len(events),3)
        self.assertEqual(events[0]['targetKey'],'real;id')
        self.assertEqual(events[0]['recipientKind'],'player')
        self.assertEqual(events[1]['kind'],'inventory_remove')
        self.assertEqual(events[1]['receiverKey'],'named actor')
        self.assertEqual(events[2]['recipientKind'],'player_position')

    def test_branch_history_return_and_expressions(self):
        events,warnings=scan('''if MenuMode
return
endif
if x == 1
AddItem gem 1
elseif x == 2
AddItem gem ( x + 1 )
else
while x < 2
AddItem gem amount
endwhile
endif''')
        self.assertFalse(warnings)
        self.assertEqual(len(events[1]['context']['blocks'][0]['branches']),2)
        self.assertEqual(len(events[2]['context']['blocks']),2)
        self.assertIsNone(events[1]['countLiteral'])
        self.assertEqual(events[0]['context']['precedingControlTransfers'][0]['blocks'][0]['kind'],'if')
        self.assertEqual(events[0]['recipientKind'],'implicit_context')

    def test_malformed_source_and_list_target_position(self):
        events,warnings=scan('''endif
addtolevitem loot gem 4
Player->AddItem "broken
if x
AddItem gem 1''')
        self.assertTrue(warnings)
        self.assertEqual(events[0]['targetKey'],'gem')
        self.assertTrue(events[0]['context']['sourceHasStructuralWarnings'])
        self.assertTrue(all(e['targetKey']=='gem' for e in events))

    def fixture(self,root):
        body=pack_record('WEAP',[('NAME',b'katana_goldbrand_unique'),('FNAM',b'Goldbrand')])
        body+=pack_record('ACTI',[('NAME',b'shrine'),('SCRI',b'testscript')])
        body+=script('begin testscript\nif x == 1\nPlayer->AddItem "katana_goldbrand_unique" 1\nendif\nRemoveItem katana_goldbrand_unique 1\nend')
        body+=topic('reward',0)+info('reward_info',kind=0,extra=[('ONAM',b'quest_actor'),('BNAM',b'Player->AddItem katana_goldbrand_unique 1')])
        foundation=test_world_catalog.WorldTests().fixture(root,body)
        world=world_build(foundation,root/'world');journal=journal_build(foundation,root/'journal')
        return world,journal

    def test_full_synthetic_build_context_and_profiles(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);world,journal=self.fixture(root);before=(world.read_bytes(),journal.read_bytes())
            path=build(journal,world,root/'evidence')
            self.assertEqual(before,(world.read_bytes(),journal.read_bytes()))
            with contextlib.closing(sqlite3.connect(path)) as db:
                result=item_evidence(db,'tr','katana_goldbrand_unique')
                self.assertFalse(result['truncated']);self.assertEqual(len(result['events']),3)
                dialogue=next(e for e in result['events'] if e['source_kind']=='dialogue')
                self.assertEqual(dialogue['dialogue_context']['actor_key'],'quest_actor')
                attached=next(e for e in result['events'] if e['source_kind']=='script')
                self.assertEqual(attached['scriptAttachments'][0]['object_key'],'shrine')
                self.assertTrue(all(e['target_status']=='resolved' for e in result['events']))
                self.assertTrue(item_evidence(db,'tr','katana_goldbrand_unique',1)['truncated'])
                self.assertEqual(item_evidence(db,'vanilla','katana_goldbrand_unique')['events'],[])
            before=path.read_bytes()
            with contextlib.closing(sqlite3.connect(journal)) as db:
                db.execute("UPDATE metadata SET value=? WHERE key='snapshotId'",(json.dumps('other'),));db.commit()
            with self.assertRaisesRegex(ExportError,'snapshot mismatch'):build(journal,world,root/'evidence')
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual([p.name for p in path.parent.iterdir()],['script-evidence.sqlite'])


if __name__=='__main__':unittest.main()
