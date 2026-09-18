"""Inspect extracted quest definitions, dialogue records, scripts, and warnings."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from extract_foundation import ROOT,load_config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path)
    parser.add_argument('--profile',default='tr',choices=['vanilla','tr','tr_arce'])
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--quest',help='Journal topic editor ID')
    group.add_argument('--topic',help='Dialogue topic editor ID')
    group.add_argument('--script',help='Standalone script editor ID')
    group.add_argument('--warnings',action='store_true')
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if not 1<=args.limit<=1000:parser.error('--limit must be 1..1000')
    path=args.database or load_config(ROOT/'foundation_config.json')[2]/'journal/journal.sqlite'
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        def rows(sql,params=()):return [dict(r) for r in db.execute(sql,params)]
        if not db.execute('SELECT 1 FROM profiles WHERE id=?',(args.profile,)).fetchone():parser.error('Profile absent from build')
        if args.quest:
            params=(args.profile,args.quest.casefold())
            result={'quest':rows('SELECT * FROM quests WHERE profile_id=? AND quest_key=?',params),
                'titles':rows('SELECT * FROM quest_titles WHERE profile_id=? AND topic_key=?',params),
                'entries':rows('SELECT * FROM journal_entries WHERE profile_id=? AND quest_key=? ORDER BY journal_index,info_key LIMIT ?',(*params,args.limit))}
        elif args.topic:
            params=(args.profile,args.topic.casefold())
            responses=rows('''SELECT r.* FROM profile_responses p JOIN responses r ON r.version_id=p.version_id
                WHERE p.profile_id=? AND p.topic_key=? ORDER BY r.info_key LIMIT ?''',(*params,args.limit))
            for r in responses:r['conditions']=rows('SELECT * FROM conditions WHERE response_version_id=? ORDER BY entry_index',(r['version_id'],))
            result={'topic':rows('''SELECT t.*,p.origin_plugin FROM profile_topics p JOIN topics t ON t.version_id=p.version_id
                WHERE p.profile_id=? AND p.topic_key=?''',params),'responses':responses,'ordering':'INFO ID display order only, not engine dialogue selection order'}
        elif args.script:
            result=rows('''SELECT s.*,p.origin_plugin FROM profile_scripts p JOIN scripts s ON s.version_id=p.version_id
                WHERE p.profile_id=? AND p.script_key=?''',(args.profile,args.script.casefold()))
        elif args.warnings:
            result=rows('SELECT * FROM warnings WHERE profile_id=? LIMIT ?',(args.profile,args.limit))
        else:
            result={'metadata':{r['key']:json.loads(r['value']) for r in db.execute('SELECT * FROM metadata')},'profile':args.profile,
                'counts':{table:db.execute('SELECT count(*) FROM '+table+' WHERE profile_id=?',(args.profile,)).fetchone()[0]
                    for table in ('profile_topics','profile_responses','profile_scripts','quests','journal_entries')},
                'warnings':rows('SELECT code,count(*) AS count FROM warnings WHERE profile_id=? GROUP BY code',(args.profile,))}
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
