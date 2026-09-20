"""Build the fast travel network as a shipped catalog.

An edge is one journey a transport provider will sell you: the cell you speak to them
in, the cell they put you down in, and what the site's toggles have to say about it.
The network is derived; the two rules that cannot be derived are authored in
`policy/travel.json` and verified against the data before anything is published.

Teleport doors are deliberately not here. 17,156 door links answer a different
question — walking between interiors and exteriors — at forty times the size.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

from build_acquisition_index import metadata
from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'
# NPC class, as the record stores it. Creatures carry no class, which is the whole
# reason the guild guide rule keys on destinations instead.
CLASS = re.compile(rb'CNAM.{4}([^\x00]*)\x00', re.S)


def load_travel_policy(path):
    policy = json.loads(Path(path).read_text(encoding='utf-8'))
    if policy.get('schemaVersion') != VERSION:
        raise ExportError(f'Unsupported travel policy schema {policy.get("schemaVersion")!r}')
    guide = policy.get('guildGuide')
    if not isinstance(guide, dict) or not guide.get('cellMarkers'):
        raise ExportError('Travel policy has no guildGuide.cellMarkers')
    rank = policy.get('conjurerRank')
    if not isinstance(rank, dict) or not isinstance(rank.get('cities'), dict) \
            or not isinstance(rank.get('edges'), list):
        raise ExportError('Travel policy has no conjurerRank.cities and conjurerRank.edges')
    for edge in rank['edges']:
        for end in ('from', 'to'):
            if edge.get(end) not in rank['cities']:
                raise ExportError(f'Conjurer edge names {edge.get(end)!r}, which is not a city')
    if not isinstance(policy.get('modes', {}).get('byClass'), dict):
        raise ExportError('Travel policy has no modes.byClass')
    if not isinstance(policy.get('excludedCells'), list):
        raise ExportError('Travel policy excludedCells must be a list, possibly empty')
    return policy


def actor_classes(game, profile):
    """Each actor's class for this profile, from the record that actually wins.

    Only the winning version matters: a later plugin can change an NPC's class, and
    reading every version would let an overridden one decide.
    """
    found = {}
    for key, payload in game.execute(
            'SELECT rv.record_key, rv.payload FROM resolved_records rr '
            'JOIN record_versions rv ON rv.id = rr.winner_id '
            "WHERE rr.profile_id = ? AND rv.record_type IN ('NPC_', 'CREA')", (profile,)):
        match = CLASS.search(payload)
        found[key] = match.group(1).decode('cp1252', 'replace') if match else None
    return found


def guild_cell(cell_key, markers):
    lowered = cell_key.casefold()
    return any(marker in lowered for marker in markers)


def collect(services, profile, policy):
    """Every provider that sells travel, where it stands, and where it sends you."""
    excluded = {key.casefold() for key in policy['excludedCells']}
    rows = services.execute(
        'SELECT pp.actor_key, pr.name, pr.record_type, pl.cell_key, pd.cell_key, pd.status '
        'FROM profile_providers pp '
        'JOIN providers pr ON pr.version_id = pp.version_id '
        'JOIN profile_destinations pd ON pd.provider_version_id = pp.version_id '
        ' AND pd.profile_id = pp.profile_id '
        'LEFT JOIN provider_locations pl ON pl.provider_version_id = pp.version_id '
        ' AND pl.profile_id = pp.profile_id '
        'WHERE pp.profile_id = ?', (profile,)).fetchall()
    providers, unplaced, skipped = {}, set(), 0
    for actor, name, record_type, home, destination, status in rows:
        if status != 'resolved':
            skipped += 1
            continue
        if destination.casefold() in excluded or (home or '').casefold() in excluded:
            skipped += 1
            continue
        entry = providers.setdefault(actor, {'key': actor, 'name': name, 'recordType': record_type,
                                             'cells': set(), 'destinations': set()})
        entry['destinations'].add(destination)
        if home:
            entry['cells'].add(home)
        else:
            unplaced.add(actor)
    return providers, sorted(unplaced), skipped


def classify(providers, classes, policy):
    """Mark the guild guides, and say where the two ways of spotting one disagree.

    The destination rule decides. It is the only one that covers a creature, and the
    data says it never half-applies: no provider mixes Mages Guild destinations with
    other ones. That premise is checked rather than assumed.
    """
    markers = policy['guildGuide']['cellMarkers']
    npc_class = policy['guildGuide'].get('npcClass')
    modes = policy['modes']['byClass']
    mixed, disagreement = [], []
    for actor, entry in providers.items():
        guildish = {guild_cell(cell, markers) for cell in entry['destinations']}
        if len(guildish) > 1:
            mixed.append(actor)
        entry['class'] = classes.get(actor)
        entry['guildGuide'] = guildish == {True}
        entry['mode'] = modes.get(entry['class'])
        if entry['guildGuide'] != (entry['class'] == npc_class):
            disagreement.append({'key': actor, 'name': entry['name'],
                                 'recordType': entry['recordType'], 'class': entry['class'],
                                 'byDestination': entry['guildGuide']})
        if entry['guildGuide'] and entry['mode'] is None:
            # A guide the class rule cannot see still travels by guild teleport.
            entry['mode'] = modes.get(npc_class)
    if mixed:
        raise ExportError(
            'The guild guide rule assumes a provider never mixes Mages Guild destinations '
            'with other ones, and these do: ' + ', '.join(sorted(mixed)[:6])
            + '\n  Identifying guild guides by destination is no longer safe. Fix the rule '
              'in policy/travel.json before publishing a network built on it.')
    return sorted(disagreement, key=lambda d: d['key'])


def conjurer_edges(policy, profile):
    """The authored rank-gated journeys, as concrete cell pairs."""
    rank = policy['conjurerRank']
    if profile not in rank['profiles']:
        return {}
    cities = rank['cities']
    return {(cities[edge['from']], cities[edge['to']]): (edge['from'], edge['to'])
            for edge in rank['edges']}


def build(services, game, profile, policy):
    providers, unplaced, skipped = collect(services, profile, policy)
    disagreement = classify(providers, actor_classes(game, profile), policy)
    gated = conjurer_edges(policy, profile)
    edges, used = [], set()
    for actor in sorted(providers):
        entry = providers[actor]
        for origin in sorted(entry['cells']):
            for destination in sorted(entry['destinations']):
                if origin == destination:
                    continue  # A provider standing in the cell they would send you to.
                pair = (origin, destination)
                if pair in gated:
                    used.add(pair)
                edges.append({
                    'key': f'{actor}|{origin}|{destination}',
                    'provider': actor, 'from': origin, 'to': destination,
                    'mode': entry['mode'],
                    'requiresMageGuild': entry['guildGuide'],
                    'requiresConjurer': pair in gated})
    missing = sorted(gated[pair] for pair in gated if pair not in used)
    if missing:
        raise ExportError(
            f'{len(missing)} Conjurer edge(s) in policy/travel.json match nothing in the '
            f'{profile} data: ' + ', '.join(f'{a} -> {b}' for a, b in missing[:6])
            + '\n  A renamed cell or a changed guide would otherwise empty the toggle '
              'silently. Check conjurerRank.cities against the extracted cell keys.')
    nodes = node_table(services, profile, edges)
    return {'edges': edges, 'nodes': nodes,
            'providers': {a: {k: v for k, v in e.items() if k != 'cells' and k != 'destinations'}
                          | {'cells': sorted(e['cells'])} for a, e in sorted(providers.items())},
            'verification': {
                'providers': len(providers), 'edges': len(edges), 'nodes': len(nodes),
                'guildGuides': sum(1 for e in providers.values() if e['guildGuide']),
                'guildGuidesByClass': sum(1 for e in providers.values()
                                          if e['class'] == policy['guildGuide'].get('npcClass')),
                'classDisagreement': disagreement,
                'conjurerEdges': len(used),
                'providersWithUnknownMode': sorted(a for a, e in providers.items()
                                                   if e['mode'] is None),
                'unplacedProviders': unplaced,
                'destinationsSkipped': skipped}}


def node_table(services, profile, edges):
    """Only the cells the network actually touches, with their names and regions."""
    wanted = {edge[end] for edge in edges for end in ('from', 'to')}
    nodes = {}
    for key, name, interior, region in services.execute(
            'SELECT cell_key, name, interior, region_key FROM cells WHERE profile_id = ?',
            (profile,)):
        if key in wanted:
            nodes[key] = {'key': key, 'name': name, 'interior': bool(interior), 'region': region}
    for key in sorted(wanted - set(nodes)):
        # An endpoint with no cell row is still a real endpoint; say so rather than drop it.
        nodes[key] = {'key': key, 'name': None, 'interior': key.startswith('interior:'),
                      'region': None}
    return nodes


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.travel-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def assemble(services, game, profile, policy, snapshot):
    network = build(services, game, profile, policy)
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'policyVersion': policy['policyVersion'],
        'toggles': {
            'mageGuildMember': {
                'default': True, 'appliesTo': 'all',
                'note': 'Off removes every edge with requiresMageGuild. Silt striders, '
                        'boats, gondolas and riverstriders are untouched.'},
            'conjurerRank': {
                'default': False, 'appliesTo': policy['conjurerRank']['profiles'],
                'note': 'Off removes every edge with requiresConjurer. These are edges, '
                        'not providers: the short-range guide in each of the four cities '
                        'keeps working.'}},
        'authored': {'guildGuide': policy['guildGuide'], 'conjurerRank': policy['conjurerRank'],
                     'source': 'authored'},
        'verification': network['verification'],
        'nodes': network['nodes'], 'providers': network['providers'],
        'coverage': 'Transport providers and the journeys they sell, from static service '
                    'flags and actor destination lists. No prices, no schedules, no '
                    'dialogue or script evaluation, and no teleport doors: walking routes '
                    'are a separate and far larger graph. A rank requirement is authored, '
                    'not extracted, because the travel records carry none.',
        'builtAtUnix': time.time(), 'edges': network['edges']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--foundation-database', type=Path)
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        policy = load_travel_policy(args.policy or ROOT/'policy/travel.json')
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        paths = (args.services_database or root/'services/services.sqlite',
                 args.foundation_database or root/'game-data.sqlite')
        written = []
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(
                    sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                dbs.append(db)
            services, game = dbs
            snapshot = metadata(services).get('snapshotId')
            for profile in profiles:
                payload = assemble(services, game, profile, policy, snapshot)
                destination, size = publish(payload, args.output or root/'travel', profile)
                check = payload['verification']
                print(f'{profile}: {check["edges"]} edges, {check["nodes"]} cells, '
                      f'{check["providers"]} providers ({check["guildGuides"]} guild guides, '
                      f'{check["conjurerEdges"]} Conjurer edges), {size/1024:.0f} KB', flush=True)
                if check['classDisagreement']:
                    for row in check['classDisagreement']:
                        print(f'  by destination {row["byDestination"]} but class '
                              f'{row["class"]!r}: {row["name"]} ({row["recordType"]})', flush=True)
                written.append(destination)
        print('Travel catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Travel catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
