"""Build normalized, indexed world catalogs from an existing foundation database.

SQLite output stays on A: by default. No inventory/leveled-list paths are expanded.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import math
import os
from pathlib import Path
import sqlite3
import struct
import tempfile
import time

from extract_foundation import ROOT, fields, load_config
from export_items import ATTRIBUTES, SKILLS, CATEGORIES, ExportError, decode, unpack

VERSION='1.1.1'
ITEM_TARGET_TYPES=set(CATEGORIES)|{'LEVI'}
OBJECT_TYPES=set(CATEGORIES)|{'ACTI','STAT','BODY','DOOR','CONT','NPC_','CREA','LEVI','LEVC'}


def js(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def text(value,encoding):
    return decode(bytes(value),encoding)


def scalar(data,key,fmt,default=None):
    return unpack(fmt,bytes(data[key]))[0] if key in data else default


def finite(value):
    if value is not None and not math.isfinite(value):
        raise ExportError('Non-finite number in world data')
    return value


class Progress:
    def __init__(self,label):
        self.label=label; self.start=self.last=time.monotonic(); self.count=0
        print(label,flush=True)

    def tick(self,force=False):
        if not force: self.count+=1
        now=time.monotonic()
        if force or now-self.last>=3:
            print(f'  {self.count:,} rows | {now-self.start:.0f}s',flush=True)
            self.last=now


def actor_details(kind,data):
    raw=bytes(data['NPDT']); flags=scalar(data,'FLAG','I',0)
    if kind=='NPC_':
        if len(raw)==12:
            level,disposition,reputation,rank,gold=unpack('h3B3xi',raw)
            stats={'attributes':None,'skills':None,'health':None,'magicka':None,'fatigue':None}
        elif len(raw)==52:
            values=unpack('h8B27Bx3H3Bxi',raw)
            level=values[0];disposition,reputation,rank,gold=values[39:43]
            stats={'attributes':dict(zip(ATTRIBUTES,values[1:9])),'skills':dict(zip(SKILLS,values[9:36])),
                   'health':values[36],'magicka':values[37],'fatigue':values[38]}
        else:
            raise ExportError(f'NPC NPDT size {len(raw)}, expected 12 or 52')
        details=stats|{'level':level,'disposition':disposition,'reputation':reputation,'factionRankRaw':rank,
                       'gold':gold,'female':bool(flags&1),'statsLayout':len(raw)}
        respawn,essential,auto=bool(flags&4),bool(flags&2),len(raw)==12
    else:
        values=unpack('24i',raw)
        level=values[1]
        details={'creatureTypeRaw':values[0],'level':level,'attributes':dict(zip(ATTRIBUTES,values[2:10])),
                 'health':values[10],'magicka':values[11],'fatigue':values[12],'soulValue':values[13],
                 'combat':values[14],'magic':values[15],'stealth':values[16],
                 'attacks':[{'min':values[i],'max':values[i+1]} for i in (17,19,21)],'gold':values[23]}
        respawn,essential,auto=bool(flags&2),bool(flags&128),False
    details['flagsRaw']=flags
    details['autocalcFlag']=bool(flags&16) if kind=='NPC_' else None
    # Leave absent AIDT as null, distinguishing stored values from engine defaults.
    if 'AIDT' in data:
        hello,fight,flee,alarm,services=unpack('B x 3B 3x I',bytes(data['AIDT']))
        details['ai']={'hello':hello,'fight':fight,'flee':flee,'alarm':alarm,'servicesRaw':services}
    else: details['ai']=None
    return level,respawn,essential,auto,details


def decode_object(out,version,tag,key,editor,plugin,payload,encoding):
    fs=[(k,bytes(v)) for k,v,_,_ in fields(payload)]; data=dict(fs)
    txt=lambda k: text(data[k],encoding) if k in data else ''
    out.execute('INSERT INTO objects VALUES (?,?,?,?,?,?,?,?)',
                (version,tag,key,editor,txt('FNAM') or editor,plugin,txt('SCRI').casefold() or None,txt('MODL') or None))
    if tag in ('NPC_','CREA'):
        level,respawn,essential,auto,details=actor_details(tag,data)
        refs=('RNAM','CNAM','ANAM','BNAM','KNAM') if tag=='NPC_' else ('CNAM',)
        details['recordReferences']={k:txt(k).casefold() or None for k in refs}
        out.execute('INSERT INTO actors VALUES (?,?,?,?,?,?,?)',(version,tag,level,respawn,essential,auto,js(details)))
        for i,(_,value) in enumerate((p for p in fs if p[0]=='NPCS')):
            out.execute('INSERT INTO actor_spells VALUES (?,?,?)',(version,i,text(value,encoding).casefold()))
    if tag=='CONT':
        flags=scalar(data,'FLAG','I',0)
        out.execute('INSERT INTO containers VALUES (?,?,?,?,?)',
                    (version,finite(scalar(data,'CNDT','f',0)),bool(flags&1),bool(flags&2),flags))
    if tag in ('NPC_','CREA','CONT'):
        for i,(_,value) in enumerate(p for p in fs if p[0]=='NPCO'):
            if len(value)<5: raise ExportError('Short NPCO')
            count=unpack('i',value[:4])[0]; target=text(value[4:],encoding).casefold()
            out.execute('INSERT INTO inventories VALUES (?,?,?,?,?,?)',(version,i,target,count,abs(count),count<0))
    if tag in ('LEVI','LEVC'):
        chance=scalar(data,'NNAM','B',0);flags=scalar(data,'DATA','I',0)
        out.execute('INSERT INTO leveled_lists VALUES (?,?,?,?)',(version,tag,chance,flags))
        expected=scalar(data,'INDX','I',0); target_tag='INAM' if tag=='LEVI' else 'CNAM'
        pending=None; count=0
        for field,value in fs:
            if field==target_tag:
                if pending is not None: raise ExportError('Leveled entry missing level')
                pending=text(value,encoding).casefold()
            elif field=='INTV' and pending is not None:
                out.execute('INSERT INTO leveled_entries VALUES (?,?,?,?)',(version,count,pending,unpack('h',value)[0]))
                pending=None;count+=1
        if pending is not None or count!=expected: raise ExportError('Leveled-list count/level mismatch')


def header_fields(payload):
    for key,value,_,_ in fields(payload):
        if key in ('FRMR','MVRF'): break
        yield key,bytes(value)


def cell_header(previous,payload,encoding,version,plugin):
    data=dict(header_fields(payload)); flags,x,y=unpack('Iii',data['DATA'])
    name=text(data.get('NAME',b''),encoding)
    interior=bool(flags&1); key='interior:'+name.casefold() if interior else f'exterior:{x},{y}'
    details=dict(previous or {})
    details.update(flagsRaw=flags,recordVersionId=version,winningPlugin=plugin)
    sources=dict(details.get('fieldSources',{}))
    for field in ('RGNN','AMBI','WHGT','INTV','NAM5'):
        if field not in data: continue
        sources[field]={'recordVersionId':version,'plugin':plugin}
        if field=='RGNN': details['regionKey']=text(data[field],encoding).casefold() or None
        elif field=='AMBI':
            ambient,sunlight,fog,density=unpack('IIIf',data[field])
            details['ambient']={'ambientRaw':ambient,'sunlightRaw':sunlight,'fogRaw':fog,'fogDensity':finite(density)}
        elif field in ('WHGT','INTV'):
            details['waterHeight']=finite(unpack('f' if field=='WHGT' else 'i',data[field])[0])
        else: details['mapColorRaw']=unpack('I',data[field])[0]
    details['fieldSources']=sources
    return key,name or None,interior,None if interior else x,None if interior else y,details.get('regionKey'), 'DELE' in data,details


def decode_placement(payload,encoding):
    data={k:bytes(v) for k,v,_,_ in fields(payload)}
    txt=lambda k: text(data[k],encoding).casefold() or None if k in data else None
    pos=unpack('6f',data['DATA']) if 'DATA' in data else (None,)*6
    for value in pos: finite(value)
    count=scalar(data,'NAM9','i',1)
    detail={'rotation':list(pos[3:]),'scaleRaw':finite(scalar(data,'XSCL','f',1)),
            'ownershipGlobal':txt('BNAM'),'factionRankRaw':scalar(data,'INDX','i',-2),
            'lockLevelRaw':scalar(data,'FLTV','i',0),'keyId':txt('KNAM'),'trapId':txt('TNAM'),
            'soulId':txt('XSOL'),'enchantmentCharge':finite(scalar(data,'XCHG','f',-1)),
            'itemChargeOrConditionRaw':scalar(data,'INTV','i',-1),
            'referenceBlockedRaw':scalar(data,'UNAM','b',-1)}
    if 'DODT' in data:
        dest=unpack('6f',data['DODT'])
        for value in dest: finite(value)
        detail['doorDestination']={'cellName':text(data.get('DNAM',b''),encoding) or None,
                                  'position':list(dest[:3]),'rotation':list(dest[3:])}
    else: detail['doorDestination']=None
    return (*pos[:3],count,txt('ANAM'),txt('CNAM'),js(detail))


def cell_revisions(source,profile):
    # Walk indexed plugin order explicitly; do not sort multi-megabyte CELL BLOBs
    # in SQLite temporary storage across a whole profile.
    for plugin_id,plugin in source.execute('''SELECT p.id,p.name FROM profile_plugins pp
        JOIN plugins p ON p.id=pp.plugin_id WHERE pp.profile_id=? ORDER BY pp.load_order''',(profile,)):
        for version,key,payload in source.execute('''SELECT id,record_key,payload FROM record_versions
            WHERE plugin_id=? AND record_type='CELL' ORDER BY ordinal''',(plugin_id,)):
            yield version,key,payload,plugin


def populate(source,out,selected,encoding):
    marks=','.join('?' for _ in selected)
    for p in source.execute(f'SELECT id,world,version,arce FROM profiles WHERE id IN ({marks})',selected):
        out.execute('INSERT INTO profiles VALUES (?,?,?,?)',p)
    # Decode shared object revisions once, even when several profiles use them.
    for profile in selected:
        progress=Progress(f'{profile}: object definitions and inventories')
        sql='''SELECT v.id,v.record_type,v.record_key,v.display_id,p.name,o.name,v.payload
        FROM live_records r JOIN record_versions v ON v.id=r.version_id JOIN plugins p ON p.id=v.plugin_id
        JOIN plugins o ON o.id=r.origin_plugin_id WHERE r.profile_id=?'''
        # Filter in SQL, never fetch world-cell or landscape BLOBs in this stage.
        tags=sorted(OBJECT_TYPES); query=sql+' AND v.record_type IN ('+','.join('?' for _ in tags)+')'
        for version,tag,key,editor,plugin,origin,payload in source.execute(query,(profile,*tags)):
            try:
                if not out.execute('SELECT 1 FROM objects WHERE version_id=?',(version,)).fetchone():
                    decode_object(out,version,tag,key,editor,plugin,payload,encoding)
                out.execute('INSERT INTO profile_objects VALUES (?,?,?,?,?)',(profile,tag,key,version,origin))
            except (KeyError,ValueError) as exc: raise ExportError(f'{profile} {plugin} {tag} {key}: {exc}') from exc
            progress.tick()
            if progress.count%2000==0:out.commit()
        progress.tick(True);out.commit()
        progress=Progress(f'{profile}: cell headers and inherited optional metadata')
        # Replay cell revisions in profile order to retain explicit optional fields.
        for version,key,payload,plugin in cell_revisions(source,profile):
            old=out.execute('SELECT details,deleted FROM cells WHERE profile_id=? AND cell_key=?',(profile,key)).fetchone()
            previous=json.loads(old[0]) if old and not old[1] else None
            try: ck,name,interior,x,y,region,deleted,detail=cell_header(previous,payload,encoding,version,plugin)
            except (KeyError,ValueError) as exc: raise ExportError(f'{profile} CELL {key}: {exc}') from exc
            out.execute('INSERT OR REPLACE INTO cells VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (profile,ck,name,interior,x,y,region,deleted,False,js(detail)))
            progress.tick()
            if progress.count%1000==0:out.commit()
        progress.tick(True);out.commit()
        progress=Progress(f'{profile}: indexing live placements (no path expansion)')
        for row in source.execute('''SELECT v.id,v.reference_key,v.object_id,v.source_cell_key,v.target_cell_key,
            p.name,v.record_id,v.payload_offset,v.payload_length,v.moved,o.name
            FROM resolved_references r JOIN reference_versions v ON v.id=r.winner_id
            JOIN plugins p ON p.id=v.plugin_id JOIN plugins o ON o.id=r.origin_plugin_id
            WHERE r.profile_id=? AND v.deleted=0''',(profile,)):
            version,ref,obj,src,cell,plugin,record,offset,length,moved,origin=row
            deleted=out.execute('SELECT deleted FROM cells WHERE profile_id=? AND cell_key=?',(profile,cell)).fetchone()
            if deleted and deleted[0]: continue
            if deleted is None:
                if not cell.startswith('exterior:'): raise ExportError(f'Missing interior cell {cell}')
                x,y=map(int,cell.split(':',1)[1].split(','))
                out.execute('INSERT INTO cells VALUES (?,?,?,?,?,?,?,?,?,?)',(profile,cell,None,False,x,y,None,False,True,'{}'))
            out.execute('INSERT OR IGNORE INTO placements(version_id,reference_key,object_key,source_cell_key,cell_key,plugin,record_id,payload_offset,payload_length,moved) VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (version,ref,obj.casefold() if obj else None,src,cell,plugin,record,offset,length,moved))
            out.execute('INSERT INTO profile_placements VALUES (?,?,?,?)',(profile,ref,version,origin))
            progress.tick()
            if progress.count%5000==0:out.commit()
        progress.tick(True);out.commit()
    progress=Progress('Decoding unique placement revisions, one CELL payload at a time')
    previous_record=None; blob=None
    # Indexed record order ensures a CELL BLOB is read once, not once per object.
    for version,record,offset,length in out.execute('SELECT version_id,record_id,payload_offset,payload_length FROM placements ORDER BY record_id,version_id'):
        if record!=previous_record:
            blob=source.execute('SELECT payload FROM record_versions WHERE id=?',(record,)).fetchone()[0]
            previous_record=record
        if offset<0 or length<0 or offset+length>len(blob):raise ExportError(f'Invalid reference slice {version}')
        try: values=decode_placement(memoryview(blob)[offset:offset+length],encoding)
        except (KeyError,ValueError) as exc:raise ExportError(f'Placement revision {version}: {exc}') from exc
        out.execute('UPDATE placements SET x=?,y=?,z=?,count_raw=?,owner_key=?,faction_key=?,details=? WHERE version_id=?',(*values,version))
        progress.tick()
        if progress.count%5000==0:out.commit()
    progress.tick(True);out.commit()


def validate(out):
    print('Checking joins and database integrity...',flush=True)
    last=[time.monotonic()]
    def heartbeat():
        now=time.monotonic()
        if now-last[0]>=3:
            print('  Join/integrity checks still running...',flush=True);last[0]=now
        return 0
    out.set_progress_handler(heartbeat,100000)
    # A missing entry is evidence, not a reason to invent or discard a source row.
    for table,parent_col,kind in [('inventories','holder_version_id','inventory'),('leveled_entries','list_version_id','leveled_entry')]:
        out.execute(f'''INSERT INTO warnings SELECT p.profile_id,?,e.object_key,count(*),'No live world object in profile'
            FROM {table} e JOIN profile_objects p ON p.version_id=e.{parent_col}
            WHERE NOT EXISTS (SELECT 1 FROM profile_objects q WHERE q.profile_id=p.profile_id AND q.object_key=e.object_key)
            GROUP BY p.profile_id,e.object_key''',('unresolved_'+kind,))
        # An existing model part, actor, or other world object is not necessarily
        # a valid inventory/list target. Keep the original entry as evidence.
        item_marks=','.join('?' for _ in ITEM_TARGET_TYPES)
        allowed=f"q.record_type IN ({item_marks})"
        if kind=='leveled_entry':
            allowed=f"((p.record_type='LEVI' AND {allowed}) OR (p.record_type='LEVC' AND q.record_type IN ('CREA','NPC_','LEVC')))"
        out.execute(f'''INSERT INTO warnings
            SELECT p.profile_id,?,e.object_key,count(*),
                'Existing world target has an invalid type for ' || p.record_type || ': ' ||
                (SELECT group_concat(q.record_type, ',') FROM profile_objects q
                 WHERE q.profile_id=p.profile_id AND q.object_key=e.object_key)
            FROM {table} e JOIN profile_objects p ON p.version_id=e.{parent_col}
            WHERE EXISTS (SELECT 1 FROM profile_objects q
                WHERE q.profile_id=p.profile_id AND q.object_key=e.object_key)
            AND NOT EXISTS (SELECT 1 FROM profile_objects q
                WHERE q.profile_id=p.profile_id AND q.object_key=e.object_key AND {allowed})
            GROUP BY p.profile_id,p.record_type,e.object_key''',
            ('invalid_'+kind+'_target',*sorted(ITEM_TARGET_TYPES)))
    out.execute('''INSERT INTO warnings SELECT p.profile_id,'unresolved_placement',v.object_key,count(*),'No live world object in profile'
        FROM profile_placements p JOIN placements v ON v.version_id=p.version_id
        WHERE NOT EXISTS(SELECT 1 FROM profile_objects o WHERE o.profile_id=p.profile_id AND o.object_key=v.object_key)
        GROUP BY p.profile_id,v.object_key''')
    if out.execute('SELECT 1 FROM placements WHERE details IS NULL LIMIT 1').fetchone():raise ExportError('Undecoded placement rows')
    if out.execute('''SELECT 1 FROM profile_placements p JOIN placements v ON v.version_id=p.version_id
        LEFT JOIN cells c ON c.profile_id=p.profile_id AND c.cell_key=v.cell_key WHERE c.cell_key IS NULL OR c.deleted!=0 LIMIT 1''').fetchone():
        raise ExportError('Placement points to absent/deleted cell')
    if out.execute('PRAGMA foreign_key_check').fetchone():raise ExportError('World catalog foreign-key failure')
    out.commit()
    if out.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ExportError('World catalog integrity failure')
    out.set_progress_handler(None,0)


def build(database,output,profiles=None):
    database=database.resolve();output=output.resolve()
    if not database.is_file():raise ExportError(f'Foundation missing: {database}')
    if output==database or database.is_relative_to(output):raise ExportError('World output must not contain the foundation database')
    output.mkdir(parents=True,exist_ok=True)
    lock=output/'build.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:raise ExportError(f'Build lock exists: {lock}; check for an active build before removing a stale lock') from exc
    os.close(fd)
    try:
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as source:
            source.execute('PRAGMA cache_size=-16384');source.execute('PRAGMA temp_store=MEMORY');source.execute('BEGIN')
            meta={k:json.loads(v) for k,v in source.execute('SELECT key,value FROM metadata')}
            if meta.get('schemaVersion')!=1:raise ExportError('Unsupported foundation schema')
            available=[r[0] for r in source.execute('SELECT id FROM profiles ORDER BY id')];selected=profiles or available
            if set(selected)-set(available) or len(selected)!=len(set(selected)):raise ExportError('Unknown/duplicate profile')
            with tempfile.TemporaryDirectory(prefix='.world-',dir=output) as temp:
                stage=Path(temp)/'world.sqlite'
                with closing(sqlite3.connect(stage)) as out:
                    out.execute('PRAGMA cache_size=-32768');out.execute('PRAGMA temp_store=MEMORY')
                    out.executescript((ROOT/'world_schema.sql').read_text())
                    for k,v in {'schemaVersion':VERSION,'snapshotId':meta['snapshotId'],'profiles':selected,'builtAtUnix':time.time(),
                        'coverage':'Static plugin data; no scripts, danger, sale status, auto-calculated actor stats, or paths evaluated'}.items():
                        out.execute('INSERT INTO metadata VALUES (?,?)',(k,js(v)))
                    populate(source,out,selected,meta['encoding']);validate(out)
                    for table in ('objects','actors','containers','inventories','leveled_lists','leveled_entries','cells','placements','profile_placements','warnings'):
                        print(f'{table}: {out.execute("SELECT count(*) FROM "+table).fetchone()[0]:,}',flush=True)
                os.replace(stage,output/'world.sqlite')
            print(f'World catalog complete: {output/"world.sqlite"}',flush=True)
            return output/'world.sqlite'
    finally:lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path);parser.add_argument('--output',type=Path)
    parser.add_argument('--profile',action='append',choices=['vanilla','tr','tr_arce'])
    args=parser.parse_args(argv)
    try:
        root=load_config(ROOT/'foundation_config.json')[2]
        build(args.database or root/'game-data.sqlite',args.output or root/'world',args.profile)
        return 0
    except KeyboardInterrupt:
        print('\nCancelled. Previously published world database unchanged.');return 130
    except (OSError,ValueError,KeyError,sqlite3.Error) as exc:
        print(f'World build failed: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
