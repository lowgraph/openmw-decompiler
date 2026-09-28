"""How to get to every place: the doors out of each interior, and where land is.

Routing to a tomb or a cave needs two facts the other catalogs lack. First, the way
in: which chain of doors leads from the outside to that room, and where outside it
starts. That is worked out here as the shortest door chain from each interior to an
exterior, read backwards. Second, whether a straight walk between two points stays on
land. Every exterior cell's height grid is reduced to an 8 x 8 land mask, so the site
can refuse a walk that would swim open sea without shipping the terrain.

Third, where a walk can go. The same heights are graded into a coarser walkable grid:
land, too steep to climb (steeper than OpenMW lets an actor walk), water near enough to
land to swim, and open sea. Walls the terrain cannot show, such as the Ghostfence, come
from policy/walking.json. The site finds paths over it. OpenMW builds its navigation
mesh only while the game runs, from meshes too, so rocks and buildings are not in it.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack, closing
import hashlib
import json
import math
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

VERSION = '1.2.0'
POLICY_VERSION = '1.0.0'
PROFILES = ('vanilla', 'tr', 'tr_arce')

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

# The steepest ground an actor walks up: Constants::sMaxSlope (components/misc/constants.hpp)
# as isWalkableSlope reads it (apps/openmw/mwphysics/stepper.cpp: a plane whose normal's z
# is at most cos 46 degrees is not walkable). Checked at tag openmw-0.51.0.
TRANSCRIBED_FROM = '0.51.0'
MAX_SLOPE_DEGREES = 46.0
# Terrain vertices are 128 units apart; each quad of four is two triangles.
QUAD = CELL_SIZE // (LAND_SIZE - 1)
# The walkable grid's codes, two bits a square.
SEA, LAND, BLOCKED, SWIM = 0, 1, 2, 3
CODES = {str(SEA): 'open sea', str(LAND): 'land', str(BLOCKED): 'too steep, or a wall',
         str(SWIM): 'water near enough to land to swim'}

WALKING = {
    'source': 'authored',
    'transcribedFrom': 'OpenMW 0.51.0',
    'functions': 'Npc::getWalkSpeed and Npc::getRunSpeed, apps/openmw/mwclass/npc.cpp',
    'note': 'Walk speed is fMinWalkSpeed + 0.01 x Speed x (fMaxWalkSpeed - fMinWalkSpeed), '
            'times 1 - fEncumberedMoveEffect x the load carried over the load allowed. Run '
            'speed is that times 0.01 x Athletics x fAthleticsRunBonus + fBaseRunMultiplier. '
            'Game time runs timescale times faster than real time. A walk follows the '
            'walkable grid around steep ground and open sea where the release has one, and '
            'is a straight line where it does not.',
    'swimNote': 'Swim speed is the run speed times fSwimRunBase + 0.01 x Athletics x '
                'fSwimRunAthleticsMult, and more with Swift Swim (getSwimSpeedImpl, '
                'apps/openmw/mwclass/actor.hpp).',
    'gameSettings': ['fMinWalkSpeed', 'fMaxWalkSpeed', 'fEncumberedMoveEffect',
                     'fAthleticsRunBonus', 'fBaseRunMultiplier', 'fSwimRunBase',
                     'fSwimRunAthleticsMult'],
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


def load_heights(game, profile):
    """Each exterior cell's heights by grid position. A cell with no LAND record, or no
    heights, is left out: it is sea."""
    cells = {}
    for key, payload, deleted in game.execute(
            'SELECT rv.record_key, rv.payload, rv.deleted FROM resolved_records rr '
            'JOIN record_versions rv ON rv.id = rr.winner_id '
            "WHERE rr.profile_id = ? AND rr.record_type = 'LAND'", (profile,)):
        match = GRID.match(key or '')
        if deleted or not match:
            continue
        vhgt = subrecord(payload, b'VHGT')
        grid = heights(vhgt) if vhgt else None
        if grid:
            cells[(int(match[1]), int(match[2]))] = grid
    return cells


def land_masks(cells):
    """Each exterior cell's mask, keyed as the other catalogs key cells."""
    masks = {}
    for (x, y), grid in cells.items():
        mask = land_mask(grid)
        if mask:
            masks[f'exterior:{x},{y}'] = mask
    return masks


def grade_cell(grid, per_cell, steep_share):
    """One cell's squares, south-west first and row by row: SEA, LAND or BLOCKED.

    A square is land when any of its vertices stands above the water line, as the mask
    reads it, and blocked when at least `steep_share` of its triangles are steeper than
    MAX_SLOPE_DEGREES. Each quad is split along the same diagonal; a triangle is too
    steep when its rise over 128 units, squared across both axes, passes tan(46°)².
    """
    quads = (LAND_SIZE - 1) // per_cell
    limit = (math.tan(math.radians(MAX_SLOPE_DEGREES)) * QUAD) ** 2
    needed = steep_share * 2 * quads * quads
    out = bytearray(per_cell * per_cell)
    for sy in range(per_cell):
        for sx in range(per_cell):
            land, steep = False, 0
            for qy in range(sy * quads, sy * quads + quads):
                row, above = qy * LAND_SIZE, (qy + 1) * LAND_SIZE
                for qx in range(sx * quads, sx * quads + quads):
                    a, b = grid[row + qx], grid[row + qx + 1]
                    c, d = grid[above + qx], grid[above + qx + 1]
                    if not land and max(a, b, c, d) > WATER_LEVEL:
                        land = True
                    if (b - a) ** 2 + (c - a) ** 2 > limit:
                        steep += 1
                    if (d - c) ** 2 + (d - b) ** 2 > limit:
                        steep += 1
            if land:
                out[sy * per_cell + sx] = BLOCKED if steep >= needed else LAND
    return out


def placed(world, profile, prefix):
    """(x, y) of every exterior placement whose object id starts with `prefix`."""
    prefix = prefix.lower()
    end = prefix[:-1] + chr(ord(prefix[-1]) + 1)
    # CROSS JOIN, as build_teleport_catalog.placements: by object first, through its index.
    return [(x, y) for x, y in world.execute(
        'SELECT p.x, p.y FROM placements p '
        'CROSS JOIN profile_placements pp ON pp.profile_id = ? AND pp.reference_key = p.reference_key '
        ' AND pp.version_id = p.version_id '
        "WHERE p.object_key >= ? AND p.object_key < ? AND p.cell_key LIKE 'exterior:%' "
        ' AND p.x IS NOT NULL AND p.y IS NOT NULL ORDER BY p.x, p.y', (profile, prefix, end))]


def opening_squares(openings, radius, size):
    """Squares whose middle is within `radius` of an opening: a gate's built passage."""
    reach = math.ceil(radius / size)
    out = set()
    for ox, oy in openings:
        gx, gy = math.floor(ox / size), math.floor(oy / size)
        for x in range(gx - reach, gx + reach + 1):
            for y in range(gy - reach, gy + reach + 1):
                if math.hypot((x + 0.5) * size - ox, (y + 0.5) * size - oy) <= radius:
                    out.add((x, y))
    return out


def barrier_squares(pieces, openings, barrier, size):
    """The squares a ring-shaped wall covers, and a report of how it was joined.

    Pieces are put in order by their angle around the ring's middle and each is joined to
    the next, the last back to the first, by a straight line. A pair further apart than
    maxGap is not joined, and counted. Squares within openingRadius of an opening stay
    open; walkable() makes them land whatever the terrain says, as a gate is built.
    """
    report = {'name': barrier['name'], 'pieces': 0, 'joined': 0, 'unjoined': 0, 'squares': 0}
    if not pieces:
        return set(), report
    mx = sum(x for x, _ in pieces) / len(pieces)
    my = sum(y for _, y in pieces) / len(pieces)
    ring = sorted(set(pieces), key=lambda p: (math.atan2(p[1] - my, p[0] - mx), p))
    squares = set()
    for i, (ax, ay) in enumerate(ring):
        bx, by = ring[(i + 1) % len(ring)]
        length = math.hypot(bx - ax, by - ay)
        if length > barrier['maxGap']:
            report['unjoined'] += 1
            continue
        report['joined'] += 1
        steps = max(1, math.ceil(length / (size / 4)))
        for step in range(steps + 1):
            x, y = ax + (bx - ax) * step / steps, ay + (by - ay) * step / steps
            squares.add((math.floor(x / size), math.floor(y / size)))
    squares -= opening_squares(openings, barrier['openingRadius'], size)
    report.update(pieces=len(ring), squares=len(squares))
    return squares, report


def encode(codes):
    """Two bits a square, four squares a byte with the first in the low bits; base64."""
    packed = bytearray((len(codes) + 3) // 4)
    for index, code in enumerate(codes):
        packed[index >> 2] |= code << ((index & 3) * 2)
    return base64.b64encode(bytes(packed)).decode('ascii')


def walkable(cells, policy, walls=(), gates=()):
    """The walkable grid, {(x, y): codes}, for every cell with land or water near it.

    Walls turn their squares BLOCKED and gates turn theirs LAND. Water within swimReach
    squares of land (Chebyshev, across cell borders) is SWIM; the rest is SEA, and a
    cell all sea is left out.
    """
    per, reach = policy['squaresPerCell'], policy['swimReach']
    graded = {cell: grade_cell(grid, per, policy['steepShare']) for cell, grid in cells.items()}
    for squares, code in ((walls, BLOCKED), (gates, LAND)):
        for gx, gy in squares:
            codes = graded.get((gx // per, gy // per))
            if codes is not None:
                codes[(gy % per) * per + gx % per] = code
    ground = {(cx * per + i % per, cy * per + i // per)
              for (cx, cy), codes in graded.items() for i, code in enumerate(codes) if code != SEA}
    near = {(cx + dx, cy + dy) for cx, cy in graded for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    offsets = [(dx, dy) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1)]
    out = {}
    for cx, cy in sorted(near):
        codes = graded.get((cx, cy)) or bytearray(per * per)
        for index, code in enumerate(codes):
            if code == SEA:
                gx, gy = cx * per + index % per, cy * per + index // per
                if any((gx + dx, gy + dy) in ground for dx, dy in offsets):
                    codes[index] = SWIM
        if any(codes):
            out[(cx, cy)] = codes
    return out


def load_walking_policy(path):
    policy = json.loads(Path(path).read_text(encoding='utf-8'))
    if policy.get('schemaVersion') != POLICY_VERSION:
        raise ExportError(f'Unsupported walking policy schema {policy.get("schemaVersion")!r}')
    number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    whole = lambda v: isinstance(v, int) and not isinstance(v, bool)
    if not isinstance(policy.get('policyVersion'), str) or not policy['policyVersion'].strip():
        raise ExportError('Walking policy needs a policyVersion')
    per = policy.get('squaresPerCell')
    if not whole(per) or per < 1 or (LAND_SIZE - 1) % per:
        raise ExportError('Walking policy squaresPerCell must divide 64')
    if not number(policy.get('steepShare')) or not 0 < policy['steepShare'] <= 1:
        raise ExportError('Walking policy steepShare must be above 0 and at most 1')
    if not whole(policy.get('swimReach')) or not 0 <= policy['swimReach'] <= 8:
        raise ExportError('Walking policy swimReach must be a whole number of squares, 0 to 8')
    if not isinstance(policy.get('barriers'), list):
        raise ExportError('Walking policy barriers must be a list')
    names = set()
    for barrier in policy['barriers']:
        ok = (isinstance(barrier, dict) and isinstance(barrier.get('name'), str) and barrier['name'].strip()
              and all(isinstance(barrier.get(k), list) and all(isinstance(v, str) and v.strip() for v in barrier[k])
                      for k in ('objects', 'openings')) and bool(barrier['objects'])
              and all(number(barrier.get(k)) and barrier[k] > 0 for k in ('openingRadius', 'maxGap'))
              and isinstance(barrier.get('why'), str) and bool(barrier['why'].strip())
              and (barrier.get('profiles') is None or (isinstance(barrier['profiles'], list)
                                                       and bool(barrier['profiles'])
                                                       and set(barrier['profiles']) <= set(PROFILES))))
        if not ok:
            raise ExportError('Walking policy barriers need a name, object and opening id prefixes, '
                              'openingRadius, maxGap and why, and profiles if any from '
                              + ', '.join(PROFILES))
        if barrier['name'].casefold() in names:
            raise ExportError(f'Walking policy names the barrier {barrier["name"]!r} twice')
        names.add(barrier['name'].casefold())
    return policy


def walls_for(world, profile, policy):
    """Every barrier's wall squares and gate squares in this profile. A barrier that
    applies here but has no pieces fails the build: a renamed object would otherwise open
    the wall silently."""
    size = CELL_SIZE // policy['squaresPerCell']
    squares, gates, reports = set(), set(), []
    for barrier in policy['barriers']:
        if profile not in barrier.get('profiles', PROFILES):
            continue
        pieces = [p for prefix in barrier['objects'] for p in placed(world, profile, prefix)]
        openings = [p for prefix in barrier['openings'] for p in placed(world, profile, prefix)]
        if not pieces:
            raise ExportError(f'{profile}: the {barrier["name"]} barrier in policy/walking.json matches '
                              'no placement; check its object id prefixes')
        found, report = barrier_squares(pieces, openings, barrier, size)
        report['openings'] = len(openings)
        squares |= found
        opened = opening_squares(openings, barrier['openingRadius'], size)
        report['gateSquares'] = len(opened)
        gates |= opened
        reports.append(report)
    return squares, gates, reports


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

    A sealed room, one no door chain leads out of, lists instead the rooms its doors
    join (`doors`, either way through the door), so a site can walk from it to a room a
    teleport reaches: Mournhold's streets to the room its transport arrives in.
    """
    inward, joined = {}, {}
    for origin, links in doors.items():
        for destination, _x, _y in links:
            if destination.startswith('interior:') and origin.startswith('interior:'):
                inward.setdefault(destination, set()).add(origin)
                if destination != origin:
                    joined.setdefault(origin, set()).add(destination)
                    joined.setdefault(destination, set()).add(origin)
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
            records.append({'key': cell, 'depth': None, 'exits': [],
                            'doors': sorted(joined.get(cell, ()), key=str.casefold)})
            continue
        record = {'key': cell, 'depth': depth[cell], 'exits': exits_of(outer[cell], doors)}
        if cell in via:
            record['via'] = via[cell]
        records.append(record)
    return records


def assemble(services, game, profile, snapshot, world=None, policy=None):
    interiors = [key for key, in services.execute(
        "SELECT cell_key FROM cells WHERE profile_id = ? AND interior = 1 ORDER BY cell_key",
        (profile,))]
    if not interiors:
        raise ExportError(f'No interior cells for profile {profile}; build the services catalog first')
    records = access(interiors, load_doors(services, profile))
    cells = load_heights(game, profile)
    land = land_masks(cells)
    if not land:
        raise ExportError(f'{profile}: no LAND heights at all; check the extraction')
    reached = [r for r in records if r['depth'] is not None]
    payload = {
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
            'sealedWithDoors': sum(1 for r in records if r['depth'] is None and r['doors']),
            'deepest': max((r['depth'] for r in reached), default=0),
            'landCells': len(land)},
        'coverage': 'For every interior, the next room towards the outside (via), how many '
                    'doors away the outside is (depth) and up to four points outdoors its '
                    'nearest exit opens onto (exits). Depth null means no door leads out: '
                    'reached by a script or a spell, or not at all; such a room lists the '
                    'rooms its doors join (doors), to walk to one a teleport reaches. The land mask says '
                    'where a straight walk stays out of the sea; it is not a path over the '
                    'terrain. Doors are assumed to work both ways, as nearly all do.',
        'builtAtUnix': time.time(), 'records': records}
    if policy is None:
        return payload
    walls, gates, barriers = walls_for(world, profile, policy) if world is not None else (set(), set(), [])
    grid = walkable(cells, policy, walls, gates)
    counts = [0, 0, 0, 0]
    for codes in grid.values():
        for code in codes:
            counts[code] += 1
    per = policy['squaresPerCell']
    payload['walkable'] = {
        'policyVersion': policy['policyVersion'],
        'squaresPerCell': per, 'squareSize': CELL_SIZE // per,
        'steepShare': policy['steepShare'], 'swimReach': policy['swimReach'],
        'maxSlopeDegrees': MAX_SLOPE_DEGREES, 'transcribedFrom': f'OpenMW {TRANSCRIBED_FROM}',
        'slopeSource': 'Constants::sMaxSlope, components/misc/constants.hpp, as isWalkableSlope '
                       'reads it in apps/openmw/mwphysics/stepper.cpp',
        'codes': CODES,
        'encoding': 'per cell, two bits a square, four squares a byte with the first in the low '
                    'bits, base64; squares run west to east, then south to north; a cell absent '
                    'is open sea',
        'barriers': barriers,
        'note': 'Terrain heights only: rocks, buildings and trees are meshes this grid does not '
                'see. A path over it goes around steep ground and open sea, not around boulders.',
        'cells': {f'exterior:{x},{y}': encode(codes) for (x, y), codes in sorted(grid.items())}}
    payload['derivation'].update({
        'walkableCells': len(grid), 'landSquares': counts[LAND],
        'blockedSquares': counts[BLOCKED], 'swimSquares': counts[SWIM],
        'wallSquares': sum(b['squares'] for b in barriers)})
    payload['coverage'] += (' The walkable grid grades every square of land walkable or too steep '
                            'from the heights alone, and adds the walls policy/walking.json names.')
    return payload


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
    parser.add_argument('--world-database', type=Path, help='Where barrier placements are read')
    parser.add_argument('--policy', type=Path, help='The walking policy (default policy/walking.json)')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        policy = load_walking_policy(args.policy or ROOT/'policy/walking.json')
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
            snapshot = metadata(services).get('snapshotId')
            for profile in profiles:
                payload = assemble(services, game, profile, snapshot, world, policy)
                destination, size = publish(payload, args.output or root/'access', profile)
                d = payload['derivation']
                print(f'{profile}: {d["reachable"]} of {d["interiors"]} interiors reach the '
                      f'outside ({d["sealed"]} sealed, deepest {d["deepest"]} doors), '
                      f'{d["landCells"]} land cells, {size/1024:.0f} KB', flush=True)
                walls = '; '.join(f'{b["name"]}: {b["pieces"]} pieces, {b["joined"]} joined, '
                                  f'{b["unjoined"]} gaps over maxGap, {b["openings"]} openings, '
                                  f'{b["squares"]} squares' for b in payload['walkable']['barriers'])
                print(f'  walkable: {d["landSquares"]} land squares, {d["blockedSquares"]} too steep '
                      f'or walled, {d["swimSquares"]} to swim' + (f'; {walls}' if walls else ''),
                      flush=True)
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
