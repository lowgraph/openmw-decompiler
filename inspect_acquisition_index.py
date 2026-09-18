"""Query a bounded reverse evidence graph for an item, without path expansion."""
import argparse
from collections import deque
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from build_acquisition_index import metadata
from extract_foundation import ROOT,load_config
from export_items import ExportError


def query_item(db,world,profile,item,record_type=None,max_nodes=2000,max_edges=5000,max_depth=12,max_placements=100):
    if min(max_nodes,max_edges,max_placements)<1 or max_depth<0:raise ExportError('Query limits must be positive; depth may be zero')
    meta=metadata(db);wm=metadata(world)
    if meta.get('schemaVersion')!='1.0.0':raise ExportError('Unsupported acquisition schema')
    if (meta['snapshotId'],meta['worldSchemaVersion'],meta['worldBuiltAtUnix'])!=(wm.get('snapshotId'),wm.get('schemaVersion'),wm.get('builtAtUnix')):
        raise ExportError('World/index mismatch; rebuild acquisition index after rebuilding world')
    params=[profile,item.casefold()];sql='SELECT version_id FROM profile_nodes WHERE profile_id=? AND object_key=?'
    if record_type:sql+=' AND record_type=?';params.append(record_type.upper())
    roots=db.execute(sql,params).fetchall()
    if not roots:raise ExportError('No matching definition in this profile')
    if len(roots)!=1:raise ExportError('Ambiguous object ID; specify --type')
    root=roots[0][0];depths={root:0};queue=deque([root]);edges=[];reasons=set();stop=False
    while queue and not stop:
        target=queue.popleft();depth=depths[target]
        if depth>=max_depth:
            if db.execute('SELECT 1 FROM profile_edges WHERE profile_id=? AND target_version_id=? LIMIT 1',(profile,target)).fetchone():reasons.add('max_depth')
            continue
        for parent,kind,index,details in db.execute('''SELECT p.parent_version_id,p.kind,p.entry_index,e.details_json
            FROM profile_edges p JOIN edges e USING(parent_version_id,kind,entry_index)
            WHERE p.profile_id=? AND p.target_version_id=? ORDER BY p.parent_version_id,p.kind,p.entry_index LIMIT ?''',
            (profile,target,max_edges-len(edges)+1)):
            if len(edges)>=max_edges:reasons.add('max_edges');stop=True;break
            if parent not in depths:
                if len(depths)>=max_nodes:reasons.add('max_nodes');continue
                depths[parent]=depth+1;queue.append(parent)
            edges.append({'parentVersionId':parent,'targetVersionId':target,'kind':kind,'entryIndex':index,'details':json.loads(details)})
    nodes=[];placements=[]
    for version,depth in depths.items():
        tag,key,name,plugin,script,details=db.execute('SELECT record_type,object_key,name,plugin,script_key,details_json FROM nodes WHERE version_id=?',(version,)).fetchone()
        nodes.append({'versionId':version,'recordType':tag,'key':key,'name':name,'plugin':plugin,'scriptKey':script,'depth':depth,'details':json.loads(details)})
        if 'max_placements' in reasons:continue
        # CROSS JOIN fixes join order: object-key index first, then exact profile/ref.
        for pv,ref,cell,x,y,z,count,owner,faction,detail,winning_plugin in world.execute('''
            SELECT v.version_id,v.reference_key,v.cell_key,v.x,v.y,v.z,v.count_raw,v.owner_key,v.faction_key,v.details,v.plugin
            FROM placements v INDEXED BY placement_item CROSS JOIN profile_placements p
            ON p.profile_id=? AND p.reference_key=v.reference_key AND p.version_id=v.version_id
            WHERE v.object_key=? ORDER BY v.version_id LIMIT ?''',(profile,key,max_placements-len(placements)+1)):
            if len(placements)>=max_placements:reasons.add('max_placements');break
            placements.append({'nodeVersionId':version,'placementVersionId':pv,'referenceKey':ref,'cellKey':cell,
                'position':[x,y,z],'countRaw':count,'ownerKey':owner,'factionKey':faction,
                'details':json.loads(detail),'plugin':winning_plugin,'directItemPlacement':version==root})
    return {'snapshotId':meta['snapshotId'],'profile':profile,'rootVersionId':root,
        'scope':'Static reverse inventory/list graph and direct placements; not guaranteed acquisition or all script sources.',
        'truncated':bool(reasons),'limitReasons':sorted(reasons),
        'limits':{'nodes':max_nodes,'edges':max_edges,'depth':max_depth,'placements':max_placements},
        'nodes':nodes,'edges':edges,'placements':placements}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',type=Path);parser.add_argument('--world-database',type=Path)
    parser.add_argument('--profile',default='tr',choices=['vanilla','tr','tr_arce'])
    parser.add_argument('--item');parser.add_argument('--type',dest='record_type')
    parser.add_argument('--max-nodes',type=int,default=2000);parser.add_argument('--max-edges',type=int,default=5000)
    parser.add_argument('--max-depth',type=int,default=12);parser.add_argument('--max-placements',type=int,default=100)
    args=parser.parse_args(argv)
    if not (1<=args.max_nodes<=10000 and 1<=args.max_edges<=50000 and 0<=args.max_depth<=100 and 1<=args.max_placements<=10000):parser.error('Limits exceed supported bounds or are negative/zero')
    path=args.database or load_config(ROOT/'foundation_config.json')[2]/'acquisition/acquisition.sqlite'
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            db.execute('PRAGMA temp_store=MEMORY');db.execute('BEGIN');meta=metadata(db)
            if not db.execute('SELECT 1 FROM profiles WHERE id=?',(args.profile,)).fetchone():raise ExportError('Profile absent from index')
            if args.item:
                world_path=args.world_database or Path(meta['worldDatabase'])
                with closing(sqlite3.connect(world_path.resolve().as_uri()+'?mode=ro',uri=True)) as world:
                    world.execute('PRAGMA temp_store=MEMORY');world.execute('BEGIN')
                    result=query_item(db,world,args.profile,args.item,args.record_type,args.max_nodes,args.max_edges,args.max_depth,args.max_placements)
            else:
                result={'metadata':meta,'profile':args.profile,
                    'counts':{t:db.execute('SELECT count(*) FROM '+t+' WHERE profile_id=?',(args.profile,)).fetchone()[0] for t in ('profile_nodes','profile_edges')},
                    'warnings':[{'code':c,'targetKey':k,'count':n} for c,k,n in db.execute('SELECT code,target_key,count FROM warnings WHERE profile_id=?',(args.profile,))]}
            print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except (OSError,ValueError,KeyError,sqlite3.Error) as exc:
        print(f'Acquisition query failed: {exc}');return 1


if __name__=='__main__':raise SystemExit(main())
