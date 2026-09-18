"""Build static services and directed travel links from foundation + world catalogs."""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from extract_foundation import ROOT, fields, load_config
from export_items import ExportError, decode, unpack
from build_world_catalog import Progress, js

VERSION='1.0.0'
# ESM::NPC::Services; also used by creatures. Unknown bits remain in providers.
SERVICE_FLAGS={
    0x1:('weapons','trade'),0x2:('armor','trade'),0x4:('clothing','trade'),
    0x8:('books','trade'),0x10:('ingredients','trade'),0x20:('lockpicks','trade'),
    0x40:('probes','trade'),0x80:('lights','trade'),0x100:('apparatus','trade'),
    0x200:('repair_tools','trade'),0x400:('miscellaneous','trade'),
    0x800:('spells','service'),0x1000:('magic_items','trade'),
    0x2000:('potions','trade'),0x4000:('training','service'),
    0x8000:('spellmaking','service'),0x10000:('enchanting','service'),0x20000:('repair','service'),
}
KNOWN_BITS=sum(SERVICE_FLAGS)


def actor_services(payload,encoding):
    flags=None; destinations=[]; warnings=[]
    for tag,value,_,_ in fields(payload):
        if tag=='AIDT':
            if len(value)!=12: raise ExportError('AIDT must be 12 bytes')
            flags=unpack('I',bytes(value[8:12]))[0]
        elif tag=='DODT':
            pos=unpack('6f',bytes(value))
            if not all(math.isfinite(v) for v in pos): raise ExportError('Non-finite transport position')
            destinations.append([None,*pos])
        elif tag=='DNAM':
            if not destinations: warnings.append(('orphan_transport_name','DNAM without preceding DODT'))
            else: destinations[-1][0]=decode(bytes(value),encoding) or None
    return flags,destinations,warnings


class CellResolver:
    def __init__(self,rows):
        self.keys={};self.names={}
        for key,name,interior in rows:
            self.keys[key]=bool(interior)
            if name:self.names.setdefault(name.casefold(),[]).append(key)

    def resolve(self,name,x,y):
        if not name:
            key=f'exterior:{math.floor(x/8192)},{math.floor(y/8192)}'
            return key,'resolved' if key in self.keys else 'implicit_exterior'
        name=name.casefold();interior='interior:'+name
        if interior in self.keys:return interior,'resolved'
        matches=self.names.get(name,[])
        if len(matches)==1:return matches[0],'resolved'
        # Do not guess among multiple exterior cells with the same display name.
        return None,'ambiguous_name' if matches else 'missing_cell'


def metadata(db):
    return {k:json.loads(v) for k,v in db.execute('SELECT key,value FROM metadata')}


def placements(world,profile,key):
    # Start from the object index, not a scan of millions of profile placements.
    return world.execute('''SELECT v.version_id,v.reference_key,v.cell_key,v.x,v.y,v.z,v.details,v.plugin
        FROM placements v INDEXED BY placement_item CROSS JOIN profile_placements p
        ON p.profile_id=? AND p.reference_key=v.reference_key AND p.version_id=v.version_id
        WHERE v.object_key=?''',(profile,key))


def populate(source,world,out,profiles,encoding):
    for bit,(code,kind) in SERVICE_FLAGS.items():out.execute('INSERT INTO service_flags VALUES (?,?,?)',(bit,code,kind))
    for profile in profiles:
        out.execute('INSERT INTO profiles VALUES (?,?,?,?)',world.execute('SELECT * FROM profiles WHERE id=?',(profile,)).fetchone())
        out.executemany('INSERT INTO cells VALUES (?,?,?,?,?,?,?,?)',world.execute('''SELECT profile_id,cell_key,name,interior,grid_x,grid_y,region_key,synthetic
            FROM cells WHERE profile_id=? AND deleted=0''',(profile,)))
        resolver=CellResolver(out.execute('SELECT cell_key,name,interior FROM cells WHERE profile_id=?',(profile,)))
        progress=Progress(f'{profile}: actor service definitions and transport destinations')
        for version,key,kind,name,plugin,script,origin,stats in world.execute('''
            SELECT o.version_id,o.object_key,o.record_type,o.name,o.plugin,o.script_key,p.origin_plugin,a.details
            FROM profile_objects p JOIN objects o ON o.version_id=p.version_id
            JOIN actors a ON a.version_id=o.version_id WHERE p.profile_id=?''',(profile,)):
            row=source.execute('SELECT payload FROM record_versions WHERE id=?',(version,)).fetchone()
            if row is None:raise ExportError(f'Missing foundation actor revision {version}')
            flags,destinations,issues=actor_services(row[0],encoding)
            progress.tick()
            for code,detail in issues:out.execute('INSERT INTO warnings VALUES (?,?,?,?)',(profile,code,key,detail))
            if flags and flags&~KNOWN_BITS:
                out.execute('INSERT INTO warnings VALUES (?,?,?,?)',(profile,'unknown_service_bits',key,js({'servicesRaw':flags,'unknownBits':flags&~KNOWN_BITS})))
            if not (flags is not None and flags&KNOWN_BITS) and not destinations:continue
            out.execute('INSERT OR IGNORE INTO providers VALUES (?,?,?,?,?,?,?,?,?)',
                (version,key,kind,name,plugin,script,flags,None if flags is None else flags&~KNOWN_BITS,stats))
            out.execute('INSERT INTO profile_providers VALUES (?,?,?,?)',(profile,key,version,origin))
            for bit in SERVICE_FLAGS:
                if flags is not None and flags&bit:out.execute('INSERT OR IGNORE INTO provider_services VALUES (?,?)',(version,bit))
            for i,dest in enumerate(destinations):
                out.execute('INSERT OR IGNORE INTO transport_destinations VALUES (?,?,?,?,?,?,?,?,?)',(version,i,*dest))
                cell,status=resolver.resolve(*dest[:3])
                out.execute('INSERT INTO profile_destinations VALUES (?,?,?,?,?)',(profile,version,i,cell,status))
                if status!='resolved':out.execute('INSERT INTO warnings VALUES (?,?,?,?)',(profile,'transport_'+status,key,js({'entryIndex':i,'cellName':dest[0],'cellKey':cell})))
            found=False
            for pv,ref,cell,x,y,z,details,placement_plugin in placements(world,profile,key):
                found=True
                out.execute('INSERT INTO provider_locations VALUES (?,?,?,?,?,?,?,?)',(profile,ref,pv,version,cell,x,y,z))
            if not found:
                out.execute('INSERT INTO warnings VALUES (?,?,?,?)',(profile,'provider_without_direct_placement',key,'May be spawned by a list or script; no availability inferred'))
        progress.tick(True);out.commit()
        progress=Progress(f'{profile}: directed teleport doors')
        for (key,) in world.execute("SELECT object_key FROM profile_objects WHERE profile_id=? AND record_type='DOOR'",(profile,)):
            for pv,ref,cell,x,y,z,details,plugin in placements(world,profile,key):
                progress.tick()
                detail=json.loads(details);dest=detail.get('doorDestination')
                if not dest:continue
                pos=dest['position'];rot=dest['rotation'];name=dest['cellName']
                if len(pos)!=3 or len(rot)!=3 or not all(math.isfinite(v) for v in (*pos,*rot)):
                    raise ExportError(f'Invalid door destination {ref}')
                out.execute('INSERT OR IGNORE INTO door_links VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (pv,ref,key,plugin,cell,name,*pos,*rot,x,y,z,details))
                target,status=resolver.resolve(name,*pos[:2])
                out.execute('INSERT INTO profile_door_links VALUES (?,?,?,?)',(profile,pv,target,status))
                if status!='resolved':out.execute('INSERT INTO warnings VALUES (?,?,?,?)',(profile,'door_'+status,ref,js({'cellName':name,'cellKey':target})))
        progress.tick(True);out.commit()


def validate(out):
    print('Checking service and travel links...',flush=True)
    if out.execute('PRAGMA foreign_key_check').fetchone():raise ExportError('Service catalog foreign-key failure')
    for table in ('profile_destinations','profile_door_links'):
        key='cell_key' if table=='profile_destinations' else 'to_cell_key'
        if out.execute(f'''SELECT 1 FROM {table} d LEFT JOIN cells c
            ON c.profile_id=d.profile_id AND c.cell_key=d.{key}
            WHERE d.status='resolved' AND c.cell_key IS NULL LIMIT 1''').fetchone():
            raise ExportError('Resolved destination missing from cells')
    if out.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ExportError('Service database integrity failure')


def build(database,world_database,output,profiles=None):
    database=Path(database).resolve();world_database=Path(world_database).resolve();output=Path(output).resolve()
    for path in (database,world_database):
        if not path.is_file():raise ExportError(f'Input database missing: {path}')
        if path==output or path.is_relative_to(output):raise ExportError('Output must not contain input databases')
    output.mkdir(parents=True,exist_ok=True);lock=output/'build.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:raise ExportError(f'Build lock exists: {lock}') from exc
    os.close(fd)
    try:
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(world_database.as_uri()+'?mode=ro',uri=True)) as world:
            for db in (source,world):
                db.execute('PRAGMA cache_size=-16384');db.execute('PRAGMA temp_store=MEMORY');db.execute('BEGIN')
            fm=metadata(source);wm=metadata(world)
            if fm.get('schemaVersion')!=1 or wm.get('schemaVersion') not in ('1.1.0','1.1.1'):
                raise ExportError('Unsupported input schema; rebuild world catalog with the current builder')
            if not fm.get('snapshotId') or fm['snapshotId']!=wm.get('snapshotId'):raise ExportError('Foundation/world snapshot mismatch')
            available=[r[0] for r in world.execute('SELECT id FROM profiles ORDER BY id')];selected=profiles or available
            if not selected or set(selected)-set(available) or len(selected)!=len(set(selected)):raise ExportError('Unknown/duplicate profiles')
            for profile in selected:
                if source.execute('SELECT * FROM profiles WHERE id=?',(profile,)).fetchone()!=world.execute('SELECT * FROM profiles WHERE id=?',(profile,)).fetchone():
                    raise ExportError(f'Profile mismatch: {profile}')
            with tempfile.TemporaryDirectory(prefix='.services-',dir=output) as temp:
                stage=Path(temp)/'services.sqlite'
                with closing(sqlite3.connect(stage)) as out:
                    out.execute('PRAGMA cache_size=-16384');out.execute('PRAGMA temp_store=MEMORY')
                    out.executescript((ROOT/'services_schema.sql').read_text())
                    meta={'schemaVersion':VERSION,'snapshotId':fm['snapshotId'],'profiles':selected,'builtAtUnix':time.time(),
                        'worldSchemaVersion':wm['schemaVersion'],'worldBuiltAtUnix':wm.get('builtAtUnix'),
                        'coverage':'Static service flags, actor destinations, and teleport doors. No dialogue/script evaluation, prices, walkability, route safety, merchant stock, or pathfinding.'}
                    out.executemany('INSERT INTO metadata VALUES (?,?)',[(k,js(v)) for k,v in meta.items()])
                    populate(source,world,out,selected,fm['encoding']);validate(out);out.commit()
                    for table in ('providers','provider_services','transport_destinations','provider_locations','door_links','profile_door_links','travel_edges','warnings'):
                        print(f'{table}: {out.execute("SELECT count(*) FROM "+table).fetchone()[0]:,}',flush=True)
                os.replace(stage,output/'services.sqlite')
            print(f'Services catalog complete: {output/"services.sqlite"}',flush=True)
            return output/'services.sqlite'
    finally:lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path,help='Foundation database')
    parser.add_argument('--world-database',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--profile',action='append',choices=['vanilla','tr','tr_arce'])
    args=parser.parse_args(argv)
    try:
        root=load_config(ROOT/'foundation_config.json')[2]
        build(args.database or root/'game-data.sqlite',args.world_database or root/'world/world.sqlite',args.output or root/'services',args.profile)
        return 0
    except KeyboardInterrupt:
        print('\nCancelled. Previously published services database unchanged.');return 130
    except (OSError,ValueError,KeyError,sqlite3.Error) as exc:
        print(f'Services build failed: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
