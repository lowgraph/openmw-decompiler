"""Read the foundation database without loading its full contents."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from extract_foundation import fields, load_config, ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path)
    parser.add_argument('--profile', choices=['vanilla', 'tr', 'tr_arce'], default='vanilla')
    parser.add_argument('--type', help='Record type, for example WEAP')
    parser.add_argument('--id', help='Canonical record key, usually a case-insensitive editor ID')
    args = parser.parse_args()
    path = args.database or load_config(ROOT/'foundation_config.json')[2]/'game-data.sqlite'
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if args.type and args.id is not None:
            row = db.execute('''SELECT v.display_id,v.deleted,p.name,o.name,v.payload
                FROM resolved_records r JOIN record_versions v ON v.id=r.winner_id
                JOIN plugins p ON p.id=v.plugin_id JOIN plugins o ON o.id=r.origin_plugin_id
                WHERE r.profile_id=? AND r.record_type=? AND r.record_key=?''',
                (args.profile,args.type.upper(),args.id.casefold())).fetchone()
            if not row:
                print('No matching record in this profile.')
                return
            ident, deleted, winner, origin, payload = row
            print(json.dumps({'id': ident, 'deleted': bool(deleted), 'originPlugin': origin,
                              'winningPlugin': winner, 'subrecords': [
                                  {'type': tag, 'size': len(value), 'hex': bytes(value).hex()}
                                  for tag,value,_,_ in fields(payload)]}, indent=2))
        else:
            print('Metadata:')
            for key,value in db.execute('SELECT key,value FROM metadata WHERE key != "profiles"'):
                print(f'  {key}: {value}')
            print(f'Live records in {args.profile}:')
            for tag,count in db.execute('SELECT record_type,count(*) FROM live_records WHERE profile_id=? GROUP BY record_type ORDER BY record_type',(args.profile,)):
                print(f'  {tag}: {count:,}')
            print('Live references:', db.execute('SELECT count(*) FROM live_references WHERE profile_id=?',(args.profile,)).fetchone()[0])


if __name__ == '__main__':
    main()
