"""Index script/dialogue command evidence. Run full extraction locally in VS Code."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from extract_foundation import ROOT,load_config
from export_items import CATEGORIES,ExportError
from build_world_catalog import Progress,js
from build_acquisition_index import metadata
from script_evidence_parser import scan,COMMANDS


def sources(journal,profile):
    for row in journal.execute('''SELECT s.*,p.origin_plugin FROM profile_scripts p
        JOIN scripts s ON s.version_id=p.version_id WHERE p.profile_id=?''',(profile,)):
        yield row['version_id'],'script',row['script_key'],None,row['plugin'],row['origin_plugin'],row['source_text'],None
    for row in journal.execute('''SELECT r.*,p.origin_plugin FROM profile_responses p
        JOIN responses r ON r.version_id=p.version_id WHERE p.profile_id=? AND r.result_script IS NOT NULL AND r.result_script!='' ''',(profile,)):
        context=dict(row);context.pop('result_script')
        context['conditions']=[dict(c) for c in journal.execute('SELECT * FROM conditions WHERE response_version_id=? ORDER BY entry_index',(row['version_id'],))]
        yield row['version_id'],'dialogue',js([row['topic_key'],row['info_key']]),row['topic_key'],row['plugin'],row['origin_plugin'],row['result_script'],js(context)


def resolve(event,objects,journals,scripts):
    target,command=event
    if target is None:return 'unresolved_syntax',[]
    if command in ('startscript','stopscript'):
        return ('resolved' if target in scripts else 'missing_target'),(['SCPT'] if target in scripts else [])
    if command in ('journal','setjournalindex'):
        return ('resolved' if target in journals else 'missing_target'),(['DIAL'] if target in journals else [])
    matches=objects.get(target,[])
    if not matches:return 'missing_target',[]
    if len(matches)>1:return 'ambiguous_target',matches
    if command in ('additem','removeitem','addtolevitem','removefromlevitem'):allowed=set(CATEGORIES)|{'LEVI'}
    elif command in ('addtolevcreature','removefromlevcreature'):allowed={'CREA','NPC_','LEVC'}
    else:allowed=set(CATEGORIES)|{'ACTI','BODY','CONT','CREA','DOOR','LEVC','LEVI','NPC_','STAT'}
    return ('resolved' if matches[0] in allowed else 'invalid_target_type'),matches


def populate(journal,world,out,selected):
    for profile in selected:
        out.execute('INSERT INTO profiles VALUES (?,?,?,?)',tuple(journal.execute('SELECT * FROM profiles WHERE id=?',(profile,)).fetchone()))
        objects={}
        for kind,key in world.execute('SELECT record_type,object_key FROM profile_objects WHERE profile_id=?',(profile,)):
            objects.setdefault(key,[]).append(kind)
        journals={r[0] for r in journal.execute('SELECT quest_key FROM quests WHERE profile_id=?',(profile,))}
        scripts={r[0] for r in journal.execute('SELECT script_key FROM profile_scripts WHERE profile_id=?',(profile,))}
        progress=Progress(f'{profile}: script and dialogue evidence')
        for version,kind,key,topic,plugin,origin,source,context in sources(journal,profile):
            if source is None:
                out.execute('INSERT INTO warnings VALUES (?,?,?,?,?)',(profile,version,None,'source_absent',key));continue
            first=not out.execute('SELECT 1 FROM sources WHERE version_id=?',(version,)).fetchone()
            if first:
                out.execute('INSERT INTO sources VALUES (?,?,?,?,?,?,?)',(version,kind,key,topic,plugin,source,context))
                events,issues=scan(source)
                for event in events:
                    out.execute('INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                        (version,event['line'],event['command'],event['kind'],event['targetKey'],event['receiverKey'],event['recipientKind'],
                         js(event['countLiteral']),js(event['arguments']),js(event['context']),js(event['notes']),event['rawLine']))
                # Parser warnings are source-level and shared through profile_sources.
                for line,code,detail in issues:out.execute('INSERT INTO warnings VALUES (?,?,?,?,?)',(None,version,line,code,detail))
            out.execute('INSERT INTO profile_sources VALUES (?,?,?)',(profile,version,origin))
            for line,target,command,notes in out.execute('SELECT line_number,target_key,command,notes_json FROM events WHERE source_version_id=?',(version,)):
                status,types=resolve((target,command),objects,journals,scripts)
                out.execute('INSERT INTO profile_events VALUES (?,?,?,?,?)',(profile,version,line,status,js(types)))
                if status!='resolved':out.execute('INSERT INTO warnings VALUES (?,?,?,?,?)',(profile,version,line,status,target or 'No simple target token'))
                if notes!='[]':out.execute('INSERT INTO warnings VALUES (?,?,?,?,?)',(profile,version,line,'unverified_arguments',notes))
            progress.tick()
            if progress.count%2000==0:out.commit()
        progress.tick(True)
        out.executemany('INSERT INTO script_attachments VALUES (?,?,?,?,?)',world.execute('''
            SELECT p.profile_id,o.script_key,o.version_id,o.record_type,o.object_key FROM profile_objects p
            JOIN objects o ON o.version_id=p.version_id WHERE p.profile_id=? AND o.script_key IS NOT NULL''',(profile,)))
        out.commit()


def build(journal_database,world_database,output,profiles=None):
    jp=Path(journal_database).resolve();wp=Path(world_database).resolve();output=Path(output).resolve()
    for path in (jp,wp):
        if not path.is_file():raise ExportError(f'Input missing: {path}')
        if output==path or path.is_relative_to(output):raise ExportError('Output must not contain inputs')
    output.mkdir(parents=True,exist_ok=True);lock=output/'build.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:raise ExportError(f'Build lock exists: {lock}') from exc
    os.close(fd)
    try:
        with closing(sqlite3.connect(jp.as_uri()+'?mode=ro',uri=True)) as journal,closing(sqlite3.connect(wp.as_uri()+'?mode=ro',uri=True)) as world:
            journal.row_factory=sqlite3.Row
            for db in (journal,world):
                db.execute('PRAGMA cache_size=-16384');db.execute('PRAGMA temp_store=MEMORY');db.execute('BEGIN')
            jm=metadata(journal);wm=metadata(world)
            if jm.get('schemaVersion')!='1.0.0' or wm.get('schemaVersion')!='1.1.1':raise ExportError('Unsupported journal/world schema')
            if jm.get('snapshotId')!=wm.get('snapshotId'):raise ExportError('Journal/world snapshot mismatch')
            available=[r[0] for r in journal.execute('SELECT id FROM profiles ORDER BY id')];selected=profiles or available
            if not selected or set(selected)-set(available) or len(selected)!=len(set(selected)):raise ExportError('Unknown/duplicate profiles')
            for p in selected:
                if tuple(journal.execute('SELECT * FROM profiles WHERE id=?',(p,)).fetchone())!=world.execute('SELECT * FROM profiles WHERE id=?',(p,)).fetchone():raise ExportError('Journal/world profile mismatch')
            with tempfile.TemporaryDirectory(prefix='.script-evidence-',dir=output) as tmp:
                stage=Path(tmp)/'script-evidence.sqlite'
                with closing(sqlite3.connect(stage)) as out:
                    out.execute('PRAGMA cache_size=-16384');out.execute('PRAGMA temp_store=MEMORY')
                    out.executescript((ROOT/'script_evidence_schema.sql').read_text())
                    meta={'schemaVersion':'1.0.0','builderVersion':'1.0.1','snapshotId':jm['snapshotId'],'profiles':selected,'builtAtUnix':time.time(),
                        'journalBuiltAtUnix':jm['builtAtUnix'],'worldBuiltAtUnix':wm['builtAtUnix'],'commands':sorted(COMMANDS),
                        'coverage':'Lexical MWScript evidence only. No execution, path-condition evaluation, guaranteed rewards, script-call traversal or inferred locations.'}
                    out.executemany('INSERT INTO metadata VALUES (?,?)',[(k,js(v)) for k,v in meta.items()])
                    populate(journal,world,out,selected)
                    print('Checking script evidence integrity...',flush=True)
                    if out.execute('PRAGMA foreign_key_check').fetchone():raise ExportError('Script evidence foreign-key failure')
                    if out.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ExportError('Script evidence integrity failure')
                    out.commit()
                    for table in ('sources','events','profile_events','script_attachments','warnings'):
                        print(f'{table}: {out.execute("SELECT count(*) FROM "+table).fetchone()[0]:,}',flush=True)
                os.replace(stage,output/'script-evidence.sqlite')
            print(f'Script evidence complete: {output/"script-evidence.sqlite"}',flush=True)
            return output/'script-evidence.sqlite'
    finally:lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal-database',type=Path);parser.add_argument('--world-database',type=Path)
    parser.add_argument('--output',type=Path);parser.add_argument('--profile',action='append',choices=['vanilla','tr','tr_arce'])
    args=parser.parse_args(argv)
    try:
        root=load_config(ROOT/'foundation_config.json')[2]
        build(args.journal_database or root/'journal/journal.sqlite',args.world_database or root/'world/world.sqlite',args.output or root/'script-evidence',args.profile);return 0
    except KeyboardInterrupt:
        print('\nCancelled. Previously published evidence unchanged.');return 130
    except (OSError,ValueError,KeyError,sqlite3.Error) as exc:
        print(f'Script evidence build failed: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
