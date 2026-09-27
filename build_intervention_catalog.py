"""Where Divine and Almsivi Intervention put you down, from every place in the game.

Both spells teleport to the "closest" marker of their kind: divinemarker for Divine
Intervention, templemarker for Almsivi. OpenMW's idea of closest is not distance.
Outdoors it takes the markers in the smallest square ring of cells around you and
breaks ties by walking the ring from its south-west corner; indoors it walks out
through doors, a cell at a time, and takes a marker it meets inside or else the ring
around the first door that opens outdoors. Both are transcribed from
World::getClosestMarker and getClosestMarkerFromExteriorPosition (see RULE).

The answer depends only on the cell you cast from, so it is worked out here once for
every cell Places publishes, and the site looks it up.
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

from build_acquisition_index import metadata
from build_travel_catalog import assign_towns, load_travel_policy
from export_items import ExportError
from extract_foundation import ROOT, label_carries, load_config

VERSION = '1.0.0'

# The OpenMW release RULE was checked against, line by line, at tag openmw-0.51.0:
# World::getClosestMarker and World::getClosestMarkerFromExteriorPosition in
# apps/openmw/mwworld/worldimp.cpp, WorldModel::getExteriorPtrs in worldmodel.cpp, and
# ESM::positionToExteriorCellLocation in components/esm/util.hpp. It is code, not data;
# check_transcription stops the build when the extraction names another release.
TRANSCRIBED_FROM = '0.51.0'

# The spell, the marker it looks for. The marker ids are hardcoded in the engine.
KINDS = {'divine': 'divinemarker', 'almsivi': 'templemarker'}

CELL_SIZE = 8192

RULE = {
    'source': 'authored',
    'transcribedFrom': f'OpenMW {TRANSCRIBED_FROM}',
    'functions': 'World::getClosestMarker and World::getClosestMarkerFromExteriorPosition, '
                 'apps/openmw/mwworld/worldimp.cpp; WorldModel::getExteriorPtrs, '
                 'apps/openmw/mwworld/worldmodel.cpp',
    'markers': KINDS,
    'cellSize': CELL_SIZE,
    'note': 'Outdoors, the cell you stand in decides. The engine takes one marker per '
            'exterior cell, in grid order; a marker in your own cell wins outright. '
            'Otherwise it keeps the markers on the smallest square ring of cells around '
            'you and, if several share it, the first met walking the ring from its '
            'south-west corner east, then north, then west, then south. Indoors it '
            'searches outward through doors a cell at a time: a marker inside a cell it '
            'reaches wins, and the first door that opens outdoors decides by the ring '
            'around where that door puts you. A place from which no door leads outdoors '
            'and no marker is reachable has no answer; the spell fails there.',
}

GRID = re.compile(r'^exterior:(-?\d+),(-?\d+)$')


def cell_of(x, y):
    """ESM::positionToExteriorCellLocation: floor, not truncation, so -1 is west of 0."""
    return math.floor(x / CELL_SIZE), math.floor(y / CELL_SIZE)


def load_markers(world, profile):
    """Every placed marker of both kinds, in the order the engine meets them.

    getExteriorPtrs walks the exterior cells in grid order and takes the first marker
    in each, so a second marker sharing a cell is never chosen; it is kept here only
    to be reported.
    """
    rows = world.execute(
        'SELECT p.object_key, p.reference_key, p.cell_key, p.x, p.y, p.z, p.version_id '
        'FROM placements p JOIN profile_placements pp '
        ' ON pp.reference_key = p.reference_key AND pp.version_id = p.version_id '
        'WHERE pp.profile_id = ? AND p.object_key IN (?, ?) '
        'ORDER BY p.version_id', (profile, *KINDS.values())).fetchall()
    found = {kind: [] for kind in KINDS}
    by_id = {marker: kind for kind, marker in KINDS.items()}
    for object_key, reference, cell, x, y, z, _version in rows:
        if x is None or y is None:
            continue
        found[by_id[object_key]].append({'reference': reference, 'cell': cell,
                                         'pos': [round(x), round(y), round(z or 0)]})
    return found


def exterior_candidates(markers):
    """(grid x, grid y, index) for the first marker in each exterior cell, grid-ordered."""
    first, shared = {}, []
    for index, marker in enumerate(markers):
        grid = GRID.match(marker['cell'])
        if not grid:
            continue
        where = (int(grid[1]), int(grid[2]))
        if where in first:
            shared.append(marker['reference'])
            continue
        first[where] = index
    return [(x, y, index) for (x, y), index in sorted(first.items())], shared


def closest_from_exterior(where, candidates):
    """getClosestMarkerFromExteriorPosition, for a position in cell `where`."""
    cx, cy = where
    best, valid = None, []
    for x, y, index in candidates:
        dx, dy = x - cx, y - cy
        size = max(abs(dx), abs(dy)) * 2
        if size == 0:
            return index
        if best is None or size <= best:
            if best is None or size < best:
                valid, best = [], size
            valid.append((index, size // 2 + dx, size // 2 + dy))
    if not valid:
        return None
    if len(valid) == 1:
        return valid[0][0]
    chosen, earliest = None, None
    for index, column, row in valid:
        if row == 0:                 # South edge, with the SW and SE corners
            distance = column
        elif column == best:         # East edge and the NE corner
            distance = best + row
        elif row == best:            # North edge and the NW corner
            distance = best * 3 - column
        else:                        # West edge
            distance = best * 4 - row
        if earliest is None or distance < earliest:
            chosen, earliest = index, distance
    return chosen


def load_doors(services, profile):
    """Each cell's teleport doors, in placement order: (destination cell, x, y)."""
    doors = {}
    for origin, destination, x, y in services.execute(
            'SELECT d.from_cell_key, p.to_cell_key, d.x, d.y '
            'FROM profile_door_links p JOIN door_links d '
            ' ON d.placement_version_id = p.placement_version_id '
            "WHERE p.profile_id = ? AND p.status = 'resolved' AND p.to_cell_key IS NOT NULL "
            'ORDER BY d.from_cell_key, d.placement_version_id', (profile,)):
        doors.setdefault(origin, []).append((destination, x, y))
    return doors


def order_key(cell_key):
    """std::set<ESM::RefId> order: interior cell ids compare case-insensitively by name."""
    return cell_key.split(':', 1)[-1].casefold()


def closest_from_interior(cell, doors, inside, candidates):
    """getClosestMarker for a player standing in an interior.

    Returns (index or None, alternatives). The engine takes the first outcome in its
    own cell and door order; that order is reproduced as closely as the data allows,
    and every other outcome at the same depth is returned so a disagreement is visible
    rather than hidden.
    """
    checked, frontier = set(), {cell}
    while frontier:
        current = sorted(frontier, key=order_key)
        frontier = set()
        outcomes = []
        for here in current:
            checked.add(here)
            if here in inside:
                outcomes.append(inside[here])
                continue
            for destination, x, y in doors.get(here, ()):
                if destination.startswith('exterior:'):
                    outcomes.append(closest_from_exterior(cell_of(x, y), candidates))
                elif destination not in checked and destination not in current:
                    frontier.add(destination)
        if outcomes:
            chosen = outcomes[0]
            return chosen, sorted({o for o in outcomes if o != chosen},
                                  key=lambda o: (o is None, o))
    return None, []


def marker_rows(services, profile, markers, towns_rule):
    """What the site shows for each marker: its cell, name and town."""
    names = {key: name for key, name in services.execute(
        'SELECT cell_key, name FROM cells WHERE profile_id = ?', (profile,))}
    nodes = {m['cell']: {'key': m['cell'], 'name': names.get(m['cell']),
                         'interior': m['cell'].startswith('interior:'), 'region': None}
             for m in markers}
    assign_towns(services, profile, nodes, towns_rule)
    return [{'reference': m['reference'], 'cell': m['cell'], 'pos': m['pos'][:2],
             'name': nodes[m['cell']]['name'], 'town': nodes[m['cell']]['town']}
            for m in markers]


def build(services, world, profile, towns_rule=None):
    places = [key for key, in services.execute(
        'SELECT cell_key FROM cells WHERE profile_id = ? ORDER BY cell_key', (profile,))]
    if not places:
        raise ExportError(f'No cells for profile {profile}; build the services catalog first')
    doors = load_doors(services, profile)
    found = load_markers(world, profile)
    records = {key: {'key': key} for key in places}
    derivation, published = {}, {}
    for kind, markers in found.items():
        if not markers:
            raise ExportError(f'{profile}: no {KINDS[kind]} is placed anywhere. The engine '
                              f'would fail every {kind} intervention; check the extraction.')
        candidates, shared = exterior_candidates(markers)
        inside = {}
        for index, marker in enumerate(markers):
            if marker['cell'].startswith('interior:'):
                inside.setdefault(marker['cell'], index)  # searchConst finds one
        isolated = ambiguous = 0
        for key in places:
            grid = GRID.match(key)
            if grid:
                chosen, others = closest_from_exterior((int(grid[1]), int(grid[2])), candidates), []
            else:
                chosen, others = closest_from_interior(key, doors, inside, candidates)
            records[key][kind] = chosen
            if chosen is None:
                isolated += 1
            if others:
                ambiguous += 1
                records[key].setdefault('ambiguous', {})[kind] = others
        published[kind] = marker_rows(services, profile, markers, towns_rule)
        derivation[kind] = {'markers': len(markers), 'exteriorMarkers': len(candidates),
                            'interiorMarkers': len(inside), 'markersSharingACell': shared,
                            'placesWithNoAnswer': isolated,
                            'placesWithAnAmbiguousAnswer': ambiguous}
    return list(records.values()), published, derivation


def assemble(services, world, profile, snapshot, towns_rule=None):
    records, markers, derivation = build(services, world, profile, towns_rule)
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'rule': RULE,
        'markers': markers,
        'derivation': {'method': 'the engine\'s marker search, run from every cell',
                       'places': len(records)} | derivation,
        'coverage': 'For every place, the marker each intervention spell lands on, as an '
                    'index into markers[kind]; null where the spell finds none and fails. '
                    'Worked out from the cell alone, as the engine does. Where the answer '
                    'depends on an order of doors or cells the data only approximates, '
                    'the other possible markers are listed under ambiguous. Nothing here '
                    'checks whether the character has the spell or a scroll.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.intervention-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def check_transcription(versions):
    """Refuse to place interventions with a marker search copied from another release."""
    labelled = versions.get('vanilla', '')
    if not label_carries(labelled, TRANSCRIBED_FROM):
        raise ExportError(
            f'The intervention marker search was transcribed from OpenMW {TRANSCRIBED_FROM}, '
            f'but this extraction is for {labelled!r}.\n  Compare World::getClosestMarker and '
            'World::getClosestMarkerFromExteriorPosition (apps/openmw/mwworld/worldimp.cpp) '
            'between the two releases. If they are unchanged, set TRANSCRIBED_FROM in '
            'build_intervention_catalog.py to the new version; if not, transcribe them again.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--policy', type=Path, help='Travel policy, for its town rule')
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--world-database', type=Path)
    parser.add_argument('--foundation-database', type=Path,
                        help='Only read for the OpenMW release the extraction names')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        policy = load_travel_policy(args.policy or ROOT/'policy/travel.json')
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        paths = (args.services_database or root/'services/services.sqlite',
                 args.world_database or root/'world/world.sqlite',
                 args.foundation_database or root/'game-data.sqlite')
        written = []
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(
                    sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                dbs.append(db)
            services, world, game = dbs
            check_transcription({p['world']: p['version'] for p in metadata(game)['profiles']})
            snapshot = metadata(services).get('snapshotId')
            world_snapshot = metadata(world).get('snapshotId')
            if snapshot and world_snapshot and snapshot != world_snapshot:
                raise ExportError(f'services ({snapshot[:12]}) and world ({world_snapshot[:12]}) '
                                  'come from different extractions; rebuild the older one first')
            for profile in profiles:
                payload = assemble(services, world, profile, snapshot, policy.get('towns'))
                destination, size = publish(payload, args.output or root/'intervention', profile)
                parts = []
                for kind in KINDS:
                    d = payload['derivation'][kind]
                    parts.append(f'{kind} {d["markers"]} markers, {d["placesWithNoAnswer"]} places '
                                 f'with none, {d["placesWithAnAmbiguousAnswer"]} ambiguous')
                print(f'{profile}: {payload["derivation"]["places"]} places; '
                      + '; '.join(parts) + f', {size/1024:.0f} KB', flush=True)
                written.append(destination)
        print('Intervention catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Intervention catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
