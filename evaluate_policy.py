"""Turn extracted acquisition evidence into authored verdicts, with a trace.

This layer is authored policy, not extracted fact. It reads the evidence databases
read-only and never rebuilds them, so a rule change costs a re-evaluation, never a
re-extraction. Every verdict carries the reasons that produced it.
"""
from __future__ import annotations

import json
from pathlib import Path

from export_items import ExportError

VERSION = '1.0.0'
# Trade service bits a provider must hold to sell an item of that record type.
SERVICE_BITS = {'WEAP': 1, 'ARMO': 2, 'CLOT': 4, 'BOOK': 8, 'INGR': 16, 'LOCK': 32,
                'PROB': 64, 'LIGH': 128, 'APPA': 256, 'REPA': 512, 'MISC': 1024, 'ALCH': 8192}
MAGIC_ITEMS_BIT = 4096
# Route quality, best first. 'random' is absorbing: one leveled hop anywhere on a
# path makes the whole path a chance, however guaranteed the rest of it is.
DIRECT, INVENTORY, RESTOCKING, RANDOM = range(4)
QUALITY_NAMES = ['direct', 'inventory', 'restocking', 'random']
# Field holding full condition per category. A CellRef's condition/uses value is
# pro rata worth: a Glass Dagger at 2 of 300 is worth 27 gold, not 4000.
CONDITION_MAX = {'WEAP': 'health', 'ARMO': 'health', 'LOCK': 'uses', 'PROB': 'uses', 'REPA': 'uses'}
CATEGORY_FILES = {'WEAP': 'Weapons', 'ARMO': 'Armor', 'CLOT': 'Clothing', 'BOOK': 'Books',
                  'ALCH': 'Potions', 'INGR': 'Ingredients', 'APPA': 'Apparatus', 'LOCK': 'Lockpicks',
                  'PROB': 'Probes', 'REPA': 'RepairTools', 'LIGH': 'Lights', 'MISC': 'Miscellaneous'}


def load_policy(path):
    policy = json.loads(Path(path).read_text(encoding='utf-8'))
    if policy.get('schemaVersion') != VERSION:
        raise ExportError(f'Unsupported policy schema {policy.get("schemaVersion")!r}')
    early = policy.get('earlyGame')
    if not isinstance(early, dict):
        raise ExportError('Policy has no earlyGame section')
    for name, kind in [('characterLevel', int), ('maxGoldPerItem', (int, float)), ('allowTheft', bool),
                       ('assumeFactionAccess', bool), ('requireGuaranteedSource', bool),
                       ('countRestockingMerchantsAsGuaranteed', bool),
                       ('vendorOwnedPlacementsArePurchasable', bool),
                       ('allowBrokenItems', bool)]:
        if not isinstance(early.get(name), kind) or isinstance(early.get(name), bool) != (kind is bool):
            raise ExportError(f'Policy earlyGame.{name} is missing or the wrong type')
    if early['characterLevel'] < 1 or early['maxGoldPerItem'] < 0:
        raise ExportError('Policy earlyGame limits must be non-negative, level at least 1')
    if not isinstance(policy.get('hostileFightThreshold'), int):
        raise ExportError('Policy hostileFightThreshold is missing or not an integer')
    danger = early.get('danger') or {}
    if not (danger.get('limits') or danger.get('benchmark')):
        raise ExportError('Policy earlyGame.danger needs either limits or a benchmark cell')
    return policy


def details(value):
    """Stored JSON columns are sometimes the literal null; treat that as empty."""
    return (json.loads(value) if value else None) or {}


def actor_stats(world, profile, object_key, cache=None):
    if cache is not None and ('actor', profile, object_key) in cache:
        return cache['actor', profile, object_key]
    row = world.execute('''SELECT a.level,a.details FROM profile_objects p
        JOIN actors a ON a.version_id=p.version_id WHERE p.profile_id=? AND p.object_key=?''',
        (profile, object_key)).fetchone()
    extra = details(row[1]) if row else {}
    stats = None if row is None else {'key': object_key, 'level': row[0] or 0,
                                      'health': extra.get('health') or 0,
                                      'fight': (extra.get('ai') or {}).get('fight', 0)}
    if cache is not None:
        cache['actor', profile, object_key] = stats
    return stats


def actor_threat(world, profile, object_key, threshold, cache=None):
    """Only actors that attack on sight populate a cell's danger."""
    stats = actor_stats(world, profile, object_key, cache)
    return stats if stats and stats['fight'] >= threshold else None


def leveled_worst(world, profile, object_key, level, threshold, cache=None):
    """A leveled spawn is judged at its worst qualifying candidate for the level."""
    if cache is not None and ('list', profile, object_key, level) in cache:
        return cache['list', profile, object_key, level]
    row = world.execute('''SELECT l.version_id FROM profile_objects p
        JOIN leveled_lists l ON l.version_id=p.version_id WHERE p.profile_id=? AND p.object_key=?''',
        (profile, object_key)).fetchone()
    worst = None
    for candidate, in (world.execute(
            'SELECT object_key FROM leveled_entries WHERE list_version_id=? AND minimum_level<=?',
            (row[0], level)) if row else ()):
        threat = actor_threat(world, profile, candidate, threshold, cache)
        if threat and (worst is None or (threat['level'], threat['health']) > (worst['level'], worst['health'])):
            worst = threat
    if cache is not None:
        cache['list', profile, object_key, level] = worst
    return worst


def cell_danger(world, profile, cell_key, level, threshold, cache=None):
    """Worst-case hostile population of one cell for a character at this level."""
    if cache is not None and ('cell', profile, cell_key) in cache:
        return cache['cell', profile, cell_key]
    threats = []
    # CROSS JOIN fixes join order: the cell index first, then exact profile/object keys.
    for record_type, object_key in world.execute('''
            SELECT o.record_type,o.object_key FROM placements pl INDEXED BY placement_cell
            CROSS JOIN profile_placements pp
              ON pp.profile_id=? AND pp.reference_key=pl.reference_key AND pp.version_id=pl.version_id
            CROSS JOIN profile_objects po ON po.profile_id=pp.profile_id AND po.object_key=pl.object_key
            CROSS JOIN objects o ON o.version_id=po.version_id
            WHERE pl.cell_key=? AND o.record_type IN ('NPC_','CREA','LEVC')''',
            (profile, cell_key)):
        threat = (leveled_worst(world, profile, object_key, level, threshold, cache) if record_type == 'LEVC'
                  else actor_threat(world, profile, object_key, threshold, cache))
        if threat:
            threats.append(threat)
    result = {'cellKey': cell_key, 'characterLevel': level, 'hostiles': len(threats),
              'maxActorLevel': max((t['level'] for t in threats), default=0),
              'totalHealth': sum(t['health'] for t in threats),
              'actors': sorted(threats, key=lambda t: (-t['level'], t['key']))}
    if cache is not None:
        cache['cell', profile, cell_key] = result
    return result


def resolve_limits(world, policy):
    """Prefer authored numbers; otherwise measure the benchmark encounter itself."""
    early = policy['earlyGame']
    danger = early.get('danger') or {}
    if danger.get('limits'):
        return danger['limits'] | {'source': 'authored'}
    mark = danger['benchmark']
    measured = cell_danger(world, mark['profile'], mark['cellKey'], early['characterLevel'],
                           policy['hostileFightThreshold'])
    if not measured['hostiles']:
        raise ExportError(f'Benchmark cell {mark["cellKey"]!r} has no hostiles in profile '
                          f'{mark["profile"]!r}; check the cell key and profile')
    return {'maxHostiles': measured['hostiles'], 'maxActorLevel': measured['maxActorLevel'],
            'maxTotalHealth': measured['totalHealth'], 'source': 'benchmark',
            'benchmark': mark | {'measured': measured}}


def with_obstacle(danger, actor):
    """A carried item adds its holder to whatever the cell already presents."""
    if actor is None:
        return danger
    return danger | {'hostiles': danger['hostiles']+1,
                     'maxActorLevel': max(danger['maxActorLevel'], actor['level']),
                     'totalHealth': danger['totalHealth']+actor['health'],
                     'actors': danger['actors']+[actor|{'role': 'holder'}]}


def within_limits(danger, limits):
    return (danger['hostiles'] <= limits['maxHostiles']
            and danger['maxActorLevel'] <= limits['maxActorLevel']
            and danger['totalHealth'] <= limits['maxTotalHealth'])


def reachability(static):
    """Best route quality from the item up to each holder in the reverse graph."""
    root = static['nodes'][0]['versionId']
    rank = {root: DIRECT}
    changed = True
    while changed:
        changed = False
        for edge in static['edges']:
            below = rank.get(edge['targetVersionId'])
            if below is None:
                continue
            if edge['kind'] == 'leveled' or below == RANDOM:
                quality = RANDOM
            elif (edge['details'] or {}).get('restocking'):
                quality = max(below, RESTOCKING)
            else:
                quality = max(below, INVENTORY)
            if quality < rank.get(edge['parentVersionId'], RANDOM + 1):
                rank[edge['parentVersionId']] = quality
                changed = True
    return rank


def effective_value(value, maximum, condition):
    """Worth scales with remaining condition; -1 and absent both mean undamaged."""
    if value is None or not maximum or condition is None or condition < 0:
        return value, None
    remaining = min(condition, maximum)
    return round(value*remaining/maximum), {'raw': condition, 'maximum': maximum,
                                            'ratio': round(remaining/maximum, 4),
                                            'worn': remaining < maximum}


def sells(services, profile, actor_key, record_type, enchanted):
    if services is None or not actor_key:
        return None
    row = services.execute('''SELECT p.services_raw FROM profile_providers f
        JOIN providers p ON p.version_id=f.version_id WHERE f.profile_id=? AND f.actor_key=?''',
        (profile, actor_key)).fetchone()
    if row is None:
        return None
    wanted = SERVICE_BITS.get(record_type, 0) | (MAGIC_ITEMS_BIT if enchanted else 0)
    return bool(row[0] & wanted) if wanted else False


def catalog_record(catalogs, profile, record_type, key):
    """Value and enchantment live in the typed catalogs; world databases lack both."""
    if catalogs is None or record_type not in CATEGORY_FILES:
        return None
    path = Path(catalogs)/profile/(CATEGORY_FILES[record_type]+'.json')
    if not path.is_file():
        return None
    for record in json.loads(path.read_text(encoding='utf-8'))['records']:
        if record.get('key') == key:
            return record
    return None


def assess(world, services, catalogs, profile, static, script, policy, limits=None, truncated=False):
    early = policy['earlyGame']
    threshold, level = policy['hostileFightThreshold'], early['characterLevel']
    if limits is None:
        limits = resolve_limits(world, policy)
    root = static['nodes'][0]
    nodes = {node['versionId']: node for node in static['nodes']}
    rank = reachability(static)
    record = catalog_record(catalogs, profile, root['recordType'], root['key']) or {}
    enchanted = bool(record.get('enchantmentId'))
    value = record.get('value')
    maximum = record.get(CONDITION_MAX.get(root['recordType'], ''))
    cache, routes = {}, []
    for placement in static['placements']:
        holder = nodes[placement['nodeVersionId']]
        quality = rank.get(holder['versionId'], RANDOM)
        extra = placement.get('details') or {}
        worth, condition = effective_value(value, maximum, extra.get('itemChargeOrConditionRaw'))
        # Shop stock is owned by its merchant, so the owner is a vendor, not a victim.
        vendor = placement.get('ownerKey') if early['vendorOwnedPlacementsArePurchasable'] else None
        purchasable = bool(quality == RESTOCKING
                           or sells(services, profile, holder['key'], root['recordType'], enchanted)
                           or sells(services, profile, vendor, root['recordType'], enchanted))
        # An item inside an actor is guarded by that actor, however placid it is standing there.
        carrier = (actor_stats(world, profile, holder['key'], cache)
                   if holder['recordType'] in ('NPC_', 'CREA') and not purchasable else None)
        owned = bool(placement.get('ownerKey') or placement.get('factionKey'))
        faction_only = bool(placement.get('factionKey') and not placement.get('ownerKey'))
        theft = not purchasable and (bool(carrier) or
                                     (owned and not (faction_only and early['assumeFactionAccess'])))
        danger = with_obstacle(cell_danger(world, profile, placement['cellKey'], level, threshold, cache), carrier)
        reasons = []
        if quality == RANDOM:
            reasons.append('random: only reachable through a leveled list')
        elif early['requireGuaranteedSource'] and quality == RESTOCKING and not early['countRestockingMerchantsAsGuaranteed']:
            reasons.append('restocking merchant stock is not counted as guaranteed')
        if condition and not condition['ratio'] and not early['allowBrokenItems']:
            # Worth nothing and does nothing until a hammer and an Armorer skill say otherwise.
            reasons.append(f'fully worn ({condition["raw"]} of {condition["maximum"]}): '
                           'unusable until repaired')
        if theft and not early['allowTheft']:
            reasons.append('requires theft and the policy forbids it')
        if not within_limits(danger, limits):
            reasons.append(f'danger above the benchmark: {danger["hostiles"]} hostile(s), '
                           f'level up to {danger["maxActorLevel"]}, {danger["totalHealth"]} total health')
        if purchasable:
            if worth is None:
                reasons.append('purchase price unknown: no catalog value available')
            elif worth > early['maxGoldPerItem']:
                reasons.append(f'costs {worth} gold, above the {early["maxGoldPerItem"]} gold cap')
        routes.append({
            'holder': {'key': holder['key'], 'name': holder['name'], 'recordType': holder['recordType']},
            'quality': QUALITY_NAMES[quality],
            'sourceQuality': 'random' if quality == RANDOM else 'guaranteed',
            'acquisition': 'purchase' if purchasable else 'pickpocket' if carrier else 'theft' if theft
                           else 'direct' if holder['versionId'] == root['versionId'] else 'take',
            'heldBy': carrier,
            'cellKey': placement['cellKey'], 'referenceKey': placement['referenceKey'],
            'ownerKey': placement.get('ownerKey'), 'factionKey': placement.get('factionKey'),
            'lockLevel': extra.get('lockLevelRaw') or 0, 'trapId': extra.get('trapId'),
            'condition': condition, 'value': worth,
            'theftRequired': theft, 'price': worth if purchasable else None,
            'danger': danger, 'dangerWithinBenchmark': within_limits(danger, limits),
            'earlyGameEligible': not reasons, 'reasons': reasons})

    grants = [event for event in script.get('events', [])
              if event.get('effectCategory') in ('addition', 'creation', 'list_addition')]
    guaranteed = [r for r in routes if r['sourceQuality'] == 'guaranteed']
    purchases = [r for r in routes if r['price'] is not None]
    # A broken item is stocked but not a price anyone would quote.
    priced = purchases if early['allowBrokenItems'] else [
        r for r in purchases if not (r['condition'] and not r['condition']['ratio'])]
    eligible = [r for r in routes if r['earlyGameEligible']]
    if guaranteed:
        obtainable = 'guaranteed'
    elif routes:
        obtainable = 'random'
    elif grants:
        obtainable = 'script_conditional'
    else:
        obtainable = 'unknown' if truncated else 'none'
    restocks = any(r['quality'] == 'restocking' for r in routes)
    return {
        'policy': {'version': policy['policyVersion'], 'name': policy.get('name'),
                   'schemaVersion': policy['schemaVersion'], 'evaluatorVersion': VERSION},
        'limits': limits,
        'obtainable': obtainable,
        'theftRequired': None if not routes else all(r['theftRequired'] for r in routes),
        'evidenceTruncated': bool(truncated),
        'saleStatus': 'restocking' if restocks else 'stocked' if purchases else 'not_sold',
        'price': min((r['price'] for r in priced), default=None),
        'earlyGameEligible': True if eligible else None if truncated else False,
        'basisValue': value,
        'counts': {'routes': len(routes), 'guaranteed': len(guaranteed),
                   'earlyGameEligible': len(eligible), 'scriptGrants': len(grants)},
        'coverage': 'Verdicts follow the cited policy over the cited evidence. Script grants are '
                    'lexical evidence, not proof of execution, and never make a route eligible. '
                    'Prices are catalog base values; merchant markup is not simulated.',
        'routes': routes}
