"""Read script acquisition evidence with source context and explicit result limits."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from extract_foundation import ROOT,load_config
from build_acquisition_index import metadata


def item_evidence(db,profile,target,limit=30):
    db.row_factory=sqlite3.Row
    rows=db.execute('''SELECT e.*,p.target_status,p.target_types_json,s.kind AS source_kind,s.source_key,s.topic_key,s.plugin,
        s.dialogue_context_json,q.origin_plugin FROM events e INDEXED BY event_target
        CROSS JOIN profile_events p ON p.profile_id=? AND p.source_version_id=e.source_version_id AND p.line_number=e.line_number
        JOIN sources s ON s.version_id=e.source_version_id
        JOIN profile_sources q ON q.profile_id=p.profile_id AND q.version_id=s.version_id
        WHERE e.target_key=? ORDER BY e.source_version_id,e.line_number LIMIT ?''',(profile,target.casefold(),limit+1)).fetchall()
    truncated=len(rows)>limit;results=[]
    for row in rows[:limit]:
        r=dict(row)
        for name in list(r):
            if name.endswith('_json'):
                value=r.pop(name);r[name[:-5]]=json.loads(value) if value is not None else None
        attachments=[dict(a) for a in db.execute('SELECT object_version_id,record_type,object_key FROM script_attachments WHERE profile_id=? AND script_key=? ORDER BY object_version_id LIMIT 101',(profile,r['source_key']))] if r['source_kind']=='script' else []
        r['scriptAttachments']=attachments[:100]
        r['attachmentsTruncated']=len(attachments)>100
        results.append(r)
    return {'profile':profile,'targetKey':target.casefold(),'truncated':truncated,'limit':limit,
        'scope':'Source command evidence, not guaranteed acquisition. Removals and control commands remain distinguished.', 'events':results}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path);parser.add_argument('--profile',default='tr',choices=['vanilla','tr','tr_arce'])
    group=parser.add_mutually_exclusive_group();group.add_argument('--item');group.add_argument('--warnings',action='store_true')
    parser.add_argument('--limit',type=int,default=30);args=parser.parse_args(argv)
    if not 1<=args.limit<=1000:parser.error('--limit must be 1..1000')
    path=args.database or load_config(ROOT/'foundation_config.json')[2]/'script-evidence/script-evidence.sqlite'
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        if not db.execute('SELECT 1 FROM profiles WHERE id=?',(args.profile,)).fetchone():parser.error('Profile absent from evidence build')
        warning_sql='''FROM warnings w WHERE w.profile_id=? OR (w.profile_id IS NULL AND EXISTS
            (SELECT 1 FROM profile_sources s WHERE s.profile_id=? AND s.version_id=w.source_version_id))'''
        if args.item:result=item_evidence(db,args.profile,args.item,args.limit)
        elif args.warnings:result=[dict(r) for r in db.execute('SELECT w.* '+warning_sql+' LIMIT ?',(args.profile,args.profile,args.limit))]
        else:result={'metadata':metadata(db),'profile':args.profile,
            'events':db.execute('SELECT count(*) FROM profile_events WHERE profile_id=?',(args.profile,)).fetchone()[0],
            'warnings':[dict(r) for r in db.execute('SELECT code,count(*) AS count '+warning_sql+' GROUP BY code',(args.profile,args.profile))]}
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
