"""Extract quest journals, dialogue conditions, and script sources for all profiles.

Run locally in VS Code. No script execution or character-completion inference.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import math
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import json

from extract_foundation import ROOT, fields, load_config
from export_items import ExportError, decode, unpack
from build_world_catalog import Progress, js

VERSION='1.0.0'
TOPIC_TYPES={0:'topic',1:'voice',2:'greeting',3:'persuasion',4:'journal'}
QUEST_MARKERS={'QSTN':'name','QSTF':'finished','QSTR':'restart'}


def text(data,tag,encoding,default=None):
    return decode(data[tag],encoding) if tag in data else default


def key(data,tag,encoding):
    value=text(data,tag,encoding)
    return value.casefold() if value else None


def parse_condition(raw,value_tag,value,encoding):
    rule=decode(raw,encoding)
    status=[];value_type=None;number=None
    if len(rule)<5:status.append('short_rule')
    else:
        if rule[0] not in '0123456789':status.append('invalid_slot')
        if rule[1] not in '123456789ABC':status.append('unknown_kind')
        if rule[4] not in '012345':status.append('invalid_comparison')
    if value_tag is None:status.append('missing_value')
    elif len(value)!=4:status.append('invalid_value_size')
    else:
        value_type='integer' if value_tag=='INTV' else 'float'
        number=unpack('i' if value_tag=='INTV' else 'f',value)[0]
        if isinstance(number,float) and not math.isfinite(number):
            status.append('nonfinite_value');number=None
    # Header characters remain raw: syntax extraction is not engine validation.
    return (rule,raw.hex(),rule[:1] or None,rule[1:2] or None,rule[2:4] or None,
            rule[4:5] or None,rule[5:] if len(rule)>=5 else None,value_type,
            js(number) if number is not None else None,value_tag,value.hex() if value is not None else None,
            ','.join(status) if status else 'structural_only')


def decode_response(payload,encoding):
    fs=[(k,bytes(v)) for k,v,_,_ in fields(payload)];data=dict(fs);issues=[]
    if 'DATA' in data:
        if len(data['DATA'])!=12:raise ExportError('INFO DATA must be 12 bytes')
        stats=unpack('ii3bx',data['DATA'])
    else:
        stats=(None,)*5;issues.append(('missing_info_data','No DATA subrecord; values remain null'))
    conditions=[];pending=None;quest='none';markers=[]
    for tag,value in fs:
        if pending is not None:
            if tag in ('INTV','FLTV'):
                conditions.append(parse_condition(pending,tag,value,encoding));pending=None;continue
            conditions.append(parse_condition(pending,None,None,encoding));pending=None
        if tag=='SCVR':pending=value
        elif tag in ('INTV','FLTV'):issues.append(('orphan_condition_value',f'{tag} without SCVR'))
        elif tag in QUEST_MARKERS:
            quest=QUEST_MARKERS[tag];markers.append(tag)
    if pending is not None:conditions.append(parse_condition(pending,None,None,encoding))
    if len(markers)>1:issues.append(('multiple_quest_markers',js(markers)))
    for i,c in enumerate(conditions):
        if c[-1]!='structural_only':issues.append(('condition_structure',js({'entryIndex':i,'status':c[-1]})))
    faction=key(data,'FNAM',encoding)
    values=(key(data,'PNAM',encoding),key(data,'NNAM',encoding),*stats,
        key(data,'ONAM',encoding),key(data,'RNAM',encoding),key(data,'CNAM',encoding),faction,
        faction=='ffff',key(data,'DNAM',encoding),text(data,'ANAM',encoding),text(data,'SNAM',encoding),
        text(data,'NAME',encoding,''),text(data,'BNAM',encoding),quest)
    return values,conditions,issues


def decode_script(payload,encoding):
    data={k:bytes(v) for k,v,_,_ in fields(payload)};issues=[]
    header=data.get('SCHD',b'')
    if len(header)!=52:raise ExportError('SCPT SCHD must be 52 bytes')
    shorts,longs,floats,bytecode_size,variable_size=unpack('5I',header[32:])
    actual_bytecode=len(data.get('SCDT',b''));variables=data.get('SCVR',b'')
    names=[decode(v,encoding) for v in variables.rstrip(b'\0').split(b'\0')] if variables else []
    if bytecode_size!=actual_bytecode:issues.append(('script_bytecode_size_mismatch',f'{bytecode_size} declared; {actual_bytecode} stored'))
    if variable_size!=len(variables):issues.append(('script_variable_size_mismatch',f'{variable_size} declared; {len(variables)} stored'))
    if 'SCTX' not in data:issues.append(('script_source_absent','No SCTX; source remains null, bytecode remains in foundation'))
    return (text(data,'SCTX',encoding),shorts,longs,floats,bytecode_size,actual_bytecode,variable_size,len(variables),js(names)),issues


def records(source,profile,tag):
    return source.execute('''SELECT v.id,v.record_key,v.display_id,p.name,o.name,v.payload
        FROM resolved_records r JOIN record_versions v ON v.id=r.winner_id
        JOIN plugins p ON p.id=v.plugin_id JOIN plugins o ON o.id=r.origin_plugin_id
        WHERE r.profile_id=? AND r.record_type=? AND v.deleted=0''',(profile,tag))


def warn(out,profile,tag,key,code,detail):
    out.execute('INSERT INTO warnings VALUES (?,?,?,?,?)',(profile,tag,key,code,detail))


def populate(source,out,profiles,encoding):
    # Cache only small per-revision warning lists; text/payloads are streamed.
    issues_by_version={}
    for profile in profiles:
        out.execute('INSERT INTO profiles VALUES (?,?,?,?)',source.execute('SELECT * FROM profiles WHERE id=?',(profile,)).fetchone())
        for tag,label in [('DIAL','topics'),('INFO','responses and journal stages'),('SCPT','script sources')]:
            progress=Progress(f'{profile}: {label}')
            for version,rkey,editor,plugin,origin,payload in records(source,profile,tag):
                try:
                    if tag=='DIAL':
                        if not out.execute('SELECT 1 FROM topics WHERE version_id=?',(version,)).fetchone():
                            data={k:bytes(v) for k,v,_,_ in fields(payload)}
                            kind=unpack('b',data['DATA'])[0] if len(data.get('DATA',b''))==1 else None
                            out.execute('INSERT INTO topics VALUES (?,?,?,?,?,?)',(version,rkey,editor,kind,TOPIC_TYPES.get(kind,'unknown'),plugin))
                            issues_by_version[version]=[] if kind in TOPIC_TYPES else [('unknown_topic_type',str(kind))]
                        out.execute('INSERT INTO profile_topics VALUES (?,?,?,?)',(profile,rkey,version,origin))
                    elif tag=='INFO':
                        topic,info=json.loads(rkey)
                        if not out.execute('SELECT 1 FROM profile_topics WHERE profile_id=? AND topic_key=?',(profile,topic)).fetchone():
                            warn(out,profile,tag,rkey,'inactive_parent_topic','Parent DIAL absent or deleted; response excluded from profile')
                            progress.tick();continue
                        if not out.execute('SELECT 1 FROM responses WHERE version_id=?',(version,)).fetchone():
                            values,conditions,issues=decode_response(payload,encoding)
                            out.execute('INSERT INTO responses VALUES ('+','.join('?' for _ in range(23))+')',(version,topic,info,editor,*values,plugin))
                            for i,c in enumerate(conditions):out.execute('INSERT INTO conditions VALUES ('+','.join('?' for _ in range(14))+')',(version,i,*c))
                            if issues:issues_by_version[version]=issues
                        out.execute('INSERT INTO profile_responses VALUES (?,?,?,?,?)',(profile,topic,info,version,origin))
                    else:
                        if not out.execute('SELECT 1 FROM scripts WHERE version_id=?',(version,)).fetchone():
                            values,issues=decode_script(payload,encoding)
                            out.execute('INSERT INTO scripts VALUES ('+','.join('?' for _ in range(13))+')',(version,rkey,editor,plugin,*values))
                            if issues:issues_by_version[version]=issues
                        out.execute('INSERT INTO profile_scripts VALUES (?,?,?,?)',(profile,rkey,version,origin))
                    for code,detail in issues_by_version.get(version,[]):warn(out,profile,tag,rkey,code,detail)
                except (ValueError,KeyError) as exc:raise ExportError(f'{profile} {plugin} {tag} {rkey}: {exc}') from exc
                progress.tick()
                if progress.count%2000==0:out.commit()
            progress.tick(True);out.commit()


def validate(out):
    print('Checking journal links and database integrity...',flush=True)
    last=[time.monotonic()]
    def heartbeat():
        now=time.monotonic()
        if now-last[0]>=3:
            print('  Journal link/integrity checks still running...',flush=True);last[0]=now
        return 0
    out.set_progress_handler(heartbeat,100000)
    # Make repeated validation safe; extraction warnings remain intact.
    out.execute("DELETE FROM warnings WHERE code IN ('journal_title_missing','journal_title_ambiguous','info_topic_type_mismatch')")
    out.execute('''INSERT INTO warnings SELECT profile_id,'DIAL',quest_key,
        CASE WHEN title_count=0 THEN 'journal_title_missing' ELSE 'journal_title_ambiguous' END,
        'Distinct nonempty title candidates: ' || title_count
        FROM quests WHERE title_count!=1''')
    out.execute('''INSERT INTO warnings SELECT p.profile_id,'INFO',p.topic_key || '/' || p.info_key,
        'info_topic_type_mismatch','INFO type ' || r.type_raw || '; DIAL type ' || t.type_raw
        FROM profile_responses p JOIN responses r ON r.version_id=p.version_id
        JOIN profile_topics q ON q.profile_id=p.profile_id AND q.topic_key=p.topic_key
        JOIN topics t ON t.version_id=q.version_id WHERE r.type_raw!=t.type_raw''')
    if out.execute('PRAGMA foreign_key_check').fetchone():raise ExportError('Journal foreign-key failure')
    if out.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ExportError('Journal integrity failure')
    out.commit()
    out.set_progress_handler(None,0)


def build(database,output,profiles=None):
    database=Path(database).resolve();output=Path(output).resolve()
    if not database.is_file():raise ExportError(f'Foundation missing: {database}')
    if output==database or database.is_relative_to(output):raise ExportError('Output must not contain the foundation')
    output.mkdir(parents=True,exist_ok=True);lock=output/'build.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError as exc:raise ExportError(f'Build lock exists: {lock}') from exc
    os.close(fd)
    try:
        with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as source:
            source.execute('PRAGMA cache_size=-16384');source.execute('PRAGMA temp_store=MEMORY');source.execute('BEGIN')
            meta={k:json.loads(v) for k,v in source.execute('SELECT key,value FROM metadata')}
            if meta.get('schemaVersion')!=1:raise ExportError('Unsupported foundation schema')
            available=[r[0] for r in source.execute('SELECT id FROM profiles ORDER BY id')];selected=profiles or available
            if not selected or set(selected)-set(available) or len(selected)!=len(set(selected)):raise ExportError('Unknown/duplicate profile')
            with tempfile.TemporaryDirectory(prefix='.journal-',dir=output) as tmp:
                stage=Path(tmp)/'journal.sqlite'
                with closing(sqlite3.connect(stage)) as out:
                    out.execute('PRAGMA cache_size=-16384');out.execute('PRAGMA temp_store=MEMORY')
                    out.executescript((ROOT/'journal_schema.sql').read_text())
                    metadata={'schemaVersion':VERSION,'snapshotId':meta['snapshotId'],'profiles':selected,'encoding':meta['encoding'],
                        'builtAtUnix':time.time(),'coverage':'Static journal markers, dialogue filters, raw conditions and script sources. No dialogue order replay, condition evaluation, script execution, quest availability or character completion.'}
                    out.executemany('INSERT INTO metadata VALUES (?,?)',[(k,js(v)) for k,v in metadata.items()])
                    populate(source,out,selected,meta['encoding']);validate(out)
                    for table in ('topics','responses','conditions','scripts','quests','journal_entries','warnings'):
                        print(f'{table}: {out.execute("SELECT count(*) FROM "+table).fetchone()[0]:,}',flush=True)
                    for row in out.execute('SELECT profile_id,code,count(*) FROM warnings GROUP BY profile_id,code'):
                        print('  warning:',*row,flush=True)
                os.replace(stage,output/'journal.sqlite')
            print(f'Journal catalog complete: {output/"journal.sqlite"}',flush=True)
            return output/'journal.sqlite'
    finally:lock.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--profile',action='append',choices=['vanilla','tr','tr_arce'])
    args=parser.parse_args(argv)
    try:
        root=load_config(ROOT/'foundation_config.json')[2]
        build(args.database or root/'game-data.sqlite',args.output or root/'journal',args.profile);return 0
    except KeyboardInterrupt:
        print('\nCancelled. Previously published journal database unchanged.');return 130
    except (OSError,ValueError,KeyError,sqlite3.Error) as exc:
        print(f'Journal build failed: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
