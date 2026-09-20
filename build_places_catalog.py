"""Build the places every other catalog points at.

Gear rows, merchants and travel all identify somewhere by `cellKey`, and until now
only Travel's own endpoints carried a name. This publishes every cell: what it is
called, whether it is inside, which region it sits in, and where on the world grid.

Named exterior cells are also grouped into settlements, because a town is several
grid squares sharing one name — Port Telvannis is seven — and "which cells are
Balmora" is a question three other catalogs need answered.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from build_acquisition_index import metadata
from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'


def cells(services, profile):
    return services.execute(
        'SELECT cell_key, name, interior, grid_x, grid_y, region_key, synthetic '
        'FROM cells WHERE profile_id = ? ORDER BY cell_key', (profile,)).fetchall()


def place(key, name, interior, x, y, region, synthetic):
    """One cell. Absent fields are left out rather than published as null.

    Most exterior cells are unnamed wilderness carrying only a region, and spelling
    out four nulls apiece across 4,801 of them costs more than everything else here.
    """
    record = {'key': key, 'interior': bool(interior)}
    if name:
        record['name'] = name
    if region:
        record['region'] = region
    if not interior:
        record['grid'] = [x, y]
    if synthetic:
        # A cell the extraction inferred from a reference rather than read from a
        # CELL record. Rare, and worth flagging rather than passing off as read.
        record['synthetic'] = True
    return record


def settlements(rows):
    """Named exterior cells grouped by name: a town is several grid squares."""
    grouped = defaultdict(list)
    for key, name, interior, x, y, _region, _synthetic in rows:
        if name and not interior and x is not None and y is not None:
            grouped[name].append((key, x, y))
    found = []
    for name in sorted(grouped):
        members = sorted(grouped[name])
        xs = [x for _, x, _ in members]
        ys = [y for _, _, y in members]
        found.append({
            'name': name, 'cells': [key for key, _, _ in members],
            # The rounded middle of the bounding box: good enough to point at, and
            # honestly not a claim about where the town centre is.
            'centre': [(min(xs)+max(xs))//2, (min(ys)+max(ys))//2],
            'bounds': {'minX': min(xs), 'maxX': max(xs),
                       'minY': min(ys), 'maxY': max(ys)}})
    return found


def regions(rows):
    counted = defaultdict(int)
    for _key, _name, _interior, _x, _y, region, _synthetic in rows:
        if region:
            counted[region] += 1
    return [{'key': key, 'cells': counted[key]} for key in sorted(counted)]


def assemble(services, profile, snapshot):
    rows = cells(services, profile)
    if not rows:
        raise ExportError(f'No cells for profile {profile}; build the services catalog first')
    records = [place(*row) for row in rows]
    towns = settlements(rows)
    named = sum(1 for r in records if r.get('name'))
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'derivation': {
            'method': 'every cell the profile resolves, with settlements grouped by the '
                      'name their exterior cells share',
            'places': len(records), 'named': named,
            'interiors': sum(1 for r in records if r['interior']),
            'exteriors': sum(1 for r in records if not r['interior']),
            'settlements': len(towns),
            'settlementsSpanningSeveralCells': sum(1 for t in towns if len(t['cells']) > 1),
            'regions': len(regions(rows)),
            'synthetic': sum(1 for r in records if r.get('synthetic'))},
        'regions': regions(rows),
        'settlements': towns,
        'coverage': 'Names, regions and grid positions for every cell, so a cellKey from '
                    'any other catalog can be shown as somewhere. An absent name means '
                    'the cell has none -- most exterior wilderness does -- and an absent '
                    'region means the record carries none, which is normal for interiors. '
                    'Nothing here knows what is inside a cell, how to walk between cells, '
                    'or where within a cell anything stands.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.places-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--services-database', type=Path)
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        path = args.services_database or root/'services/services.sqlite'
        written = []
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as services:
            services.execute('PRAGMA temp_store=MEMORY')
            snapshot = metadata(services).get('snapshotId')
            for profile in profiles:
                payload = assemble(services, profile, snapshot)
                destination, size = publish(payload, args.output or root/'places', profile)
                counts = payload['derivation']
                print(f'{profile}: {counts["places"]} places ({counts["interiors"]} inside, '
                      f'{counts["exteriors"]} outside), {counts["named"]} named, '
                      f'{counts["settlements"]} settlements, {counts["regions"]} regions, '
                      f'{size/1024:.0f} KB', flush=True)
                written.append(destination)
        print('Places catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Places catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
