"""Combine static item sources and script evidence without rebuilding databases."""
import argparse
from contextlib import ExitStack,closing
import json
from pathlib import Path
import sqlite3
import sys

from extract_foundation import ROOT,load_config
from export_items import CATEGORIES,ExportError
from build_acquisition_index import metadata
from inspect_acquisition_index import query_item
from inspect_script_evidence import item_evidence


def unified_sources(acquisition,world,evidence,profile,item,record_type=None,
                    max_nodes=2000,max_edges=5000,max_depth=12,max_placements=100,
                    max_events=100,max_script_targets=200,max_anchors=100,max_anchor_placements=100):
    if min(max_events,max_script_targets,max_anchors,max_anchor_placements)<1:
        raise ExportError('Evidence limits must be positive')
    am,wm,em=metadata(acquisition),metadata(world),metadata(evidence)
    if em.get('schemaVersion')!='1.0.0' or em.get('builderVersion')!='1.0.1':
        raise ExportError('Rebuild script evidence with builder 1.0.1 before using this tool')
    if not wm.get('snapshotId') or any(m.get('snapshotId')!=wm['snapshotId'] for m in (am,em)):
        raise ExportError('Input snapshot mismatch')
    if em.get('worldBuiltAtUnix')!=wm.get('builtAtUnix'):
        raise ExportError('Script evidence/world mismatch; rebuild script evidence')
    rows=[db.execute('SELECT id,world,version,arce FROM profiles WHERE id=?',(profile,)).fetchone() for db in (world,acquisition,evidence)]
    if any(r is None for r in rows) or any(tuple(r)!=tuple(rows[0]) for r in rows[1:]):
        raise ExportError('Profile missing or inconsistent across inputs')
    static=query_item(acquisition,world,profile,item,record_type,max_nodes,max_edges,max_depth,max_placements)
    root=static['nodes'][0]
    if root['recordType'] not in CATEGORIES:raise ExportError('The requested definition is not an item category')
    reasons={'static:'+r for r in static['limitReasons']}
    events=[];seen=set();anchors={};anchor_links=[];link_seen=set();lookup={}

    def add_anchor(key,role,event_id,expected_version=None):
        if not key or key=='player':return
        if key not in lookup:
            if len(lookup)>=max_anchors:
                reasons.add('script:anchors');return
            found=world.execute('''SELECT o.version_id,o.record_type,o.name FROM profile_objects p
                JOIN objects o ON o.version_id=p.version_id WHERE p.profile_id=? AND p.object_key=? LIMIT 2''',(profile,key)).fetchall()
            lookup[key]=found
        found=lookup[key]
        status='missing_definition' if not found else 'ambiguous_definition' if len(found)>1 else 'resolved'
        version=found[0][0] if status=='resolved' else None
        if expected_version is not None and version!=expected_version:
            status='attachment_revision_mismatch';version=None
        if key not in anchors:
            anchors[key]={'key':key,'status':status,'versionId':version,
                'recordType':found[0][1] if version is not None else None,
                'name':found[0][2] if version is not None else None}
        identity=(key,role,event_id)
        if identity not in link_seen:
            link_seen.add(identity);anchor_links.append({'anchorKey':key,'role':role,'eventId':event_id})

    targets=static['nodes'][:max_script_targets]
    if len(targets)<len(static['nodes']):reasons.add('script:targets')
    targets_examined=0
    for node in targets:
        remaining=max_events-len(events)
        if remaining<=0:
            reasons.add('script:events');break
        result=item_evidence(evidence,profile,node['key'],remaining)
        targets_examined+=1
        if result['truncated']:reasons.add('script:events')
        for event in result['events']:
            event_id=f"{event['source_version_id']}:{event['line_number']}"
            if event_id in seen:continue
            seen.add(event_id)
            event['eventId']=event_id;event['relatedNodeVersionId']=node['versionId']
            event['relationToItem']='direct_target' if node['versionId']==root['versionId'] else 'static_ancestor_target'
            # These remain separate evidence types; removals are never grants.
            event['effectCategory']={'inventory_add':'addition','object_create':'creation','list_add':'list_addition',
                'inventory_remove':'removal','list_remove':'list_removal'}.get(event['kind'],'control')
            if event['attachmentsTruncated']:reasons.add('script:attachments')
            for attachment in event['scriptAttachments']:
                add_anchor(attachment['object_key'],'script_attachment',event_id,attachment['object_version_id'])
            context=event.get('dialogue_context') or {}
            add_anchor(context.get('actor_key'),'dialogue_actor_filter',event_id)
            add_anchor(event.get('receiver_key'),'explicit_receiver',event_id)
            events.append(event)
        if result['truncated']:break
    locations=[]
    for anchor in anchors.values():
        if anchor['status']!='resolved':continue
        remaining=max_anchor_placements-len(locations)
        found=world.execute('''SELECT v.version_id,v.reference_key,v.cell_key,v.x,v.y,v.z,v.owner_key,v.faction_key,v.details
            FROM placements v INDEXED BY placement_item CROSS JOIN profile_placements p
            ON p.profile_id=? AND p.reference_key=v.reference_key AND p.version_id=v.version_id
            WHERE v.object_key=? ORDER BY v.version_id LIMIT ?''',(profile,anchor['key'],remaining+1))
        for version,ref,cell,x,y,z,owner,faction,details in found:
            if len(locations)>=max_anchor_placements:
                reasons.add('script:anchor_placements');break
            locations.append({'anchorKey':anchor['key'],'placementVersionId':version,'referenceKey':ref,
                'cellKey':cell,'position':[x,y,z],'ownerKey':owner,'factionKey':faction,'details':json.loads(details)})
        if 'script:anchor_placements' in reasons:break
    return {'schemaVersion':'1.0.0','snapshotId':wm['snapshotId'],
        'profile':{'id':profile,'world':rows[0][1],'version':rows[0][2],'arce':bool(rows[0][3])},
        'inputBuilds':{'world':wm['builtAtUnix'],'acquisition':am['builtAtUnix'],'scriptEvidence':em['builtAtUnix']},
        'item':{'key':root['key'],'name':root['name'],'recordType':root['recordType'],'versionId':root['versionId']},
        'truncated':bool(reasons),'limitReasons':sorted(reasons),
        'counts':{'staticPlacements':len(static['placements']),'scriptEvents':len(events),
            'scriptContextDefinitions':len(anchors),'scriptContextPlacements':len(locations)},
        'coverage':'Static containment plus lexical script evidence for the item and discovered ancestors. Context locations are not item placements or proof of execution.',
        'assessment':{'obtainable':None,'theftRequired':None,'saleStatus':None,'price':None,'earlyGameEligible':None},
        'static':static,'script':{'events':events,'contextAnchors':list(anchors.values()),'contextLinks':anchor_links,
            'contextPlacements':locations,'targetsExamined':targets_examined,
            'limits':{'events':max_events,'targets':max_script_targets,'anchors':max_anchors,'anchorPlacements':max_anchor_placements}}}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--item',required=True);parser.add_argument('--type',dest='record_type',choices=sorted(CATEGORIES))
    parser.add_argument('--profile',default='tr',choices=['vanilla','tr','tr_arce'])
    parser.add_argument('--acquisition-database',type=Path);parser.add_argument('--world-database',type=Path)
    parser.add_argument('--evidence-database',type=Path)
    for name,default in [('nodes',2000),('edges',5000),('depth',12),('placements',100),('events',100),('script-targets',200),('anchors',100),('anchor-placements',100)]:
        parser.add_argument('--max-'+name,type=int,default=default)
    args=parser.parse_args(argv)
    for name,ceiling in [('nodes',10000),('edges',50000),('depth',100),('placements',10000),('events',1000),('script_targets',10000),('anchors',1000),('anchor_placements',10000)]:
        if not (0 if name=='depth' else 1)<=getattr(args,'max_'+name)<=ceiling:parser.error('Query limit outside supported range: '+name)
    try:
        root=load_config(ROOT/'foundation_config.json')[2]
        paths=(args.acquisition_database or root/'acquisition/acquisition.sqlite',args.world_database or root/'world/world.sqlite',args.evidence_database or root/'script-evidence/script-evidence.sqlite')
        with ExitStack() as stack:
            dbs=[]
            for path in paths:
                db=stack.enter_context(closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)))
                db.execute('PRAGMA temp_store=MEMORY');db.execute('PRAGMA cache_size=-16384');db.execute('BEGIN');dbs.append(db)
            result=unified_sources(*dbs,args.profile,args.item,args.record_type,args.max_nodes,args.max_edges,args.max_depth,args.max_placements,
                args.max_events,args.max_script_targets,args.max_anchors,args.max_anchor_placements)
            print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False));return 0
    except (OSError,ValueError,KeyError,sqlite3.Error) as exc:
        print(f'Item source query failed: {exc}',file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
