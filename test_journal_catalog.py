import contextlib
import io
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import unittest

from build_journal_catalog import build,decode_response,parse_condition
from extract_foundation import build as foundation
from export_items import ExportError
from test_export_items import pack_record,plugin_file,VERSIONS


def topic(name,kind=4):
    return pack_record('DIAL',[('NAME',name.encode()),('DATA',bytes([kind]))])


def info(ident,index=0,response='Entry',marker=None,extra=(),kind=4):
    fs=[('INAM',ident.encode()),('PNAM',b''),('NNAM',b''),
        ('DATA',struct.pack('<ii3bx',kind,index,-1,-1,-1)),('NAME',response.encode())]
    if marker:fs.append((marker,b'\1'))
    return pack_record('INFO',fs+list(extra))


def script(source):
    return pack_record('SCPT',[('SCHD',b'testscript'.ljust(32,b'\0')+struct.pack('<5I',1,0,0,1,2)),
        ('SCVR',b'x\0'),('SCDT',b'\0'),('SCTX',source.encode())])


class JournalTests(unittest.TestCase):
    def fixture(self,root):
        base=root/'base.esm';mod=root/'mod.esp'
        plugin_file(base,topic('QuestOne')+info('title',response='First title',marker='QSTN')+
            info('start',10)+info('duplicate_index',10)+info('finish',77,marker='QSTF')+
            info('restart',5,marker='QSTR')+topic('QuestTwo')+info('start',10)+
            topic('Greeting',2)+info('dialogue',40,kind=2,extra=[('ONAM',b'Actor'),('FNAM',b'FFFF'),
                ('SCVR',b'04JX0QuestOne'),('INTV',struct.pack('<i',10)),
                ('SCVR',b'12fX2MyGlobal'),('FLTV',struct.pack('<f',1.5)),('BNAM',b'Journal QuestOne 77')])+
            script('begin testscript\nshort x\nend'))
        plugin_file(mod,topic('QuestOne')+info('title',response='Updated title',marker='QSTN')+
            pack_record('INFO',[('INAM',b'start'),('DELE',b'\0'*4)])+
            pack_record('DIAL',[('NAME',b'QuestTwo'),('DELE',b'\0'*4)])+
            script('begin testscript\nshort x\nset x to 1\nend'),('base.esm',))
        config={'profiles':[
            {'id':'vanilla','world':'vanilla','version':VERSIONS['vanilla'],'arce':False,'plugins':[base.name]},
            {'id':'tr','world':'tamriel_rebuilt','version':VERSIONS['tamriel_rebuilt'],'arce':False,'plugins':[base.name,mod.name]}]}
        source=root/'source.sqlite';foundation(config,[base,mod],'cp1252',source);return source

    def test_profiles_journal_markers_and_script_provenance(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source=self.fixture(root);before=source.read_bytes();result=build(source,root/'journal')
            self.assertEqual(source.read_bytes(),before)
            with contextlib.closing(sqlite3.connect(result)) as db:
                self.assertEqual(db.execute("SELECT title FROM quests WHERE profile_id='tr'").fetchall(),[('Updated title',)])
                self.assertEqual(db.execute("SELECT count(*) FROM journal_entries WHERE profile_id='vanilla' AND quest_key='questone' AND journal_index=10").fetchone()[0],2)
                self.assertEqual(db.execute("SELECT count(*) FROM journal_entries WHERE profile_id='tr' AND quest_key='questone' AND journal_index=10").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT journal_index FROM journal_entries WHERE profile_id='tr' AND quest_status='finished'").fetchone()[0],77)
                self.assertEqual(db.execute("SELECT journal_index FROM journal_entries WHERE profile_id='tr' AND quest_status='restart'").fetchone()[0],5)
                self.assertEqual(db.execute("SELECT actor_key,factionless,result_script FROM responses WHERE info_key='dialogue'").fetchone(),('actor',1,'Journal QuestOne 77'))
                self.assertEqual(db.execute('SELECT value_type,value_json FROM conditions ORDER BY entry_index').fetchall(),[('integer','10'),('float','1.5')])
                self.assertEqual(db.execute("SELECT s.plugin,p.origin_plugin FROM profile_scripts p JOIN scripts s ON s.version_id=p.version_id WHERE p.profile_id='tr'").fetchone(),('mod.esp','base.esm'))
                self.assertTrue(db.execute("SELECT 1 FROM warnings WHERE profile_id='tr' AND code='inactive_parent_topic'").fetchone())
                self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_structural_conditions_preserve_unusual_data(self):
        bad=parse_condition(b'?',None,None,'cp1252')
        self.assertIn('short_rule',bad[-1]);self.assertIn('missing_value',bad[-1])
        raw=info('i',extra=[('SCVR',b'04JX0Quest'),('SCVR',b'04JX0Other'),('INTV',struct.pack('<i',3))])[16:]
        _,conditions,issues=decode_response(raw,'cp1252')
        self.assertEqual(len(conditions),2)
        self.assertEqual(conditions[1][-1],'structural_only')
        self.assertTrue(issues)
        raw=info('i',marker='QSTF',extra=[('QSTR',b'\1')])[16:]
        values,_,issues=decode_response(raw,'cp1252')
        self.assertEqual(values[-1],'restart');self.assertEqual(issues[0][0],'multiple_quest_markers')

    def test_bad_build_preserves_published_database(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source=self.fixture(root);result=build(source,root/'journal');before=result.read_bytes()
            with contextlib.closing(sqlite3.connect(source)) as db:
                db.execute("UPDATE record_versions SET payload=? WHERE record_type='SCPT'",(b'bad',));db.commit()
            with self.assertRaises(ExportError):build(source,root/'journal')
            self.assertEqual(result.read_bytes(),before)
            self.assertEqual([p.name for p in result.parent.iterdir()],['journal.sqlite'])

    def test_missing_and_ambiguous_titles_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.redirect_stdout(io.StringIO()):
            root=Path(tmp);source=self.fixture(root)
            with contextlib.closing(sqlite3.connect(source)) as db:
                db.execute("UPDATE record_versions SET payload=? WHERE record_type='INFO' AND display_id='duplicate_index'",
                    (info('duplicate_index',response='Another title',marker='QSTN')[16:],));db.commit()
            result=build(source,root/'journal')
            with contextlib.closing(sqlite3.connect(result)) as db:
                self.assertEqual(db.execute("SELECT title,title_count FROM quests WHERE profile_id='tr' AND quest_key='questone'").fetchone(),(None,2))
                self.assertEqual(db.execute("SELECT title,title_count FROM quests WHERE profile_id='vanilla' AND quest_key='questtwo'").fetchone(),(None,0))
                self.assertEqual(db.execute("SELECT count(*) FROM quest_titles WHERE profile_id='tr' AND topic_key='questone'").fetchone()[0],2)


if __name__=='__main__':unittest.main()
