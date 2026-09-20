"""Build the factions, their ranks, and what each rank asks of you.

47 factions own placements in Tamriel Rebuilt and 14 in vanilla, and until now none of
them resolved to anything. The policy layer already asks whether an item is
faction-owned and answers with a single `assumeFactionAccess` boolean; this is what
would let it say *which* faction, and what joining it actually costs.

The requirements are read from the FADT subrecord, 240 bytes laid out as two favoured
attributes, ten ranks of five numbers each, seven faction skills and a flags word. See
components/esm3/loadfact.hpp.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import struct
import tempfile
import time

from build_acquisition_index import metadata
from export_items import ExportError
from extract_foundation import ROOT, fields, load_config

VERSION = '1.0.0'
RANKS = 10
FACTION_SKILLS = 7
# FADTstruct: 2 attribute ids, 10 x RankData(5 ints), 7 skill ids, flags.
FADT_SIZE = (2 + RANKS*5 + FACTION_SKILLS + 1) * 4
HIDDEN = 1
UNUSED = -1


def reference(catalogs, profile):
    """Attribute and skill names by index; the record stores numbers."""
    loaded = {}
    for name in ('Attributes', 'Skills'):
        path = Path(catalogs)/profile/(name+'.json')
        if not path.is_file():
            raise ExportError(f'Catalog missing for factions: {path}')
        loaded[name] = json.loads(path.read_text(encoding='utf-8'))['records']
    return {'attributes': {r['index']: r['id'] for r in loaded['Attributes']},
            'skills': {int(r['key']): r['skill'] for r in loaded['Skills']}}


def named(index, table):
    """A name for an index, or None when the record says the slot is unused."""
    if index is None or index < 0:
        return None
    return table.get(index)


def rank(values, position, names, reference_data):
    attribute1, attribute2, primary, favoured, reputation = values
    return {'index': position,
            'name': names[position] if position < len(names) else None,
            # Both favoured attributes must reach these.
            'attribute1': attribute1, 'attribute2': attribute2,
            # One faction skill at primarySkill, two more at favouredSkill.
            'primarySkill': primary, 'favouredSkill': favoured,
            'reputation': reputation}


def parse(payload, encoding, reference_data):
    """One FACT record: name, rank names, requirements, skills and reactions."""
    name, rank_names, data, reactions = None, [], None, {}
    pending = None
    for tag, value, _start, _end in fields(payload):
        raw = bytes(value)
        if tag == 'FNAM':
            name = raw.split(b'\0', 1)[0].decode(encoding, 'replace')
        elif tag == 'RNAM':
            rank_names.append(raw.split(b'\0', 1)[0].decode(encoding, 'replace').strip())
        elif tag == 'FADT':
            if len(raw) != FADT_SIZE:
                raise ExportError(f'FADT is {len(raw)} bytes, expected {FADT_SIZE}')
            data = struct.unpack(f'<{FADT_SIZE//4}i', raw)
        elif tag == 'ANAM':
            pending = raw.split(b'\0', 1)[0].decode(encoding, 'replace')
        elif tag == 'INTV' and pending is not None:
            reactions[pending] = struct.unpack('<i', raw)[0]
            pending = None
    if data is None:
        raise ExportError('Faction record has no FADT')
    attributes = [named(i, reference_data['attributes']) for i in data[:2]]
    ranks = [rank(data[2 + position*5:7 + position*5], position, rank_names, reference_data)
             for position in range(RANKS)]
    skills = [named(i, reference_data['skills'])
              for i in data[2 + RANKS*5:2 + RANKS*5 + FACTION_SKILLS]]
    flags = data[-1]
    # A rank nobody can hold is padding, not a rank: the record always carries ten.
    joinable = [r for r in ranks if r['name']]
    return {'name': name, 'favouredAttributes': [a for a in attributes if a],
            'skills': [s for s in skills if s],
            'ranks': joinable, 'rankCount': len(joinable),
            'hidden': bool(flags & HIDDEN), 'flagsRaw': flags,
            'reactions': [{'faction': key.casefold(), 'adjustment': value}
                          for key, value in sorted(reactions.items())]}


def owners(world, profile):
    """How many placements each faction owns, which is why this catalog exists."""
    counted = {}
    for key, count in world.execute(
            'SELECT pl.faction_key, COUNT(*) FROM profile_placements pp '
            'JOIN placements pl ON pl.version_id = pp.version_id '
            'WHERE pp.profile_id = ? AND pl.faction_key IS NOT NULL '
            'GROUP BY pl.faction_key', (profile,)):
        counted[key.casefold()] = count
    return counted


def build(game, world, profile, reference_data, encoding='cp1252'):
    owned = owners(world, profile)
    records = []
    for key, payload in game.execute(
            'SELECT rv.record_key, rv.payload FROM resolved_records rr '
            'JOIN record_versions rv ON rv.id = rr.winner_id '
            "WHERE rr.profile_id = ? AND rv.record_type = 'FACT' "
            'ORDER BY rv.record_key', (profile,)):
        parsed = parse(payload, encoding, reference_data)
        records.append({'key': key, **parsed, 'ownedPlacements': owned.get(key.casefold(), 0)})
    missing = sorted(set(owned) - {r['key'].casefold() for r in records})
    return records, missing


def assemble(game, world, profile, reference_data, snapshot):
    records, missing = build(game, world, profile, reference_data)
    if missing:
        raise ExportError(
            f'{len(missing)} faction(s) own placements but have no FACT record in '
            f'{profile}: ' + ', '.join(missing[:5])
            + '\n  The world and the foundation disagree; rebuild both.')
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'derivation': {
            'method': 'FACT records, with rank requirements read from the FADT subrecord',
            'factions': len(records),
            'hidden': sum(1 for r in records if r['hidden']),
            'joinable': sum(1 for r in records if r['rankCount']),
            'owningPlacements': sum(1 for r in records if r['ownedPlacements']),
            'reactions': sum(len(r['reactions']) for r in records)},
        'coverage': 'Every faction, the ranks it has, and the attribute, skill and '
                    'reputation each rank asks for. A faction with no named ranks is not '
                    'joinable -- the record still reserves ten slots, and the unnamed ones '
                    'are padding rather than ranks. Nothing here knows your standing, who '
                    'can admit you, or which quests a rank gates: those live in dialogue '
                    'and scripts, which this layer does not evaluate.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.factions-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--catalogs', type=Path)
    parser.add_argument('--foundation-database', type=Path)
    parser.add_argument('--world-database', type=Path)
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        catalogs = args.catalogs
        if catalogs is None:
            pointer = root/'catalogs/current.json'
            if not pointer.is_file():
                raise ExportError('No catalog release found; pass --catalogs')
            catalogs = root/'catalogs'/json.loads(pointer.read_text(encoding='utf-8'))['releaseId']
        paths = (args.foundation_database or root/'game-data.sqlite',
                 args.world_database or root/'world/world.sqlite')
        written = []
        with closing(sqlite3.connect(paths[0].resolve().as_uri()+'?mode=ro', uri=True)) as game, \
             closing(sqlite3.connect(paths[1].resolve().as_uri()+'?mode=ro', uri=True)) as world:
            for db in (game, world):
                db.execute('PRAGMA temp_store=MEMORY')
            snapshot = metadata(world).get('snapshotId')
            for profile in profiles:
                payload = assemble(game, world, profile,
                                   reference(catalogs, profile), snapshot)
                destination, size = publish(payload, args.output or root/'factions', profile)
                counts = payload['derivation']
                print(f'{profile}: {counts["factions"]} factions, {counts["joinable"]} joinable, '
                      f'{counts["hidden"]} hidden, {counts["owningPlacements"]} own placements, '
                      f'{counts["reactions"]} reactions, {size/1024:.0f} KB', flush=True)
                written.append(destination)
        print('Faction catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error, struct.error) as exc:
        print(f'Faction catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
