"""Build a compact reverse inventory/list index; never expand location paths."""
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

VERSION='1.0.0'
NODE_TYPES=set(CATEGORIES)|{'CONT','NPC_','CREA','LEVI','LEVC'}
ITEM_TARGETS=set(CATEGORIES)|{'LEVI'}


def metadata(db):return {k:json.loads(v) for k,v in db.execute('SELECT key,value FROM metadata')}


def populate(world,out,selected):
    for profile in selected:
        out.execute('INSERT INTO profiles VALUES (?,?,?,?)',world.execute('SELECT * FROM profiles WHERE id=?',(profile,)).fetchone())
        # Small definition lookup only; never accumulate placements or paths.
        targets={}
        for tag,key,version in world.execute('SELECT record_type,object_key,version_id FROM profile_objects WHERE profile_id=?',(profile,)):
            targets.setdefault(key,[]).append((tag,version))
        progress=Progress(f'{profile}: acquisition nodes')
        for tag,key,version,origin in world.execute('SELECT record_type,object_key,version_id,origin_plugin FROM profile_objects WHERE profile_id=?',(profile,)):
            if tag not in NODE_TYPES:continue
            if not out.execute('SELECT 1 FROM nodes WHERE version_id=?',(version,)).fetchone():
                name,plugin,script=world.execute('SELECT name,plugin,script_key FROM objects WHERE version_id=?',(version,)).fetchone()
                detail={}
                if tag in ('LEVI','LEVC'):
                    chance,flags=world.execute('SELECT chance_none,flags_raw FROM leveled_lists WHERE version_id=?',(version,)).fetchone()
                    detail={'chanceNone':chance,'flagsRaw':flags}
                elif tag=='CONT':
                    capacity,organic,respawns,flags=world.execute('SELECT capacity,organic,respawns,flags_raw FROM containers WHERE version_id=?',(version,)).fetchone()
                    detail={'capacity':capacity,'organic':bool(organic),'respawns':bool(respawns),'flagsRaw':flags}
                elif tag in ('NPC_','CREA'):
                    respawns,essential,auto,stats=world.execute('SELECT respawns,essential,autocalculated,details FROM actors WHERE version_id=?',(version,)).fetchone()
                    detail={'respawns':bool(respawns),'essential':bool(essential),'autocalculated':bool(auto),'stats':json.loads(stats)}
                out.execute('INSERT INTO nodes VALUES (?,?,?,?,?,?,?)',(version,tag,key,name,plugin,script,js(detail)))
            out.execute('INSERT INTO profile_nodes VALUES (?,?,?,?,?)',(profile,tag,key,version,origin));progress.tick()
        progress.tick(True);out.commit()
        progress=Progress(f'{profile}: inventory and list edges (no path expansion)')
        for tag,key,parent,origin in world.execute("SELECT record_type,object_key,version_id,origin_plugin FROM profile_objects WHERE profile_id=? AND record_type IN ('CONT','NPC_','CREA','LEVI','LEVC')",(profile,)):
            if tag in ('LEVI','LEVC'):
                kind='leveled';allowed={'CREA','NPC_','LEVC'} if tag=='LEVC' else ITEM_TARGETS
                rows=world.execute('SELECT entry_index,object_key,minimum_level FROM leveled_entries WHERE list_version_id=?',(parent,))
            else:
                kind='inventory';allowed=ITEM_TARGETS
                rows=world.execute('SELECT entry_index,object_key,count_raw,quantity,restocking FROM inventories WHERE holder_version_id=?',(parent,))
            for i,target,*values in rows:
                detail={'minimumLevel':values[0]} if kind=='leveled' else {'countRaw':values[0],'quantity':values[1],'restocking':bool(values[2])}
                out.execute('INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?)',(parent,kind,i,target,js(detail)))
                matches=targets.get(target,[])
                status='missing_target' if not matches else 'ambiguous_target' if len(matches)>1 else 'resolved' if matches[0][0] in allowed else 'invalid_target_type'
                target_version=matches[0][1] if status=='resolved' else None
                out.execute('INSERT INTO profile_edges VALUES (?,?,?,?,?,?)',(profile,parent,kind,i,target_version,status))
                progress.tick()
                if progress.count%5000==0:out.commit()
        progress.tick(True);out.commit()


def build(world_database,output,profiles=None):
    path=Path(world_database).resolve();output=Path(output).resolve()
    if not path.is_file():raise ExportError(f'World database missing: {path}')
    if path==output or path.is_relative_to(output):raise ExportError('Output must not contain the world database')
    output.mkdir(parents=True,exist_ok=True);lock=output/'build.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:raise ExportError(f'Build lock exists: {lock}') from exc
    os.close(fd)
    try:
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as world:
            world.execute('PRAGMA cache_size=-16384');world.execute('PRAGMA temp_store=MEMORY');world.execute('BEGIN')
            wm=metadata(world)
            if wm.get('schemaVersion')!='1.1.1':raise ExportError('Expected world schema 1.1.1')
            available=[r[0] for r in world.execute('SELECT id FROM profiles ORDER BY id')];selected=profiles or available
            if not selected or set(selected)-set(available) or len(selected)!=len(set(selected)):raise ExportError('Unknown/duplicate profiles')
            with tempfile.TemporaryDirectory(prefix='.acquisition-',dir=output) as tmp:
                stage=Path(tmp)/'acquisition.sqlite'
                with closing(sqlite3.connect(stage)) as out:
                    out.execute('PRAGMA cache_size=-16384');out.execute('PRAGMA temp_store=MEMORY')
                    out.executescript((ROOT/'acquisition_schema.sql').read_text())
                    meta={'schemaVersion':VERSION,'snapshotId':wm['snapshotId'],'worldSchemaVersion':wm['schemaVersion'],
                        'worldBuiltAtUnix':wm['builtAtUnix'],'worldDatabase':str(path),'profiles':selected,'builtAtUnix':time.time(),
                        'coverage':'Static inventory/list evidence graph. Placements read on demand from world. No scripts, sale status, probabilities, safety or acquisition paths evaluated.'}
                    out.executemany('INSERT INTO metadata VALUES (?,?)',[(k,js(v)) for k,v in meta.items()])
                    populate(world,out,selected)
                    print('Checking edge integrity...',flush=True)
                    last=[time.monotonic()]
                    def heartbeat():
                        now=time.monotonic()
                        if now-last[0]>=3:
                            print('  Edge/integrity checks still running...',flush=True);last[0]=now
                        return 0
                    out.set_progress_handler(heartbeat,100000)
                    out.execute('''INSERT INTO warnings SELECT p.profile_id,p.status,e.target_key,count(*)
                        FROM profile_edges p JOIN edges e USING(parent_version_id,kind,entry_index)
                        WHERE p.status!='resolved' GROUP BY p.profile_id,p.status,e.target_key''')
                    if out.execute('PRAGMA foreign_key_check').fetchone():raise ExportError('Acquisition foreign-key failure')
                    if out.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ExportError('Acquisition integrity failure')
                    out.commit()
                    out.set_progress_handler(None,0)
                    for table in ('nodes','edges','profile_nodes','profile_edges','warnings'):
                        print(f'{table}: {out.execute("SELECT count(*) FROM "+table).fetchone()[0]:,}',flush=True)
                os.replace(stage,output/'acquisition.sqlite')
            print(f'Acquisition index complete: {output/"acquisition.sqlite"}',flush=True)
            return output/'acquisition.sqlite'
    finally:lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-database',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--profile',action='append',choices=['vanilla','tr','tr_arce'])
    args=parser.parse_args(argv)
    try:
        root=load_config(ROOT/'foundation_config.json')[2]
        build(args.world_database or root/'world/world.sqlite',args.output or root/'acquisition',args.profile);return 0
    except KeyboardInterrupt:
        print('\nCancelled. Previous acquisition index unchanged.');return 130
    except (OSError,ValueError,KeyError,sqlite3.Error) as exc:
        print(f'Acquisition build failed: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
