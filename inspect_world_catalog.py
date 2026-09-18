"""Read normalized world counts or direct inventory sources without path expansion."""
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
    parser.add_argument('--item',help='Item editor ID; shows direct sources, not recursive leveled paths')
    parser.add_argument('--cell',help='Canonical cell key, e.g. interior:balmora, guild of mages')
    parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if args.limit<1 or args.limit>1000:parser.error('--limit must be 1..1000')
    path=args.database or load_config(ROOT/'foundation_config.json')[2]/'world/world.sqlite'
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        if not db.execute('SELECT 1 FROM profiles WHERE id=?',(args.profile,)).fetchone():
            parser.error('Profile is not present in this world build')
        if args.item:
            key=args.item.casefold()
            queries={
                'directPlacements':('''SELECT v.reference_key,v.cell_key,v.x,v.y,v.z,v.owner_key,v.faction_key
                    FROM placements v JOIN profile_placements p ON p.version_id=v.version_id
                    WHERE v.object_key=? AND p.profile_id=? LIMIT ?''',(key,args.profile,args.limit)),
                'inventoryDefinitions':('''SELECT o.record_type,o.object_key,o.name,i.entry_index,i.count_raw,i.restocking
                    FROM inventories i JOIN objects o ON o.version_id=i.holder_version_id
                    JOIN profile_objects p ON p.version_id=o.version_id
                    WHERE i.object_key=? AND p.profile_id=? LIMIT ?''',(key,args.profile,args.limit)),
                'leveledLists':('''SELECT o.object_key,e.entry_index,e.minimum_level,l.chance_none,l.flags_raw
                    FROM leveled_entries e JOIN objects o ON o.version_id=e.list_version_id
                    JOIN leveled_lists l ON l.version_id=o.version_id JOIN profile_objects p ON p.version_id=o.version_id
                    WHERE e.object_key=? AND p.profile_id=? LIMIT ?''',(key,args.profile,args.limit))}
            print(json.dumps({label:[dict(r) for r in db.execute(sql,params)] for label,(sql,params) in queries.items()},indent=2))
        elif args.cell:
            rows=db.execute('''SELECT v.reference_key,v.object_key,v.x,v.y,v.z,v.owner_key,v.faction_key
                FROM placements v JOIN profile_placements p ON p.version_id=v.version_id
                WHERE v.cell_key=? AND p.profile_id=? LIMIT ?''',(args.cell.casefold(),args.profile,args.limit))
            print(json.dumps([dict(r) for r in rows],indent=2))
        else:
            print('Metadata:')
            for row in db.execute('SELECT key,value FROM metadata'):print(' ',row['key']+':',row['value'])
            print('Profile:',args.profile)
            for row in db.execute('SELECT record_type,count(*) AS n FROM profile_objects WHERE profile_id=? GROUP BY record_type',(args.profile,)):
                print(' ',row['record_type'],f'{row["n"]:,}')
            for table in ('cells','profile_placements','warnings'):
                print(table,db.execute('SELECT count(*) FROM '+table+' WHERE profile_id=?',(args.profile,)).fetchone()[0])


if __name__=='__main__':main()
