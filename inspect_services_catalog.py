"""Inspect service providers, directed travel links, or grouped warnings."""
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
    group.add_argument('--service',help='Service code, e.g. enchanting, spellmaking, training, potions')
    group.add_argument('--cell',help='Canonical departure cell key')
    group.add_argument('--warnings',action='store_true')
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if not 1<=args.limit<=1000:parser.error('--limit must be 1..1000')
    path=args.database or load_config(ROOT/'foundation_config.json')[2]/'services/services.sqlite'
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        if not db.execute('SELECT 1 FROM profiles WHERE id=?',(args.profile,)).fetchone():parser.error('Profile absent from build')
        if args.service:
            if not db.execute('SELECT 1 FROM service_flags WHERE code=?',(args.service,)).fetchone():parser.error('Unknown service code')
            rows=db.execute('''SELECT p.actor_key,p.name,l.reference_key,l.cell_key,p.version_id
                FROM profile_providers q JOIN providers p ON p.version_id=q.version_id
                JOIN provider_services s ON s.provider_version_id=p.version_id
                JOIN service_flags f ON f.bit=s.service_bit
                LEFT JOIN provider_locations l ON l.profile_id=q.profile_id AND l.provider_version_id=p.version_id
                WHERE q.profile_id=? AND f.code=? LIMIT ?''',(args.profile,args.service,args.limit))
        elif args.cell:
            rows=db.execute('SELECT * FROM travel_edges WHERE profile_id=? AND from_cell_key=? LIMIT ?',
                (args.profile,args.cell.casefold(),args.limit))
        elif args.warnings:
            rows=db.execute('SELECT code,source_key,detail FROM warnings WHERE profile_id=? LIMIT ?',(args.profile,args.limit))
        else:
            print('Metadata:')
            for row in db.execute('SELECT key,value FROM metadata'):print(' ',row['key']+':',row['value'])
            for table in ('profile_providers','provider_locations','profile_destinations','profile_door_links','travel_edges'):
                print(table,db.execute('SELECT count(*) FROM '+table+' WHERE profile_id=?',(args.profile,)).fetchone()[0])
            rows=db.execute('SELECT code,count(*) AS count FROM warnings WHERE profile_id=? GROUP BY code',(args.profile,))
        print(json.dumps([dict(r) for r in rows],indent=2,ensure_ascii=False))


if __name__=='__main__':main()
