"""How to get to every place: the doors out of each interior, and where land is.

Routing to a tomb or a cave needs two facts the other catalogs lack. First, the way
in: which chain of doors leads from the outside to that room, and where outside it
starts. That is worked out here as the shortest door chain from each interior to an
exterior, read backwards. Second, whether a straight walk between two points stays on
land. Every exterior cell's height grid is reduced to an 8 x 8 land mask, so the site
can refuse a walk that would swim open sea without shipping the terrain.

Neither is a path over the terrain. OpenMW builds its navigation mesh only while the
game runs, so a walk here is a straight line, and says so.
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
import struct
import tempfile
import time

from build_acquisition_index import metadata
from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'

# ESM::Land: a 65 x 65 grid of vertices per cell, heights stored as a float offset and
# signed byte deltas, scaled by 8 (components/esm3/loadland.cpp, Land::loadData).
LAND_SIZE = 65
HEIGHT_SCALE = 8
CELL_SIZE = 8192
# The mask: 8 x 8 blocks of 1024 units. A block is land when any of its vertices stands
# above the water line, so a river, a canal or a bridge's footing does not break a walk.
MASK = 8
WATER_LEVEL = 0
# How many exits a room keeps: a tomb with three doors out needs the nearest, not all.
MAX_EXITS = 4

GRID = re.compile(r'^exterior:(-?\d+),(-?\d+)$')

WALKING = {
    'source': 'authored',
    'transcribedFrom': 'OpenMW 0.51.0',
    'functions': 'Npc::getWalkSpeed and Npc::getRunSpeed, apps/openmw/mwclass/npc.cpp',
    'note': 'Walk speed is fMinWalkSpeed + 0.01 x Speed x (fMaxWalkSpeed - fMinWalkSpeed), '
            'times 1 - fEncumberedMoveEffect x the load carried over the load allowed. Run '
            'speed is that times 0.01 x Athletics x fAthleticsRunBonus + fBaseRunMultiplier. '
            'Game time runs timescale times faster than real time. A walk here is a '
            'straight line between two points, so real routes around hills and water take '
            'longer.',
    'gameSettings': ['fMinWalkSpeed', 'fMaxWalkSpeed', 'fEncumberedMoveEffect',
                     'fAthleticsRunBonus', 'fBaseRunMultiplier'],
    'timescale': 30,
    'timescaleNote': 'The starting value of the timescale global; a mod or a script can change it.',
}


def heights(vhgt):
    """ESM::Land::loadData: the 65 x 65 heights, rows south to north, in game units."""
    if len(vhgt) < 4 + LAND_SIZE * LAND_SIZE:
        return None
    offset = struct.unpack_from('<f', vhgt, 0)[0]
    deltas = struct.unpack_from(f'<{LAND_SIZE * LAND_SIZE}b', vhgt, 4)
    out = [0.0] * (LAND_SIZE * LAND_SIZE)
    row = offset
    for y in range(LAND_SIZE):
        row += deltas[y * LAND_SIZE]
        out[y * LAND_SIZE] = row * HEIGHT_SCALE
        column = row
        for x in range(1, LAND_SIZE):
            column += deltas[y * LAND_SIZE + x]
            out[y * LAND_SIZE + x] = column * HEIGHT_SCALE
    return out


def subrecord(payload, tag):
    """The first subrecord with this tag, or None."""
    at = 0
    while at + 8 <= len(payload):
        name, size = payload[at:at + 4], int.from_bytes(payload[at + 4:at + 8], 'little')
        if name == tag:
            return payload[at + 8:at + 8 + size]
        at += 8 + size
    return None


def land_mask(grid):
    """64 bits, block (bx, by) at bit by x 8 + bx, as 16 hex digits. None when all water."""
    step = (LAND_SIZE - 1) // MASK
    bits = 0
    for by in range(MASK):
        for bx in range(MASK):
            if any(grid[y * LAND_SIZE + x] > WATER_LEVEL
                   for y in range(by * step, by * step + step + 1)
                   for x in range(bx * step, bx * step + step + 1)):
                bits |= 1 << (by * MASK + bx)
    return f'{bits:016x}' if bits else None


def load_land(game, profile):
    """Each exterior cell's mask. A cell with no LAND record, or no heights, is sea."""
    masks = {}
    for key, payload, deleted in game.execute(
            'SELECT rv.record_key, rv.payload, rv.deleted FROM resolved_records rr '
            'JOIN record_versions rv ON rv.id = rr.winner_id '
            "WHERE rr.profile_id = ? AND rr.record_type = 'LAND'", (profile,)):
        if deleted or not GRID.match(key or ''):
            continue
        vhgt = subrecord(payload, b'VHGT')
        grid = heights(vhgt) if vhgt else None
        mask = land_mask(grid) if grid else None
        if mask:
            masks[key] = mask
    return masks


def load_doors(services, profile):
    """Each cell's teleport doors in placement order: (destination, x, y)."""
    doors = {}
    for origin, destination, x, y in services.execute(
            'SELECT d.from_cell_key, p.to_cell_key, d.x, d.y '
            'FROM profile_door_links p JOIN door_links d '
            ' ON d.placement_version_id = p.placement_version_id '
            "WHERE p.profile_id = ? AND p.status = 'resolved' AND p.to_cell_key IS NOT NULL "
            'ORDER BY d.from_cell_key, d.placement_version_id', (profile,)):
        doors.setdefault(origin, []).append((destination, x, y))
    return doors


def exits_of(cell, doors):
    """Where the doors of this room let you out, distinct to the nearest 256 units."""
    seen, out = set(), []
    for destination, x, y in doors.get(cell, ()):
        if not destination.startswith('exterior:') or x is None or y is None:
            continue
        point = [round(x), round(y)]
        mark = (point[0] // 256, point[1] // 256)
        if mark in seen:
            continue
        seen.add(mark)
        out.append(point)
        if len(out) == MAX_EXITS:
            break
    return out


def access(interiors, doors):
    """For every interior, the fewest doors to the outside, and the room to go through.

    A breadth-first search outward from every room with a door outdoors. A room's
    `via` is the next room towards the outside; following `via` from a tomb's depths
    and reading the list backwards is the way in. Ties go to the room first in
    case-insensitive name order, so the answer is stable.
    """
    inward = {}
    for origin, links in doors.items():
        for destination, _x, _y in links:
            if destination.startswith('interior:') and origin.startswith('interior:'):
                inward.setdefault(destination, set()).add(origin)
    depth, via, outer = {}, {}, {}
    frontier = sorted((c for c in interiors if exits_of(c, doors)), key=str.casefold)
    for cell in frontier:
        depth[cell], outer[cell] = 0, cell
    level = 0
    while frontier:
        level += 1
        found = {}
        for cell in frontier:
            for room in sorted(inward.get(cell, ()), key=str.casefold):
                if room not in depth and room not in found:
                    found[room] = cell
        for room, through in found.items():
            depth[room], via[room], outer[room] = level, through, outer[through]
        frontier = sorted(found, key=str.casefold)
    records = []
    for cell in sorted(interiors):
        if cell not in depth:
            records.append({'key': cell, 'depth': None, 'exits': []})
            continue
        record = {'key': cell, 'depth': depth[cell], 'exits': exits_of(outer[cell], doors)}
        if cell in via:
            record['via'] = via[cell]
        records.append(record)
    return records


def assemble(services, game, profile, snapshot):
    interiors = [key for key, in services.execute(
        "SELECT cell_key FROM cells WHERE profile_id = ? AND interior = 1 ORDER BY cell_key",
        (profile,))]
    if not interiors:
        raise ExportError(f'No interior cells for profile {profile}; build the services catalog first')
    records = access(interiors, load_doors(services, profile))
    land = load_land(game, profile)
    if not land:
        raise ExportError(f'{profile}: no LAND heights at all; check the extraction')
    reached = [r for r in records if r['depth'] is not None]
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'walking': WALKING,
        'landMask': {'blocks': MASK, 'blockSize': CELL_SIZE // MASK, 'waterLevel': WATER_LEVEL,
                     'bitOrder': 'bit by x 8 + bx, bx west to east and by south to north, '
                                 'in 16 hex digits; a cell absent from land is sea',
                     'source': 'VHGT heights, components/esm3/loadland.cpp'},
        'land': dict(sorted(land.items())),
        'derivation': {
            'method': 'shortest door chain from each interior to an exterior; every '
                      "exterior cell's height grid reduced to a land mask",
            'interiors': len(records), 'reachable': len(reached),
            'sealed': len(records) - len(reached),
            'deepest': max((r['depth'] for r in reached), default=0),
            'landCells': len(land)},
        'coverage': 'For every interior, the next room towards the outside (via), how many '
                    'doors away the outside is (depth) and up to four points outdoors its '
                    'nearest exit opens onto (exits). Depth null means no door leads out: '
                    'reached by a script or a spell, or not at all. The land mask says '
                    'where a straight walk stays out of the sea; it is not a path over the '
                    'terrain. Doors are assumed to work both ways, as nearly all do.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.access-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--foundation-database', type=Path, help='Where LAND heights are read')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
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
                payload = assemble(services, game, profile, snapshot)
                destination, size = publish(payload, args.output or root/'access', profile)
                d = payload['derivation']
                print(f'{profile}: {d["reachable"]} of {d["interiors"]} interiors reach the '
                      f'outside ({d["sealed"]} sealed, deepest {d["deepest"]} doors), '
                      f'{d["landCells"]} land cells, {size/1024:.0f} KB', flush=True)
                written.append(destination)
        print('Access catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error, struct.error) as exc:
        print(f'Access catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
