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
from evaluate_policy import (assess, check_near_start, load_policy, load_category,
                             profile_cells, resolve_limits)
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
# ESM::PRT_Head, PRT_RFoot, PRT_LFoot, from components/esm3/loadarmo.hpp.
BEAST_FORBIDDEN_PARTS = frozenset({0, 15, 16})
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
    """What the piece is for: protection, damage, or capacity when it has neither."""
    if record['recordType'] == 'ARMO':
        return record['armorRating']
    if record['recordType'] == 'WEAP':
        return max(record[k]['max'] for k in ('chop', 'slash', 'thrust'))
    return record.get('enchantp') or 0


def enchantment(record):
    """Enchantment capacity, which decides what a constant effect can cost."""
    return record.get('enchantp') or 0


# What each objective ranks on. A row is answered once per objective, and the two
# disagree often: Eleidon's Ward carries 30,000 points at 100 armour, while the best
# cuirass in the game has 100 armour at 1,500.
OBJECTIVES = {'power': 'strength', 'enchantment': 'enchantment'}


def row_key(record, settings):
    if record['recordType'] == 'ARMO':
        if record['type'] not in ARMOR_WEIGHT_GMST:
            return None
        # Shields are their own category but still split light/medium/heavy.
        category = 'shield' if record['type'] == 'shield' else 'armor'
        slot = None if category == 'shield' else record['type']
        return (category, slot, armor_class(record, settings), None)
    if record['recordType'] == 'WEAP':
        if record['type'] not in WEAPON_ROWS:
            return None
        skill, hands = WEAPON_ROWS[record['type']]
        return ('weapon', None, None, (skill, hands))
    return ('clothing', record['type'], None, None) if record['type'] in CLOTHING_SLOTS else None


def beast_wearable(record):
    """Whether an Argonian or Khajiit can equip this at all.

    MWClass::Armor::canBeEquipped and its Clothing twin refuse any item whose body part
    list touches the head or either foot, with the engine's own comment: "Beast races
    cannot equip shoes / boots, or full helms (head part vs hair part)". An open helm
    dresses PRT_Hair instead of PRT_Head, which is why some helmets are fine and most
    are not. The rule is per item, not per slot: one Tamriel Rebuilt shoe passes it.
    """
    for part in record.get('bodyParts') or ():
        if part.get('slot') in BEAST_FORBIDDEN_PARTS:
            return False
    return True


def pick(record, verdict, route):
    return {'key': record['key'], 'name': record['name'], 'strength': strength(record),
            'enchantment': enchantment(record),
            'beastWearable': beast_wearable(record),
            'baseValue': record['value'], 'endgame': verdict['endgame'],
            'acquisition': route['acquisition'], 'price': route['price'], 'value': route['value'],
            'cellKey': route['cellKey'], 'nearStart': route['nearStart'],
            'needsRepair': route['needsRepair'], 'condition': route['condition'],
            'holder': route['holder']['name'], 'theftRequired': route['theftRequired'],
            'evidenceTruncated': verdict['evidenceTruncated']}


def row_identity(category, slot, armour, weapon, toggles, objective):
    """Stable key for one row, across definitions, toggle sets and objectives."""
    part = slot or (f'{weapon[0]}-{weapon[1]}h' if weapon else '-')
    flags = f"{int(toggles['theft'])}{int(toggles['endgame'])}{int(toggles['nearStart'])}"
    return f"{category}/{part}/{armour or '-'}/{flags}/{objective}"


def best(candidates, field='strength'):
    # Best on the objective first; among equals the one that costs least.
    return max(candidates, key=lambda c: (c[field], -(c['price'] or 0)), default=None)


def objectives_from(policy):
    """The objectives the policy asks for, checked against the ones we can measure."""
    named = policy.get('objectives')
    if not named:
        return ['power']
    unknown = [o for o in named if o not in OBJECTIVES]
    if unknown:
        raise ExportError(
            'Policy names objective(s) the row builder cannot measure: '
            + ', '.join(sorted(unknown))
            + '\n  Known objectives: ' + ', '.join(sorted(OBJECTIVES)))
    return list(named)


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
    return assemble(buckets, categories, objectives_from(policy))


def assemble(buckets, categories, objectives=('power',)):
    rows = []
    definitions = []
    if 'armor' in categories:
        definitions += [('armor', slot, armour, None) for slot in ARMOR_SLOTS for armour in ARMOR_CLASSES]
    if 'shield' in categories:
        definitions += [('shield', None, armour, None) for armour in ARMOR_CLASSES]
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
            # The objectives cost nothing here: the candidates are already gathered and
            # the policy already evaluated, so answering a second question about the
            # same list is free. Only the choosing changes.
            for objective in objectives:
                field = OBJECTIVES[objective]
                primary = best(near, field) or best(far, field)
                strongest = best(far, field)
                # A beast race gets its own pick from the same candidates: an Argonian
                # in a boots row has nothing at all, and in a helmet row wants the best
                # open helm rather than the best helm.
                beast_near = [c for c in near if c['beastWearable']]
                beast_far = [c for c in far if c['beastWearable']]
                beast_primary = best(beast_near, field) or best(beast_far, field)
                # An "or" row only earns its place when it beats the close pick.
                alternative = (strongest if primary and strongest and primary['nearStart']
                               and strongest[field] > primary[field] else None)
                rows.append({'key': row_identity(category, slot, armour, weapon, toggles,
                                                 objective),
                             'category': category, 'slot': slot, 'armorClass': armour,
                             'skill': weapon[0] if weapon else None,
                             'hands': weapon[1] if weapon else None,
                             'toggles': toggles, 'objective': objective,
                             'eligible': len(candidates),
                             'nearStart': len(near), 'primary': primary,
                             'alternative': alternative,
                             'beastEligible': len(beast_near) + len(beast_far),
                             'beastPrimary': beast_primary})
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
               'objectives': [{'key': key, 'ranksOn': OBJECTIVES[key],
                               'note': (policy.get('objectiveNotes') or {}).get(key)}
                              for key in objectives_from(policy)],
               'coverage': 'Rows are derived from policy verdicts over static evidence. Script '
                           'grants are not consulted; a quest reward is never an eligible row. '
                           'beastPrimary is the same row for an Argonian or Khajiit, who cannot '
                           'equip anything covering the head or a foot: null there means nothing '
                           'in this slot fits them, which is every boots and almost every shoes '
                           'row, not that the row is empty.',
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
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'],
                        help='Repeat for several; every profile when omitted, like every '
                             'other step. Each takes about twenty minutes.')
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
    profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
    try:
        # The bundler takes the newest rows per profile, and a partial run does not merge
        # with the last full one, so published beside the real rows it would ship in
        # their place. A --limit smoke run once did exactly that.
        if (args.limit is not None or args.category) and args.output is None:
            raise ExportError('A partial run (--limit or --category) would become the newest '
                              'rows and be bundled in place of the full ones; pass --output '
                              'with a scratch folder, such as A:/Cache/RowsPreview')
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
            # The near-start places are authored substrings; check them against the real
            # cell keys before spending twenty minutes building rows around them.
            coverage = check_near_start(policy, profile_cells(services))
            snapshot = metadata(world).get('snapshotId')
            limits = resolve_limits(world, policy)
            for profile in profiles:
                inert = sorted(place for place, seen in coverage.items() if profile not in seen)
                if inert:
                    print(f'{profile}: near-start places that match nothing in this '
                          f'profile: {", ".join(inert)}', flush=True)
                started = time.time()
                rows = build(world, acquisition, services, catalogs, profile, policy,
                             categories, limits, args.max_placements, args.max_nodes,
                             args.max_edges, args.max_depth, args.limit)
                destination, size = publish(rows, args.output or root/'gear-rows', profile,
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
