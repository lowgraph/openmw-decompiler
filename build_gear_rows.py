"""Build one gear row per slot per toggle combination, from policy verdicts.

A row answers "what should a level 1 character wear here", for one equipment slot
under one set of the site's three toggles. Rows are derived, never authored: the
candidates come from the catalogs, the verdicts from the policy layer, and nothing
here decides what is obtainable.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from build_acquisition_index import metadata
from evaluate_policy import assess, load_policy, load_category, resolve_limits
from export_items import ExportError
from extract_foundation import ROOT, load_config
from inspect_acquisition_index import query_item

VERSION = '1.0.0'
# Bracers share the gauntlet threshold; OpenMW's Armor::getEquipmentSkill does the same.
ARMOR_WEIGHT_GMST = {
    'helmet': 'ihelmweight', 'cuirass': 'icuirassweight', 'greaves': 'igreavesweight',
    'boots': 'ibootsweight', 'shield': 'ishieldweight',
    'left_pauldron': 'ipauldronweight', 'right_pauldron': 'ipauldronweight',
    'left_gauntlet': 'igauntletweight', 'right_gauntlet': 'igauntletweight',
    'left_bracer': 'igauntletweight', 'right_bracer': 'igauntletweight'}
ARMOR_SLOTS = [s for s in ARMOR_WEIGHT_GMST if s != 'shield']
ARMOR_CLASSES = ['light', 'medium', 'heavy']
# Arrows and bolts are ammunition, not an equipment slot, so they get no row.
WEAPON_ROWS = {'SB1H': ('short_blade', 1), 'LB1H': ('long_blade', 1), 'LB2H': ('long_blade', 2),
               'BL1H': ('blunt', 1), 'BL2C': ('blunt', 2), 'BL2W': ('blunt', 2),
               'AX1H': ('axe', 1), 'AX2H': ('axe', 2), 'SP2H': ('spear', 2),
               'BOW': ('marksman', 2), 'CROSSBOW': ('marksman', 2), 'THROWN': ('marksman', 1)}
CLOTHING_SLOTS = ['shirt', 'pants', 'shoes', 'belt', 'robe', 'skirt',
                  'ring', 'amulet', 'left_glove', 'right_glove']
CATEGORIES = ('armor', 'shield', 'weapon', 'clothing')


def toggle_sets():
    return [{'theft': t, 'endgame': e, 'nearStart': n}
            for t in (False, True) for e in (False, True) for n in (False, True)]


def variant(policy, toggles):
    policy = copy.deepcopy(policy)
    policy['earlyGame']['allowTheft'] = toggles['theft']
    policy['earlyGame']['allowEndgameEarly'] = toggles['endgame']
    policy['earlyGame']['nearStart']['required'] = toggles['nearStart']
    return policy


def armor_class(record, settings):
    """Weight against the slot's threshold, exactly as the engine classifies it."""
    base = settings.get(ARMOR_WEIGHT_GMST[record['type']])
    if base is None:
        raise ExportError(f'Missing armour weight setting for {record["type"]}')
    weight = record['weight']
    if base*settings['flightmaxmod'] >= weight:
        return 'light'
    return 'medium' if base*settings['fmedmaxmod'] >= weight else 'heavy'


def strength(record):
    """The number a row ranks on: protection, damage, or enchantment capacity."""
    if record['recordType'] == 'ARMO':
        return record['armorRating']
    if record['recordType'] == 'WEAP':
        return max(record[k]['max'] for k in ('chop', 'slash', 'thrust'))
    return record.get('enchantp') or 0


def row_key(record, settings):
    if record['recordType'] == 'ARMO':
        if record['type'] == 'shield':
            return ('shield', None, None, None)
        if record['type'] not in ARMOR_WEIGHT_GMST:
            return None
        return ('armor', record['type'], armor_class(record, settings), None)
    if record['recordType'] == 'WEAP':
        if record['type'] not in WEAPON_ROWS:
            return None
        skill, hands = WEAPON_ROWS[record['type']]
        return ('weapon', None, None, (skill, hands))
    return ('clothing', record['type'], None, None) if record['type'] in CLOTHING_SLOTS else None


def pick(record, verdict, route):
    return {'key': record['key'], 'name': record['name'], 'strength': strength(record),
            'baseValue': record['value'], 'endgame': verdict['endgame'],
            'acquisition': route['acquisition'], 'price': route['price'], 'value': route['value'],
            'cellKey': route['cellKey'], 'nearStart': route['nearStart'],
            'needsRepair': route['needsRepair'], 'condition': route['condition'],
            'holder': route['holder']['name'], 'theftRequired': route['theftRequired'],
            'evidenceTruncated': verdict['evidenceTruncated']}


def best(candidates):
    # Strongest first; among equals the one that costs least.
    return max(candidates, key=lambda c: (c['strength'], -(c['price'] or 0)), default=None)


def build(world, acquisition, services, catalogs, profile, policy, categories, limits,
          max_placements, max_nodes, max_edges, max_depth, limit=None):
    settings = {r['key']: r['value'] for r in _settings(catalogs, profile)}
    wanted = {'ARMO': 'armor', 'WEAP': 'weapon', 'CLOT': 'clothing'}
    variants = [(toggles, variant(policy, toggles)) for toggles in toggle_sets()]
    buckets = {}
    cache = {}
    for record_type, label in wanted.items():
        if label not in categories and not (label == 'armor' and 'shield' in categories):
            continue
        records = list(load_category(catalogs, profile, record_type).values())
        if limit:
            records = records[:limit]
        print(f'{profile}: {label} candidates: {len(records):,}', flush=True)
        for index, record in enumerate(records, 1):
            key = row_key(record, settings)
            if key is None or key[0] not in categories:
                continue
            try:
                static = query_item(acquisition, world, profile, record['key'], record['recordType'],
                                    max_nodes, max_edges, max_depth, max_placements)
            except ExportError:
                continue  # Not present in this profile's acquisition graph.
            for toggles, rules in variants:
                verdict = assess(world, services, catalogs, profile, static, {'events': []},
                                 rules, limits, static['truncated'], cache)
                chosen = verdict['recommended']
                if chosen is None:
                    continue
                bucket = buckets.setdefault(key, {}).setdefault(
                    (toggles['theft'], toggles['endgame'], toggles['nearStart']), [])
                bucket.append(pick(record, verdict, verdict['routes'][chosen]))
            if index % 200 == 0:
                print(f'  {index:,}/{len(records):,}', flush=True)
    return assemble(buckets, categories)


def assemble(buckets, categories):
    rows = []
    definitions = []
    if 'armor' in categories:
        definitions += [('armor', slot, armour, None) for slot in ARMOR_SLOTS for armour in ARMOR_CLASSES]
    if 'shield' in categories:
        definitions += [('shield', None, None, None)]
    if 'weapon' in categories:
        definitions += [('weapon', None, None, pair) for pair in sorted(set(WEAPON_ROWS.values()))]
    if 'clothing' in categories:
        definitions += [('clothing', slot, None, None) for slot in CLOTHING_SLOTS]
    for key in definitions:
        category, slot, armour, weapon = key
        for toggles in toggle_sets():
            candidates = buckets.get(key, {}).get(
                (toggles['theft'], toggles['endgame'], toggles['nearStart']), [])
            near = [c for c in candidates if c['nearStart']]
            far = [c for c in candidates if not c['nearStart']]
            primary = best(near) or best(far)
            strongest = best(far)
            # An "or" row only earns its place when it beats the close pick.
            alternative = (strongest if primary and strongest and primary['nearStart']
                           and strongest['strength'] > primary['strength'] else None)
            rows.append({'category': category, 'slot': slot, 'armorClass': armour,
                         'skill': weapon[0] if weapon else None,
                         'hands': weapon[1] if weapon else None,
                         'toggles': toggles, 'eligible': len(candidates),
                         'nearStart': len(near), 'primary': primary, 'alternative': alternative})
    return rows


def _settings(catalogs, profile):
    path = Path(catalogs)/profile/'GameSettings.json'
    if not path.is_file():
        raise ExportError(f'GameSettings catalog missing: {path}')
    return json.loads(path.read_text(encoding='utf-8'))['records']


def publish(rows, output, profile, policy, limits, snapshot, categories):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    payload = {'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
               'policy': {'version': policy['policyVersion'], 'schemaVersion': policy['schemaVersion'],
                          'name': policy.get('name')},
               'limits': limits, 'categories': sorted(categories),
               'coverage': 'Rows are derived from policy verdicts over static evidence. Script '
                           'grants are not consulted; a quest reward is never an eligible row.',
               'builtAtUnix': time.time(), 'rows': rows}
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.rows-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='vanilla', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--catalogs', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--category', action='append', choices=list(CATEGORIES))
    parser.add_argument('--limit', type=int, help='Only the first N records per category, for a smoke run')
    parser.add_argument('--max-placements', type=int, default=1500)
    parser.add_argument('--max-nodes', type=int, default=2000)
    parser.add_argument('--max-edges', type=int, default=5000)
    parser.add_argument('--max-depth', type=int, default=12)
    for name, database in (('world-database', 'world/world.sqlite'),
                           ('acquisition-database', 'acquisition/acquisition.sqlite'),
                           ('services-database', 'services/services.sqlite')):
        parser.add_argument('--'+name, type=Path)
    args = parser.parse_args(argv)
    categories = set(args.category or CATEGORIES)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        policy = load_policy(args.policy or ROOT/'policy/early-game.json')
        catalogs = args.catalogs
        if catalogs is None:
            pointer = root/'catalogs/current.json'
            if not pointer.is_file():
                raise ExportError('No catalog release found; pass --catalogs')
            catalogs = root/'catalogs'/json.loads(pointer.read_text(encoding='utf-8'))['releaseId']
        paths = (args.world_database or root/'world/world.sqlite',
                 args.acquisition_database or root/'acquisition/acquisition.sqlite',
                 args.services_database or root/'services/services.sqlite')
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                db.execute('PRAGMA cache_size=-32768')
                db.execute('BEGIN')
                dbs.append(db)
            world, acquisition, services = dbs
            snapshot = metadata(world).get('snapshotId')
            limits = resolve_limits(world, policy)
            started = time.time()
            rows = build(world, acquisition, services, catalogs, args.profile, policy, categories,
                         limits, args.max_placements, args.max_nodes, args.max_edges,
                         args.max_depth, args.limit)
            destination, size = publish(rows, args.output or root/'gear-rows', args.profile,
                                        policy, limits, snapshot, categories)
        filled = sum(1 for r in rows if r['primary'])
        print(f'Gear rows complete: {destination}\n'
              f'{len(rows)} rows, {filled} filled, {len(rows)-filled} empty, '
              f'{size/1024:.0f} KB, {time.time()-started:.0f}s', flush=True)
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; no rows were published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Gear row build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
