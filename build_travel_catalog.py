"""Build the fast travel network as a shipped catalog.

An edge is one journey a transport provider will sell you: the cell you speak to them
in, the cell they put you down in, and what the site's toggles have to say about it.
The network is derived; the two rules that cannot be derived are authored in
`policy/travel.json` and verified against the data before anything is published.

Each journey also carries what the engine charges for it and how many hours pass,
worked out the way OpenMW's travel window does (see TRAVEL_FORMULA), and every stop
names the town it belongs to, so a town's docks, districts and guild hall can be one
place on the site.

Teleport doors are deliberately not here. 17,156 door links answer a different
question — walking between interiors and exteriors — at forty times the size.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

import autocalc
from build_acquisition_index import metadata
from build_merchant_catalog import (BARTER_FORMULA, actor_records, barter_stats,
                                    check_transcription)
from export_items import ExportError
from extract_foundation import ROOT, label_carries, load_config

VERSION = '1.0.0'
# NPC class, as the record stores it. Creatures carry no class, which is the whole
# reason the guild guide rule keys on destinations instead.
CLASS = re.compile(rb'CNAM.{4}([^\x00]*)\x00', re.S)

# The OpenMW release TRAVEL_FORMULA was checked against, line by line, at tag
# openmw-0.51.0: TravelWindow::addDestination and TravelWindow::onTravelButtonClick in
# apps/openmw/mwgui/travelwindow.cpp. It is code, not data, so no rebuild can update
# it; check_travel_transcription stops the build when the extraction names another
# release. The barter step and the autocalc it needs are pinned separately, in
# build_merchant_catalog.py.
TRANSCRIBED_FROM = '0.51.0'

# What the travel window charges and how long the journey takes. Engine code rather
# than game settings, so authored and marked; the settings it reads are published
# beside it with their values for this profile.
TRAVEL_FORMULA = {
    'source': 'authored',
    'transcribedFrom': f'OpenMW {TRANSCRIBED_FROM}',
    'function': 'TravelWindow::addDestination and TravelWindow::onTravelButtonClick, '
                'apps/openmw/mwgui/travelwindow.cpp',
    'note': 'A provider standing in an interior charges fMagesGuildTravel and no time '
            'passes. Anyone else charges the straight-line distance, in three dimensions, '
            'from the player to the destination divided by fTravelMult, truncated; the '
            'journey takes the flat two-dimensional distance divided by fTravelTimeMult, '
            'truncated, in whole hours. The price is at least 1, is multiplied by one plus '
            'the followers travelling along, and then goes through getBarterOffer (see '
            'barterFormula). The engine measures from where the player stands; this '
            'measures from where the provider stands, a few steps away, so a price can '
            'differ by a gold piece where it sits on a boundary.',
    'minimumPrice': 1,
    'followersMultiplyPrice': True,
    'interiorProviderChargesFlat': 'fMagesGuildTravel',
    'gameSettings': ['fTravelMult', 'fTravelTimeMult', 'fMagesGuildTravel'],
}


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
    vehicle = policy['modes'].get('byVehicle')
    if vehicle is not None:
        markers = vehicle.get('markers')
        if not (isinstance(vehicle.get('classes'), list) and isinstance(vehicle.get('radius'), (int, float))
                and vehicle['radius'] > 0 and isinstance(markers, list) and markers
                and all(isinstance(m, dict) and isinstance(m.get('mode'), str) and m['mode']
                        and isinstance(m.get('models'), list) and m['models']
                        and all(isinstance(x, str) and x for x in m['models']) for m in markers)):
            raise ExportError('Travel policy modes.byVehicle needs classes, a positive radius and '
                              'markers, each a mode with a non-empty models list')
    if not isinstance(policy.get('excludedCells'), list):
        raise ExportError('Travel policy excludedCells must be a list, possibly empty')
    towns = policy.get('towns')
    if towns is not None:
        radius = towns.get('radius') if isinstance(towns, dict) else None
        overrides = towns.get('overrides') if isinstance(towns, dict) else None
        if not (isinstance(radius, int) and not isinstance(radius, bool) and radius >= 0
                and isinstance(overrides, dict)
                and all(isinstance(k, str) and k.startswith(('exterior:', 'interior:'))
                        and (v is None or (isinstance(v, str) and v.strip()))
                        for k, v in overrides.items())):
            raise ExportError('Travel policy towns needs a whole radius of 0 or more and '
                              'overrides mapping cell keys to a town name, or to null for '
                              'a stop that belongs to no town')
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
        'SELECT pp.actor_key, pr.name, pr.record_type, pl.cell_key, pd.cell_key, pd.status, '
        ' pl.x, pl.y, pl.z, td.x, td.y, td.z, pr.stats_json '
        'FROM profile_providers pp '
        'JOIN providers pr ON pr.version_id = pp.version_id '
        'JOIN profile_destinations pd ON pd.provider_version_id = pp.version_id '
        ' AND pd.profile_id = pp.profile_id '
        'LEFT JOIN transport_destinations td ON td.provider_version_id = pd.provider_version_id '
        ' AND td.entry_index = pd.entry_index '
        'LEFT JOIN provider_locations pl ON pl.provider_version_id = pp.version_id '
        ' AND pl.profile_id = pp.profile_id '
        'WHERE pp.profile_id = ?', (profile,)).fetchall()
    providers, unplaced, skipped = {}, set(), 0
    for (actor, name, record_type, home, destination, status,
         sx, sy, sz, dx, dy, dz, stats) in rows:
        if status != 'resolved':
            skipped += 1
            continue
        if destination.casefold() in excluded or (home or '').casefold() in excluded:
            skipped += 1
            continue
        entry = providers.setdefault(actor, {'key': actor, 'name': name, 'recordType': record_type,
                                             'cells': set(), 'destinations': set(),
                                             'stats': json.loads(stats or '{}'), 'points': {}})
        entry['destinations'].add(destination)
        if home:
            entry['cells'].add(home)
            source, target = (sx, sy, sz), (dx, dy, dz)
            if None not in source and None not in target:
                entry['points'].setdefault((home, destination), []).append((source, target))
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


GRID = re.compile(r'^exterior:(-?\d+),(-?\d+)$')


def nearby_models(world, profile, cell, x, y, radius):
    """Models placed within radius of a point. An exterior stop can sit on a cell border,
    so the eight neighbouring cells are searched too."""
    grid = GRID.match(cell)
    cells = ([f'exterior:{int(grid[1])+dx},{int(grid[2])+dy}' for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
             if grid else [cell])
    marks = ','.join('?'*len(cells))
    return [model or '' for model, in world.execute(
        f'SELECT o.model FROM placements p '
        f'JOIN profile_placements pp ON pp.reference_key = p.reference_key AND pp.version_id = p.version_id '
        f'JOIN profile_objects po ON po.profile_id = pp.profile_id AND po.object_key = p.object_key '
        f'JOIN objects o ON o.version_id = po.version_id '
        f'WHERE pp.profile_id = ? AND p.cell_key IN ({marks}) '
        f'AND (p.x - ?)*(p.x - ?) + (p.y - ?)*(p.y - ?) < ?',
        (profile, *cells, x, x, y, y, radius*radius))]


def vehicle_modes(world, profile, providers, rule):
    """What each operator of the listed classes actually drives, from the vehicle at their stop.

    Returns {actor: {'mode', 'model'}} for every operator a marker matched. The markers
    are tried in the policy's order, so a strider port with a guar cart beside it is
    still a strider port.
    """
    if world is None or not rule:
        return {}
    classes = set(rule['classes'])
    found = {}
    for actor, entry in providers.items():
        if entry.get('class') not in classes:
            continue
        spots = world.execute(
            'SELECT p.cell_key, p.x, p.y FROM placements p '
            'JOIN profile_placements pp ON pp.reference_key = p.reference_key '
            ' AND pp.version_id = p.version_id '
            'WHERE pp.profile_id = ? AND p.object_key = ?', (profile, actor)).fetchall()
        for cell, x, y in spots:
            if x is None or y is None:
                continue
            models = [m.casefold() for m in nearby_models(world, profile, cell, x, y, rule['radius'])]
            match = next(((marker['mode'], model) for marker in rule['markers'] for model in models
                          if any(part.casefold() in model for part in marker['models'])), None)
            if match:
                found[actor] = {'mode': match[0], 'model': match[1]}
                break
    return found


def conjurer_edges(policy, profile):
    """The authored rank-gated journeys, as concrete cell pairs."""
    rank = policy['conjurerRank']
    if profile not in rank['profiles']:
        return {}
    cities = rank['cities']
    return {(cities[edge['from']], cities[edge['to']]): (edge['from'], edge['to'])
            for edge in rank['edges']}


def journey(points, interior, settings):
    """Price before barter and hours, as TravelWindow works them out, or None.

    `points` holds (provider position, destination position) pairs for one journey; a
    provider placed twice in one cell, or a destination listed twice, gives several,
    and the shortest is used. None when no position is known or no settings were given.
    """
    if not settings or not points:
        return None
    for name in TRAVEL_FORMULA['gameSettings']:
        if not isinstance(settings.get(name), (int, float)) or isinstance(settings.get(name), bool):
            raise ExportError(f'GameSettings has no numeric {name}; the travel price needs it')
    source, target = min(points, key=lambda pair: (math.dist(*pair), pair))
    distance = math.dist(source, target)
    if interior:
        # gmst.find("fMagesGuildTravel")->mValue.getInteger(): a float setting, truncated.
        price, hours = int(settings['fMagesGuildTravel']), 0
    else:
        mult = settings['fTravelMult']
        price = int(distance / mult) if mult != 0 else int(distance)
        time_mult = settings['fTravelTimeMult']
        flat = math.dist(source[:2], target[:2])
        hours = int(flat / time_mult) if time_mult else 0
    return {'price': max(TRAVEL_FORMULA['minimumPrice'], price), 'hours': hours,
            'distance': round(distance),
            'fromPos': [round(source[0]), round(source[1])],
            'toPos': [round(target[0]), round(target[1])]}


def provider_barter(entry, identity, reference):
    """The seller's side of getBarterOffer, read from the record or rerun as autocalc.

    Most travel providers are auto-calculated: their records store no skills at all.
    """
    stats = entry['stats']
    barter = barter_stats(stats)
    haggles = entry['recordType'] != 'CREA'
    source = 'record' if None not in barter.values() else None
    if source is None and reference is not None and haggles:
        derived = autocalc.derive(reference, identity.get('race'), identity.get('class'),
                                  stats.get('level'), bool(stats.get('female')))
        if derived and None not in derived.values():
            barter, source = derived, 'derived'
    return {'mercantile': barter['mercantile'], 'personality': barter['personality'],
            'luck': barter['luck'], 'disposition': stats.get('disposition'),
            'statsSource': source, 'haggles': haggles,
            # getBarterOffer returns a creature's price unchanged.
            'priceable': not haggles or source is not None,
            'race': identity.get('race'), 'female': bool(stats.get('female'))}


def build(services, game, profile, policy, world=None, settings=None, reference=None):
    providers, unplaced, skipped = collect(services, profile, policy)
    disagreement = classify(providers, actor_classes(game, profile), policy)
    rule = policy['modes'].get('byVehicle')
    vehicles = vehicle_modes(world, profile, providers, rule)
    for actor, vehicle in vehicles.items():
        providers[actor]['mode'] = vehicle['mode']
        providers[actor]['vehicle'] = vehicle['model']
    without = sorted(a for a, e in providers.items()
                     if rule and world is not None and e.get('class') in set(rule['classes'])
                     and a not in vehicles and e['cells'])
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
                edge = {
                    'key': f'{actor}|{origin}|{destination}',
                    'provider': actor, 'from': origin, 'to': destination,
                    'mode': entry['mode'],
                    'requiresMageGuild': entry['guildGuide'],
                    'requiresConjurer': pair in gated}
                if settings:
                    cost = journey(entry['points'].get(pair), origin.startswith('interior:'),
                                   settings)
                    # Null, never a guess, when a position is missing.
                    edge |= cost or {'price': None, 'hours': None}
                edges.append(edge)
    missing = sorted(gated[pair] for pair in gated if pair not in used)
    if missing:
        raise ExportError(
            f'{len(missing)} Conjurer edge(s) in policy/travel.json match nothing in the '
            f'{profile} data: ' + ', '.join(f'{a} -> {b}' for a, b in missing[:6])
            + '\n  A renamed cell or a changed guide would otherwise empty the toggle '
              'silently. Check conjurerRank.cities against the extracted cell keys.')
    nodes = node_table(services, profile, edges)
    unattached = assign_towns(services, profile, nodes, policy.get('towns'))
    identities = actor_records(game, profile) if settings else {}
    published = {}
    for actor, entry in sorted(providers.items()):
        row = {k: v for k, v in entry.items()
               if k not in ('cells', 'destinations', 'stats', 'points')}
        row['cells'] = sorted(entry['cells'])
        if settings:
            row['barter'] = provider_barter(entry, identities.get(actor, {}), reference)
        published[actor] = row
    unpriced = sorted(e['key'] for e in edges if settings and e.get('price') is None)
    return {'edges': edges, 'nodes': nodes, 'providers': published,
            'verification': {
                'providers': len(providers), 'edges': len(edges), 'nodes': len(nodes),
                'guildGuides': sum(1 for e in providers.values() if e['guildGuide']),
                'guildGuidesByClass': sum(1 for e in providers.values()
                                          if e['class'] == policy['guildGuide'].get('npcClass')),
                'classDisagreement': disagreement,
                'conjurerEdges': len(used),
                'providersWithUnknownMode': sorted(a for a, e in providers.items()
                                                   if e['mode'] is None),
                'vehicleModes': {mode: sum(1 for v in vehicles.values() if v['mode'] == mode)
                                 for mode in sorted({v['mode'] for v in vehicles.values()})},
                'operatorsWithoutVehicle': without,
                'unplacedProviders': unplaced,
                'destinationsSkipped': skipped,
                'towns': len({n['town'] for n in nodes.values() if n.get('town')}),
                'stopsWithoutTown': unattached,
                'edgesWithoutPrice': unpriced,
                'providersWithoutBarterStats': sorted(
                    a for a, p in published.items() if 'barter' in p and not p['barter']['priceable'])}}


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


def split_town(name):
    """'Old Ebonheart, Docks' is the Docks of Old Ebonheart. A stop's name before the
    first comma is its town; what follows is the district, hall or building."""
    town, _, district = name.partition(',')
    return town.strip(), (district.strip() or None)


def assign_towns(services, profile, nodes, rule):
    """Give every stop a town, so the site can treat a town's stops as one place.

    A named stop's town is its name up to the first comma. An unnamed exterior stop, a
    dock or a strider post just outside town, joins the town owning most of the named
    cells nearest to it within `radius` cells; a tie joins nothing. An override in the
    policy decides before either rule. Returns the stops left without a town.
    """
    rule = rule or {'radius': 0, 'overrides': {}}
    overrides = {k.casefold(): v for k, v in rule['overrides'].items()}
    named = {}
    if rule['radius'] > 0:
        for name, gx, gy in services.execute(
                "SELECT name, grid_x, grid_y FROM cells WHERE profile_id = ? AND interior = 0 "
                "AND name IS NOT NULL AND name != ''", (profile,)):
            if gx is not None and gy is not None:
                named[(gx, gy)] = split_town(name)[0]
    unattached = []
    for key, node in nodes.items():
        town = district = how = None
        if key.casefold() in overrides:
            town, how = overrides[key.casefold()], 'override'
            if node['name']:
                district = split_town(node['name'])[1]
        elif node['name']:
            (town, district), how = split_town(node['name']), 'name'
        else:
            grid = GRID.match(key)
            if grid and named:
                x, y = int(grid[1]), int(grid[2])
                near = [(max(abs(a-x), abs(b-y)), t) for (a, b), t in named.items()
                        if max(abs(a-x), abs(b-y)) <= rule['radius']]
                if near:
                    closest = min(d for d, _ in near)
                    votes = {}
                    for d, t in near:
                        if d == closest:
                            votes[t] = votes.get(t, 0) + 1
                    ranked = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
                    if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
                        town, how = ranked[0][0], 'nearest'
        node['town'], node['district'] = town, district
        node['townRule'] = how if town else None
        if not town:
            unattached.append(key)
    return sorted(unattached)


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


def assemble(services, game, profile, policy, snapshot, world=None, settings=None,
             reference=None):
    network = build(services, game, profile, policy, world, settings, reference)
    formula = None
    if settings:
        formula = TRAVEL_FORMULA | {'settings': {name: settings[name]
                                                 for name in TRAVEL_FORMULA['gameSettings']}}
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'policyVersion': policy['policyVersion'],
        'toggles': {
            'mageGuildMember': {
                'default': True, 'appliesTo': 'all',
                'note': 'Off removes every edge with requiresMageGuild. Silt striders, '
                        'pack guars, sky lamps, carriages, boats, gondolas and riverstriders '
                        'are untouched.'},
            'conjurerRank': {
                'default': False, 'appliesTo': policy['conjurerRank']['profiles'],
                'note': 'Off removes every edge with requiresConjurer. These are edges, '
                        'not providers: the short-range guide in each of the four cities '
                        'keeps working.'}},
        'authored': {'guildGuide': policy['guildGuide'], 'conjurerRank': policy['conjurerRank'],
                     'towns': policy.get('towns'), 'source': 'authored'},
        'travelFormula': formula,
        'barterFormula': BARTER_FORMULA if settings else None,
        'verification': network['verification'],
        'nodes': network['nodes'], 'providers': network['providers'],
        'coverage': 'Transport providers and the journeys they sell, from static service '
                    'flags and actor destination lists, with the price before barter and '
                    'the hours each journey takes as the travel window works them out, the '
                    'seller side of the barter formula, and the town each stop belongs to. '
                    'No schedules, no dialogue or script evaluation, and no teleport '
                    'doors: walking routes are a separate and far larger graph. A rank '
                    'requirement and a town override are authored, not extracted, because '
                    'the records carry neither.',
        'builtAtUnix': time.time(), 'edges': network['edges']}


def game_settings(catalogs, profile):
    path = Path(catalogs)/profile/'GameSettings.json'
    if not path.is_file():
        raise ExportError(f'GameSettings catalog missing: {path}')
    return {r['id']: r['value'] for r in json.loads(path.read_text(encoding='utf-8'))['records']}


def check_travel_transcription(versions):
    """Refuse to price journeys with a travel window copied from another engine release."""
    labelled = versions.get('vanilla', '')
    if not label_carries(labelled, TRANSCRIBED_FROM):
        raise ExportError(
            f'The travel price and time were transcribed from OpenMW {TRANSCRIBED_FROM}, but '
            f'this extraction is for {labelled!r}.\n  Compare TravelWindow::addDestination and '
            'TravelWindow::onTravelButtonClick (apps/openmw/mwgui/travelwindow.cpp) between '
            'the two releases. If they are unchanged, set TRANSCRIBED_FROM in '
            'build_travel_catalog.py to the new version; if not, transcribe them again.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--foundation-database', type=Path)
    parser.add_argument('--world-database', type=Path,
                        help='Where the vehicles at each stop are read from; world/world.sqlite')
    parser.add_argument('--catalogs', type=Path,
                        help='Catalog release, for game settings and autocalc inputs')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        policy = load_travel_policy(args.policy or ROOT/'policy/travel.json')
        catalogs = args.catalogs
        if catalogs is None:
            pointer = root/'catalogs/current.json'
            if not pointer.is_file():
                raise ExportError('No catalog release found; pass --catalogs')
            catalogs = root/'catalogs'/json.loads(pointer.read_text(encoding='utf-8'))['releaseId']
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        paths = (args.services_database or root/'services/services.sqlite',
                 args.foundation_database or root/'game-data.sqlite',
                 args.world_database or root/'world/world.sqlite')
        written = []
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(
                    sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                dbs.append(db)
            services, game, world = dbs
            versions = {p['world']: p['version'] for p in metadata(game)['profiles']}
            check_travel_transcription(versions)
            check_transcription(versions)
            snapshot = metadata(services).get('snapshotId')
            # Vehicles come from the world catalog; a mismatched one would describe some
            # other extraction's stops.
            world_snapshot = metadata(world).get('snapshotId')
            if snapshot and world_snapshot and snapshot != world_snapshot:
                raise ExportError(f'services ({snapshot[:12]}) and world ({world_snapshot[:12]}) '
                                  'come from different extractions; rebuild the older one first')
            for profile in profiles:
                payload = assemble(services, game, profile, policy, snapshot, world,
                                   game_settings(catalogs, profile),
                                   autocalc.reference(catalogs, profile))
                destination, size = publish(payload, args.output or root/'travel', profile)
                check = payload['verification']
                print(f'{profile}: {check["edges"]} edges, {check["nodes"]} cells, '
                      f'{check["providers"]} providers ({check["guildGuides"]} guild guides, '
                      f'{check["conjurerEdges"]} Conjurer edges), {size/1024:.0f} KB', flush=True)
                if check['vehicleModes']:
                    print('  by vehicle: ' + ', '.join(f'{n} {mode}' for mode, n in check['vehicleModes'].items())
                          + (f'; no vehicle at {len(check["operatorsWithoutVehicle"])} stop(s): '
                             + ', '.join(check['operatorsWithoutVehicle']) if check['operatorsWithoutVehicle'] else ''),
                          flush=True)
                print(f'  {check["towns"]} towns; ' + (
                    f'{len(check["stopsWithoutTown"])} stop(s) in no town: '
                    + ', '.join(check['stopsWithoutTown']) if check['stopsWithoutTown']
                    else 'every stop is in a town'), flush=True)
                if check['edgesWithoutPrice'] or check['providersWithoutBarterStats']:
                    print(f'  unpriced: {len(check["edgesWithoutPrice"])} edge(s) with no '
                          f'position, {len(check["providersWithoutBarterStats"])} provider(s) '
                          'with no barter stats', flush=True)
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
