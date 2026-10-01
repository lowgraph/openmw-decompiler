"""Where each ingredient comes from, per profile: shops, plants, creatures and finds.

CALC-4's effect finder picks ingredients by what they do; this says where to get them.
Per ingredient, the acquisition index gives everything that holds it, directly or through
levelled lists, and the world gives where each holder is placed. Each placement becomes
at most one kind of source:

- **shops**: a merchant who trades ingredients and keeps it in their own inventory, or in
  a container they own where they trade (trade_spot). Levelled shop stock counts only if
  it restocks, as for gear.
- **plants**: organic containers that grow back, the flora a player harvests, with the
  chance per harvest from their levelled list; counted by region, around the starting
  towns, and in the interiors that hold most (cave mushrooms). Ore deposits and food
  barrels are organic too, but never refill.
- **creatures**: creatures that carry it, with the chance per kill, placed directly or as
  a levelled spawn point, and where.
- **finds**: the ingredient lying loose, or in an unowned container that is not a plant,
  put there directly or by a list that can give nothing else (an ore deposit, a kwama egg
  sack); grouped by what holds it, one-offs unless the container refills.

Theft is left out (owner, 30 September): anything owned by someone other than a merchant
selling it where they stand, and anything only an NPC carries, is not a source. Random
loot (a levelled list in a container that is not a plant) is not a source either, as for
gear. Nothing here runs scripts, judges danger or prices anything; quest rewards are not
sources. Run after the acquisition index, the services catalog and the places catalog:

    python build_ingredient_sources.py
    python build_app_bundle.py
"""
from __future__ import annotations

import argparse
from collections import Counter, namedtuple
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from build_acquisition_index import metadata
from evaluate_policy import cell_label, load_policy, sells, trade_spot
from export_items import ExportError
from extract_foundation import ROOT, label_carries, load_config
from inspect_acquisition_index import query_item

VERSION = '1.0.0'
# draw_chance is transcribed from getLevelledItem (apps/openmw/mwmechanics/levelledlist.cpp)
# and the list flags from components/esm3/loadlevlist.hpp, checked against this tag.
TRANSCRIBED_FROM = '0.51.0'
# ESM::ItemLevList::AllLevels and ESM::CreatureLevList::AllLevels: the same meaning on
# different bits, as OpenMW's getLevelledItem notes ("the flags are swapped").
ALL_LEVELS = {'LEVI': 0x02, 'LEVC': 0x01}
# Chances are given for a level 1 character, where nearly every ingredient list starts;
# a list that gives nothing at level 1 is described at the first level it does.
REFERENCE_LEVEL = 1
# How many of each a record keeps, nearest first; counts always cover all of them.
TOP = {'shops': 16, 'creatures': 12, 'regions': 8, 'cells': 6}
# One ingredient's whole graph, plants and all: generous, and any cut is reported.
QUERY_LIMITS = {'max_nodes': 20000, 'max_edges': 100000, 'max_depth': 24, 'max_placements': 500000}


def draw_chance(lists, list_key, item_key, level, seen=frozenset()):
    """The chance one draw from a levelled list gives item_key, as OpenMW draws it
    (apps/openmw/mwmechanics/levelledlist.hpp): chance-none first, then one entry
    uniformly from those at or below the level -- all of them with the all-levels flag,
    otherwise only those at the highest such level. A nested list draws again."""
    row = lists(list_key)
    if row is None or list_key in seen:
        return 0.0
    kind, none, flags, entries = row
    eligible = [(key, minimum) for key, minimum in entries if minimum <= level]
    if not eligible:
        return 0.0
    if not flags & ALL_LEVELS.get(kind, 0):
        top = max(minimum for _, minimum in eligible)
        eligible = [(key, minimum) for key, minimum in eligible if minimum == top]
    hits = sum(1.0 if key == item_key else draw_chance(lists, key, item_key, level, seen | {list_key})
               for key, _ in eligible)
    return max(0.0, 1 - none/100) * hits / len(eligible)


def list_levels(lists, list_key, seen=frozenset()):
    """Every entry level in a list and the lists under it: where its draws can change."""
    row = lists(list_key)
    if row is None or list_key in seen:
        return set()
    levels = {minimum for _, minimum in row[3]}
    for key, _ in row[3]:
        levels |= list_levels(lists, key, seen | {list_key})
    return levels


def first_chance(lists, list_key, item_key):
    """(chance, level): at the reference level, or at the first level the list gives it."""
    for level in sorted({REFERENCE_LEVEL} | {v for v in list_levels(lists, list_key) if v > REFERENCE_LEVEL}):
        chance = draw_chance(lists, list_key, item_key, level)
        if chance > 0:
            return chance, level
    return 0.0, None


class Places:
    """Cells, regions and the starting towns, read once per profile."""

    def __init__(self, world, profile, near_places):
        self.world, self.profile, self.cache = world, profile, {}
        self.cells = {key: (name, bool(interior), x, y, region) for key, name, interior, x, y, region in world.execute(
            'SELECT cell_key, name, interior, grid_x, grid_y, region_key FROM cells WHERE profile_id=? AND deleted=0',
            (profile,))}
        self.places = sorted({p.casefold() for p in near_places}, key=len, reverse=True)
        # A town is the exterior cells whose name carries the place; around it is the
        # squares next to them. The longest place wins, so Old Ebonheart is not Ebonheart.
        self.display, around = {}, {}
        for key, (name, interior, x, y, _) in self.cells.items():
            place = self.match(name)
            if place and not interior and x is not None:
                self.display[place] = min(self.display.get(place, name), name, key=len)
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        around.setdefault((x+dx, y+dy), place)
        self.around = around
        for place in self.places:   # Samarys is a tomb: no exterior to take a name from.
            self.display.setdefault(place, ' '.join(w[:1].upper()+w[1:] for w in place.split()))

    def match(self, text):
        text = (text or '').casefold()
        return next((p for p in self.places if p in text), None)

    def near(self, cell_key):
        """The starting town a cell is in or next to, by display name, or None."""
        name, interior, x, y, _ = self.cells.get(cell_key, (None, True, None, None, None))
        place = self.match(cell_label(self.world, self.profile, cell_key, self.cache))
        if place is None and not interior and x is not None:
            place = self.around.get((x, y))
        return self.display.get(place) if place else None

    def region(self, cell_key):
        name, interior, x, y, region = self.cells.get(cell_key, (None, True, None, None, None))
        return None if interior else (region or 'wilderness')

    def interior(self, cell_key):
        return self.cells.get(cell_key, (None, True))[1] or cell_key.startswith('interior:')


class Spread:
    """Where placements of one source fall: by region, around towns, and interiors."""

    def __init__(self):
        self.count, self.regions, self.near, self.cells = 0, Counter(), Counter(), Counter()

    def add(self, places, cell_key, count=1):
        self.count += count
        town = places.near(cell_key)
        if town:
            self.near[town] += count
        if places.interior(cell_key):
            self.cells[cell_key] += count
        else:
            self.regions[places.region(cell_key)] += count

    def publish(self):
        out = {'count': self.count}
        if self.regions:
            out['regions'] = [[k, n] for k, n in self.regions.most_common(TOP['regions'])]
        if self.near:
            out['near'] = [[k, n] for k, n in self.near.most_common()]
        if self.cells:
            out['cells'] = [[k, n] for k, n in self.cells.most_common(TOP['cells'])]
        return out


def outcomes(lists, list_key, seen=frozenset()):
    """Everything a levelled list can ever give, through nested lists."""
    row = lists(list_key)
    if row is None or list_key in seen:
        return {list_key}
    found = set()
    for key, _ in row[3]:
        found |= outcomes(lists, key, seen | {list_key}) if lists(key) else {key}
    return found


Draw = namedtuple('Draw', 'chance level quantity restocks only')


def holder_yield(graph, lists, holder, root):
    """What one holder gives: the quantity it keeps directly, whether that restocks, and
    one Draw per levelled entry, best first. `only` marks a list that can give nothing but
    this ingredient (a deposit, a plant), as opposed to random loot."""
    direct, restocks, listed = 0, False, []
    for edge in graph['down'].get(holder['versionId'], ()):
        if edge['kind'] != 'inventory':
            continue
        extra = edge['details'] or {}
        quantity = extra.get('quantity') or abs(extra.get('countRaw') or 0) or 1
        target = graph['nodes'][edge['targetVersionId']]
        if target['versionId'] == root['versionId']:
            direct += quantity
            restocks = restocks or bool(extra.get('restocking'))
        elif target['recordType'] in ALL_LEVELS:
            chance, level = first_chance(lists, target['key'], root['key'])
            if chance > 0:
                listed.append(Draw(chance, level, quantity, bool(extra.get('restocking')),
                                   outcomes(lists, target['key']) == {root['key']}))
    return direct, restocks, sorted(listed, reverse=True)


def best_draw(direct, listed):
    """A holder's draw as one figure: its own stock if any, else its best list."""
    if direct:
        return Draw(1.0, None, direct, False, True)
    return listed[0] if listed else None


def spawned_creatures(graph, spawn):
    """The creatures holding the ingredient that a placed levelled creature list can
    spawn, through nested lists."""
    found, stack, seen = [], [spawn['versionId']], set()
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        for edge in graph['down'].get(current, ()):
            if edge['kind'] != 'leveled':
                continue
            node = graph['nodes'][edge['targetVersionId']]
            if node['recordType'] == 'LEVC':
                stack.append(node['versionId'])
            elif node['recordType'] == 'CREA':
                found.append(node)
    return found


def drawn(entry, draw):
    """The chance, quantity and starting level of a draw, as a record carries them."""
    entry |= {'chance': round(draw.chance, 4), 'quantity': draw.quantity}
    if draw.level and draw.level > REFERENCE_LEVEL:
        entry['fromLevel'] = draw.level
    return entry


def classify(static, world, services, profile, policy, places, lists, actors, cache):
    """One ingredient's record from its evidence graph, and what was left out."""
    early = policy['earlyGame']
    excluded_cells = {key.casefold() for key in early['excludedCells']}
    holding = tuple(prefix.casefold() for prefix in early.get('holdingCellPrefixes', []))
    nodes = {node['versionId']: node for node in static['nodes']}
    down = {}
    for edge in static['edges']:
        down.setdefault(edge['parentVersionId'], []).append(edge)
    graph = {'nodes': nodes, 'down': down}
    root = nodes[static['rootVersionId']]
    shops, plants, creatures, finds, skipped, yields = {}, {}, {}, {}, Counter(), {}

    def yield_of(node):
        if node['versionId'] not in yields:
            yields[node['versionId']] = holder_yield(graph, lists, node, root)
        return yields[node['versionId']]

    def trades(actor_key):
        if not actor_key:
            return False
        if ('trades', profile, actor_key) not in cache:
            cache['trades', profile, actor_key] = bool(sells(services, profile, actor_key, 'INGR', False))
        return cache['trades', profile, actor_key]

    def add_shop(seller, name, cell_key, direct, restocks, listed):
        # Levelled shop stock counts only if it restocks, as for gear.
        stocked = direct + sum(d.quantity for d in listed if d.restocks)
        if not stocked:
            skipped['random'] += 1
            return
        entry = shops.setdefault((seller, cell_key), {'seller': seller, 'name': name, 'cellKey': cell_key,
                                                      'quantity': 0, 'restocks': False})
        entry['quantity'] += stocked
        entry['restocks'] = entry['restocks'] or restocks or any(d.restocks for d in listed)

    def add_creature(node, cell_key, spawn):
        direct, _, listed = yield_of(node)
        draw = best_draw(direct, listed)
        if draw is None:
            return
        actor = actors(node['key'])
        entry = creatures.get(node['key'])
        if entry is None:
            entry = creatures[node['key']] = drawn({'creature': node['key'], 'name': node['name'],
                                                    'level': actor[0] if actor else None}, draw)
            entry.update(placed=0, spawnPoints=0, spread=Spread())
        entry['spawnPoints' if spawn else 'placed'] += 1
        entry['spread'].add(places, cell_key)

    def add_find(name, draw, refills, cell_key, locked):
        key = (name, round(draw.chance, 4), draw.level, draw.quantity, refills)
        entry = finds.setdefault(key, {'spread': Spread(), 'locked': 0})
        entry['spread'].add(places, cell_key)
        entry['locked'] += bool(locked)

    for placement in static['placements']:
        cell_key = placement['cellKey']
        folded = cell_key.casefold()
        if folded in excluded_cells or folded.startswith(holding):
            skipped['unreachableCell'] += 1
            continue
        node = nodes[placement['nodeVersionId']]
        kind = node['recordType']
        owner = placement.get('ownerKey')
        owned = bool(owner or placement.get('factionKey'))
        # Stock a merchant owns is sold where they stand, if they deal in ingredients.
        counter = trade_spot(world, profile, owner, cell_key, cache) if owner and trades(owner) else None
        locked = (placement.get('details') or {}).get('lockLevelRaw') or 0
        if node['versionId'] == root['versionId']:
            count = abs(placement.get('countRaw') or 0) or 1
            if counter:
                add_shop(owner, None, counter[0], count, False, [])
            elif owned:
                skipped['theft'] += 1
            else:
                add_find(None, Draw(1.0, None, count, False, True), False, cell_key, False)
        elif kind == 'CONT':
            direct, restocks, listed = yield_of(node)
            flags = node['details'] or {}
            if counter:
                add_shop(owner, None, counter[0], direct, restocks, listed)
            elif owned:
                skipped['theft'] += 1
            elif flags.get('organic') and flags.get('respawns'):
                # A plant: organic, and it grows back. Deposits and food barrels are
                # organic too, but never refill.
                draw = best_draw(direct, listed)
                if draw is None:
                    skipped['random'] += 1
                    continue
                entry = plants.setdefault((node['name'], round(draw.chance, 4), draw.level, draw.quantity),
                                          {'containers': set(), 'spread': Spread(), 'draw': draw})
                entry['containers'].add(node['key'])
                entry['spread'].add(places, cell_key)
            else:
                # Put there directly, or by a list that can give only this ingredient (a
                # deposit); a list of several things is random loot, left out as for gear.
                draw = best_draw(direct, [d for d in listed if d.only])
                if draw is None:
                    skipped['random'] += 1
                    continue
                add_find(node['name'], draw, bool(flags.get('respawns')), cell_key, locked)
        elif kind in ('NPC_', 'CREA'):
            direct, restocks, listed = yield_of(node)
            if trades(node['key']):
                add_shop(node['key'], node['name'], cell_key, direct, restocks, listed)
            elif kind == 'CREA':
                add_creature(node, cell_key, spawn=False)
            else:
                skipped['carried'] += 1   # Only by pickpocketing or killing them.
        elif kind == 'LEVC':
            spawned = [c for c in spawned_creatures(graph, node) if not trades(c['key'])]
            for creature in spawned:
                add_creature(creature, cell_key, spawn=True)
            if not spawned:
                skipped['carried'] += 1   # A levelled NPC, not a creature.
        else:
            skipped['random'] += 1

    record = {'key': root['key'], 'name': root['name']}
    if shops:
        for entry in shops.values():
            entry['name'] = entry['name'] or actors(entry['seller'], name=True)
            near = places.near(entry['cellKey'])
            if near:
                entry['near'] = near
        ranked = sorted(shops.values(), key=lambda s: (s.get('near') is None, not s['restocks'],
                                                       -s['quantity'], s['name'] or '', s['cellKey']))
        record['shops'] = ranked[:TOP['shops']]
        if len(ranked) > TOP['shops']:
            record['shopCount'] = len(ranked)
    if plants:
        out = [drawn({'name': name, 'containers': sorted(entry['containers'])}, entry['draw'])
               | {'regrows': True} | entry['spread'].publish()
               for (name, *_), entry in plants.items()]
        record['plants'] = sorted(out, key=lambda p: (-sum(n for _, n in p.get('near', [])), -p['count'], p['name']))
    if creatures:
        out = []
        for entry in creatures.values():
            spread = entry.pop('spread').publish()
            spread.pop('count')
            out.append(entry | spread)
        ranked = sorted(out, key=lambda c: (-sum(n for _, n in c.get('near', [])),
                                            -(c['placed'] + c['spawnPoints']), c['name']))
        record['creatures'] = ranked[:TOP['creatures']]
        if len(ranked) > TOP['creatures']:
            record['creatureCount'] = len(ranked)
    if finds:
        out = []
        for (name, chance, level, quantity, refills), entry in finds.items():
            find = drawn({'name': name} if name else {'loose': True}, Draw(chance, level, quantity, False, True))
            if refills:
                find['refills'] = True
            if entry['locked']:
                find['locked'] = entry['locked']
            out.append(find | entry['spread'].publish())
        record['finds'] = sorted(out, key=lambda f: (-sum(n for _, n in f.get('near', [])), -f['count']))
    if static['truncated']:
        record['truncated'] = static['limitReasons']
    return record, skipped


def readers(world, profile):
    """Levelled lists and actors from the world, cached: the two lookups every graph needs."""
    lists_cache, actor_cache = {}, {}

    def lists(key):
        if key not in lists_cache:
            row = world.execute('''SELECT o.record_type, l.version_id, l.chance_none, l.flags_raw
                FROM profile_objects p JOIN objects o ON o.version_id=p.version_id
                JOIN leveled_lists l ON l.version_id=p.version_id
                WHERE p.profile_id=? AND p.object_key=?''', (profile, key)).fetchone()
            lists_cache[key] = None if row is None else (
                row[0], row[2], row[3],
                [(k, lv) for k, lv in world.execute(
                    'SELECT object_key, minimum_level FROM leveled_entries WHERE list_version_id=? ORDER BY entry_index',
                    (row[1],))])
        return lists_cache[key]

    def actors(key, name=False):
        if key not in actor_cache:
            row = world.execute('''SELECT o.name, a.level, a.respawns FROM profile_objects p
                JOIN objects o ON o.version_id=p.version_id LEFT JOIN actors a ON a.version_id=p.version_id
                WHERE p.profile_id=? AND p.object_key=?''', (profile, key)).fetchone()
            actor_cache[key] = row
        row = actor_cache[key]
        if name:
            return row[0] if row and row[0] else None
        return None if row is None or row[1] is None else (row[1], bool(row[2]))

    return lists, actors


def check_transcription(world):
    """Refuse to compute chances with a levelled-list draw copied from another release."""
    labelled = dict(world.execute('SELECT world, version FROM profiles')).get('vanilla', '')
    if not label_carries(labelled, TRANSCRIBED_FROM):
        raise ExportError(
            f'The levelled-list draw was transcribed from OpenMW {TRANSCRIBED_FROM}, but this '
            f'extraction is for {labelled!r}.\n  Compare getLevelledItem (apps/openmw/mwmechanics/'
            'levelledlist.cpp) and the list flags (components/esm3/loadlevlist.hpp) between the '
            'two releases. If they are unchanged, set TRANSCRIBED_FROM in '
            'build_ingredient_sources.py to the new version; if not, transcribe them again.')


def ingredients(acquisition, profile):
    return acquisition.execute('''SELECT n.object_key, n.name FROM profile_nodes p
        JOIN nodes n ON n.version_id=p.version_id
        WHERE p.profile_id=? AND p.record_type='INGR' ORDER BY n.object_key''', (profile,)).fetchall()


def build(world, acquisition, services, profile, policy, limit=None, only=None):
    places = Places(world, profile, policy['earlyGame']['nearStart']['places'])
    lists, actors = readers(world, profile)
    cache, records, skipped = {}, [], Counter()
    wanted = ingredients(acquisition, profile)
    if only:
        wanted = [row for row in wanted if row[0] in only]
    if limit:
        wanted = wanted[:limit]
    for index, (key, _) in enumerate(wanted, 1):
        static = query_item(acquisition, world, profile, key, 'INGR', **QUERY_LIMITS)
        record, left_out = classify(static, world, services, profile, policy, places, lists, actors, cache)
        records.append(record)
        skipped.update(left_out)
        if index % 100 == 0:
            print(f'  {profile}: {index:,}/{len(wanted):,}', flush=True)
    return records, skipped


def assemble(records, skipped, profile, snapshot, policy):
    has = lambda kind: sum(1 for r in records if r.get(kind))
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'policyVersion': policy['policyVersion'],
        'derivation': {
            'ingredients': len(records), 'withShop': has('shops'), 'withPlant': has('plants'),
            'withCreature': has('creatures'), 'withFind': has('finds'),
            'withoutSource': sum(1 for r in records if not any(r.get(k) for k in ('shops', 'plants', 'creatures', 'finds'))),
            'truncated': has('truncated'), 'referenceLevel': REFERENCE_LEVEL,
            'transcribedFrom': f'OpenMW {TRANSCRIBED_FROM}',
            'leftOut': dict(sorted(skipped.items()))},
        'coverage': 'Static evidence: what holds each ingredient and where the holders are placed. '
                    'Shops trade ingredients and keep it in their own inventory or a container '
                    'they own where they trade; levelled shop stock counts only if it restocks. '
                    'Plants are organic containers that grow back, with the chance per harvest for '
                    'a level 1 character (fromLevel when a list starts later). Creatures carry it, '
                    'placed or as levelled spawn points, whose own draw depends on level and is not '
                    'computed. Finds are loose, or in an unowned container that is not a plant, put '
                    'there directly or by a list that gives nothing else (deposits). Left out: '
                    'anything owned by someone else (theft), anything only an '
                    'NPC carries, random loot, holding and test cells, scripts and quest rewards. '
                    'Danger, locks beyond a count, and prices are not judged.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    destination = output/f'{profile}-{hashlib.sha256(body).hexdigest()[:24]}.json'
    handle, staging = tempfile.mkstemp(prefix='.ingredient-sources-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--world-database', type=Path)
    parser.add_argument('--acquisition-database', type=Path)
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--policy', type=Path, default=ROOT/'policy'/'early-game.json')
    parser.add_argument('--limit', type=int, help='Only the first N ingredients, for a quick look')
    parser.add_argument('--item', action='append', help='Print one ingredient\'s record and publish nothing')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        policy = load_policy(args.policy)
        paths = (args.world_database or root/'world/world.sqlite',
                 args.acquisition_database or root/'acquisition/acquisition.sqlite',
                 args.services_database or root/'services/services.sqlite')
        written = []
        with ExitStack() as stack:
            world, acquisition, services = [stack.enter_context(closing(
                sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True))) for path in paths]
            check_transcription(world)
            snapshot = metadata(acquisition)['snapshotId']
            if metadata(services).get('snapshotId') != snapshot:
                raise ExportError('The services catalog and the acquisition index come from different '
                                  'extractions; rebuild the older one first')
            for profile in profiles:
                records, skipped = build(world, acquisition, services, profile, policy, args.limit,
                                         {i.casefold() for i in args.item} if args.item else None)
                if args.item:
                    print(json.dumps(records, ensure_ascii=False, indent=2))
                    continue
                payload = assemble(records, skipped, profile, snapshot, policy)
                destination, size = publish(payload, args.output or root/'ingredient-sources', profile)
                d = payload['derivation']
                print(f'{profile}: {d["ingredients"]} ingredients; shop {d["withShop"]}, plant {d["withPlant"]}, '
                      f'creature {d["withCreature"]}, find {d["withFind"]}, none {d["withoutSource"]}; '
                      f'{size/1024:.0f} KB', flush=True)
                written.append(destination)
        if written:
            print('Ingredient sources complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Ingredient sources build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
