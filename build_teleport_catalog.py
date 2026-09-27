"""The teleports no travel service sells: Propylons, dialogue transports, and the like.

Morrowind moves the player by script as well as by boat. A Propylon activator sends you
to the next stronghold if you carry its index; Asciene Rane sends you to Mournhold when
you ask; a vampire clan's amulet takes you to the clan's lair. None of it is in a travel
record. It is in scripts: every `Player->PositionCell` and `Player->Position` a script or
dialogue result can run, read from the script evidence catalog's full sources.

Only teleports the player can choose to take again are published: Propylons, dialogue,
activators and doors, and items with one destination. Scripts attached to NPCs and
creatures, and scripts nothing starts, move the player once during a quest; they are
counted, never published. Conditions are kept: the items a Propylon checks for, and the
journal, variable and other tests a dialogue line or script branch makes.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
from collections import defaultdict
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
from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'
CELL_SIZE = 8192

# The player receiver, then the command, then its arguments, at the start of a line.
TELEPORT = re.compile(r'^[ \t]*(?:("?)([\w .\'-]+)\1[ \t]*->[ \t]*)?(positioncell|position)\b[ \t,]*(.*)$',
                      re.I | re.M)
NUMBER = re.compile(r'-?\d+(?:\.\d+)?')
QUOTED = re.compile(r'"([^"]*)"')
ITEM_TEST = re.compile(r'getitemcount[\s,]*(?:"([^"]+)"|([\w.\-\']+))\s*(>=|>|!=|==|<=|<|=)\s*(-?\d+)', re.I)
BRANCH = re.compile(r'^\s*(if|elseif)\b\s*(.*)$', re.I)
ELSE = re.compile(r'^\s*else\b', re.I)
ENDIF = re.compile(r'^\s*endif\b', re.I)
START_SCRIPT = re.compile(r'^\s*startscript\b[\s,]*"?([\w .\'-]+?)"?\s*(?:;.*)?$', re.I)
# Tests every activation script makes that say nothing about who may travel: the
# activation itself, the menu that asks "Teleport?" and the answer to it.
ROUTINE = re.compile(r'^\(?\s*(onactivate|menumode|onpcequip|onpcadd|onpcdrop|messageon|button|doonce)'
                     r'\s*(==\s*-?\d+)?\s*\)?$', re.I)
# A condition that ties a teleport to quest progress.
QUEST_TEST = re.compile(r'journal|getjournalindex|global|local|getpcrank|getdeadcount|getdisposition', re.I)

ITEM_TYPES = {'CLOT', 'MISC', 'ALCH', 'INGR', 'BOOK', 'ARMO', 'WEAP', 'LIGH'}
PLACED_TYPES = {'ACTI', 'DOOR', 'CONT'}
ACTOR_TYPES = {'NPC_', 'CREA'}

# ESM::DialogueCondition::Function, components/esm3/dialoguecondition.hpp (OpenMW 0.51.0),
# in enum order: a type-1 condition's two digits index this list.
FUNCTIONS = dict(enumerate((
    'FacReactionLowest FacReactionHighest RankRequirement Reputation HealthPercent PcReputation '
    'PcLevel PcHealthPercent PcMagicka PcFatigue PcStrength PcBlock PcArmorer PcMediumArmor '
    'PcHeavyArmor PcBluntWeapon PcLongBlade PcAxe PcSpear PcAthletics PcEnchant PcDestruction '
    'PcAlteration PcIllusion PcConjuration PcMysticism PcRestoration PcAlchemy PcUnarmored '
    'PcSecurity PcSneak PcAcrobatics PcLightArmor PcShortBlade PcMarksman PcMercantile '
    'PcSpeechcraft PcHandToHand PcGender PcExpelled PcCommonDisease PcBlightDisease '
    'PcClothingModifier PcCrimeLevel SameSex SameRace SameFaction FactionRankDifference Detected '
    'Alarmed Choice PcIntelligence PcWillpower PcAgility PcSpeed PcEndurance PcPersonality PcLuck '
    'PcCorprus Weather PcVampire Level Attacked TalkedToPc PcHealth CreatureTarget FriendHit Fight '
    'Hello Alarm Flee ShouldAttack Werewolf PcWerewolfKills').split()))
CONDITION_TYPES = {'2': 'global', '3': 'local', '4': 'journal', '5': 'item', '6': 'dead', '7': 'not id',
                   '8': 'not faction', '9': 'not class', 'A': 'not race', 'B': 'not cell', 'C': 'not local'}
COMPARISONS = {'0': '==', '1': '!=', '2': '>', '3': '>=', '4': '<', '5': '<='}


def strip_comment(line):
    """Drop a ; comment that is not inside quotes."""
    quoted = False
    for i, ch in enumerate(line):
        if ch == '"':
            quoted = not quoted
        elif ch == ';' and not quoted:
            return line[:i]
    return line


def branches(text):
    """For each line, the conditions it runs under: (must hold, must not hold)."""
    stack, out = [], []
    for raw in text.splitlines():
        line = strip_comment(raw)
        branch = BRANCH.match(line)
        if branch and branch.group(1).lower() == 'if':
            stack.append({'prior': [], 'current': branch.group(2).strip()})
        elif branch and stack:
            stack[-1]['prior'].append(stack[-1]['current'])
            stack[-1]['current'] = branch.group(2).strip()
        elif ELSE.match(line) and stack:
            stack[-1]['prior'].append(stack[-1]['current'])
            stack[-1]['current'] = None
        elif ENDIF.match(line) and stack:
            stack.pop()
        out.append(([f['current'] for f in stack if f['current']],
                    [c for f in stack for c in f['prior'] if c]))
    return out


def item_tests(condition):
    """Items a condition says the player carries: [(id, carried)]."""
    found = []
    for quoted, bare, op, value in ITEM_TEST.findall(condition):
        n = int(value)
        carried = (op == '>' and n >= 0) or (op == '>=' and n >= 1) or (op in ('!=',) and n == 0)
        empty = (op in ('==', '=') and n == 0) or (op == '<' and n <= 1) or (op == '<=' and n == 0)
        if carried or empty:
            found.append(((quoted or bare).strip().lower(), carried))
    return found


def gates(positive, negative):
    """What a script branch asks of the player: items needed, items that divert, other tests."""
    requires, unless, other = [], [], []
    for condition in positive:
        tests = item_tests(condition)
        for item, carried in tests:
            (requires if carried else unless).append(item)
        rest = ITEM_TEST.sub('', condition)
        if not tests and not ROUTINE.match(condition.strip()) and re.search(r'[a-z]', rest, re.I):
            other.append(condition)
    for condition in negative:
        # An earlier branch that took the player elsewhere: its item diverts them.
        for item, carried in item_tests(condition):
            (unless if carried else requires).append(item)
    return sorted(set(requires)), sorted(set(unless) - set(requires)), other


def parse_destination(command, arguments):
    """(cell name or None, x, y) from PositionCell's or Position's arguments."""
    arguments = strip_comment(arguments)
    names = QUOTED.findall(arguments)
    numbers = [float(n) for n in NUMBER.findall(QUOTED.sub(' ', arguments))]
    if len(numbers) < 2:
        return None
    if command.lower() == 'position':
        return None, numbers[0], numbers[1]
    name = names[0] if names else None
    if name is None:
        tail = re.sub(r'^[\s,\-\d.]+', '', QUOTED.sub(' ', arguments)).strip(' ,')
        name = tail or None
    return name, numbers[0], numbers[1]


def resolve_cell(name, x, y, cells):
    """The destination's cell key, or None when the profile has no such cell."""
    if name:
        key = 'interior:' + name.strip().lower()
        if key in cells:
            return key
    grid = f'exterior:{math.floor(x / CELL_SIZE)},{math.floor(y / CELL_SIZE)}'
    return grid if grid in cells else None


def dialogue_items(context):
    """Items a dialogue line tests for: (needed, diverting)."""
    requires, unless = [], []
    for condition in (context or {}).get('conditions') or []:
        rule = condition.get('rule_raw') or ''
        if len(rule) < 5 or rule[1] != '5' or not condition.get('variable_raw'):
            continue
        item, op = condition['variable_raw'].lower(), COMPARISONS.get(rule[4])
        try:
            value = int(json.loads(condition.get('value_json') or '0'))
        except (TypeError, ValueError):
            continue
        if (op == '>=' and value >= 1) or (op == '>' and value >= 0) or (op == '!=' and value == 0):
            requires.append(item)
        elif (op == '==' and value == 0) or (op == '<' and value <= 1):
            unless.append(item)
    return requires, unless


def describe_conditions(context):
    """A dialogue line's conditions, as text, leaving out the menu choice that picks it and
    the item tests, which are published as requires and unless."""
    out = []
    for condition in (context or {}).get('conditions') or []:
        rule = condition.get('rule_raw') or ''
        if len(rule) < 5:
            continue
        kind, function, comparison = rule[1], rule[2:4], rule[4]
        op = COMPARISONS.get(comparison, '?')
        value = condition.get('value_json')
        if kind == '1':
            name = FUNCTIONS.get(int(function) if function.isdigit() else -1, f'function {function}')
            if name == 'Choice':
                continue
            out.append(f'{name} {op} {value}')
        elif kind == '5':
            continue
        else:
            out.append(f'{CONDITION_TYPES.get(kind, kind)} {condition.get("variable_raw") or ""} {op} {value}'.replace('  ', ' '))
    return out


def placements(world, profile, object_keys):
    """Where the given objects stand: {object: [(cell, x, y)]}. Object keys are stored
    lowercased, so the lookup can use the placement_item index."""
    keys = sorted({k.lower() for k in object_keys if k})
    found = defaultdict(list)
    for start in range(0, len(keys), 500):
        chunk = keys[start:start + 500]
        # CROSS JOIN fixes the join order: placements by object first, through its index,
        # then each one's profile row by primary key. Left to SQLite, it scans the profile.
        for obj, cell, x, y in world.execute(
                'SELECT p.object_key, p.cell_key, p.x, p.y FROM placements p '
                'CROSS JOIN profile_placements pp ON pp.profile_id = ? AND pp.reference_key = p.reference_key '
                ' AND pp.version_id = p.version_id '
                f'WHERE p.object_key IN ({",".join("?" * len(chunk))})',
                (profile, *chunk)):
            found[obj].append((cell, x, y))
    return found


def object_names(world, profile):
    return {key.lower(): name for key, name in world.execute(
        'SELECT po.object_key, o.name FROM profile_objects po JOIN objects o ON o.version_id = po.version_id '
        'WHERE po.profile_id = ?', (profile,)) if name}


def applies(rule, profile):
    return profile in rule.get('profiles', ('vanilla', 'tr', 'tr_arce'))


def matches(record, rule):
    return all(str(record.get(field) or '').lower() == str(value).lower()
               for field, value in rule['match'].items())


def gate_reason(record, policy):
    """Why a teleport is not everyday travel, or None when it is.

    Everyday means a player can take it again whenever they like: a Propylon or an
    item, gated only by what the player carries, a dialogue gated only by an item, or
    anything the policy names. Everything else is a quest's: a condition on a journal,
    a variable or a script's own state, a greeting, a dialogue topic that only exists
    during a quest, or an activator that is a trap or a scene. Published either way.
    """
    for rule in policy.get('everyday', []):
        if applies(rule, record['profile']) and matches(record, rule):
            return None
    for rule in policy.get('questOnly', []):
        if applies(rule, record['profile']) and matches(record, rule):
            return 'authored'
    if record['conditions']:
        return 'conditions'
    if (record.get('topic') or '').startswith('greeting'):
        return 'greeting'
    if record['kind'] in ('propylon', 'item'):
        return None
    if record['kind'] == 'dialogue':
        return None if record['requires'] else 'dialogue topic'
    return 'activator'


def activated(positive):
    """True when a script line runs because the player used the object."""
    return any(re.search(r'\bonactivate\b', c, re.I) for c in positive)


def load_policy(path):
    policy = json.loads(Path(path).read_text(encoding='utf-8'))
    if policy.get('schemaVersion') != VERSION:
        raise ExportError(f'Unsupported teleport policy schema {policy.get("schemaVersion")!r}')
    for name in ('everyday', 'questOnly'):
        rules = policy.get(name)
        if not isinstance(rules, list) or not all(
                isinstance(r, dict) and isinstance(r.get('match'), dict) and r['match']
                and set(r['match']) <= {'source', 'topic', 'speaker', 'to', 'kind'}
                and isinstance(r.get('why'), str) and r['why'].strip()
                and (r.get('profiles') is None or (isinstance(r['profiles'], list) and r['profiles']
                                                   and set(r['profiles']) <= {'vanilla', 'tr', 'tr_arce'}))
                for r in rules):
            raise ExportError(f'Teleport policy {name} must be a list of {{match, why}}, matching on '
                              'source, topic, speaker, to or kind')
    return policy


def build(evidence, world, services, profile, policy=None):
    policy = policy or {'everyday': [], 'questOnly': []}
    cells = {key: name for key, name in services.execute(
        'SELECT cell_key, name FROM cells WHERE profile_id = ?', (profile,))}
    if not cells:
        raise ExportError(f'No cells for profile {profile}; build the services catalog first')
    attached = defaultdict(list)
    for script, rtype, obj in evidence.execute(
            'SELECT lower(script_key), record_type, lower(object_key) FROM script_attachments WHERE profile_id = ?',
            (profile,)):
        attached[script].append((rtype, obj))
    sources = evidence.execute(
        'SELECT s.version_id, s.kind, s.source_key, s.topic_key, s.source_text, s.dialogue_context_json '
        'FROM sources s JOIN profile_sources ps ON ps.version_id = s.version_id WHERE ps.profile_id = ?',
        (profile,)).fetchall()
    # Which dialogue lines start which scripts: an unattached teleport script is a
    # dialogue transport when a line of dialogue starts it (Mournhold's is).
    started_by = defaultdict(list)
    for _vid, kind, _key, topic, text, context in sources:
        if kind != 'dialogue':
            continue
        for line in text.splitlines():
            start = START_SCRIPT.match(strip_comment(line))
            if start:
                started_by[start.group(1).strip().lower()].append((topic, json.loads(context or '{}')))
    names = object_names(world, profile)
    skipped = defaultdict(int)
    found = []  # (kind, source, origin spec, destination, gate, label bits)
    for _vid, kind, key, topic, text, context in sources:
        if not TELEPORT.search(text):
            continue
        conditions = branches(text)
        lines = text.splitlines()
        teleports = []
        for number, raw in enumerate(lines):
            match = TELEPORT.match(strip_comment(raw))
            if not match:
                continue
            receiver = (match.group(2) or '').strip().lower()
            if receiver != 'player':
                skipped['movesSomeoneElse'] += 1
                continue
            parsed = parse_destination(match.group(3), match.group(4))
            if not parsed:
                skipped['unreadableArguments'] += 1
                continue
            destination = resolve_cell(*parsed, cells)
            if not destination:
                skipped['destinationNotInProfile'] += 1
                continue
            if kind == 'script' and attached.get((key or '').lower()) \
                    and {t for t, _ in attached[(key or '').lower()]} & PLACED_TYPES \
                    and not activated(conditions[number][0]):
                # Runs on its own, not when used: a Recall blocker, a trap, a scene.
                skipped['activatorNotUsed'] += 1
                continue
            teleports.append((destination, parsed, gates(*conditions[number])))
        if not teleports:
            continue
        script = (key or '').lower()
        if kind == 'dialogue':
            speakers = [(topic, json.loads(context or '{}'))]
            origin_kind = 'dialogue'
        elif attached.get(script):
            types = {t for t, _ in attached[script]}
            if types & PLACED_TYPES:
                origin_kind = 'activator'
            elif types & ITEM_TYPES:
                origin_kind = 'item'
                if len({t[0] for t in teleports}) > 1:
                    skipped['itemWithSeveralDestinations'] += len(teleports)
                    continue
            else:
                skipped['questScriptOnActor'] += len(teleports)
                continue
        elif started_by.get(script):
            speakers = started_by[script]
            origin_kind = 'dialogue'
        else:
            skipped['scriptNothingStarts'] += len(teleports)
            continue
        propylon = any('propylon chamber' in (cells.get(d) or '').lower() for d, _, _ in teleports)
        for index, (destination, (_name, x, y), (requires, unless, other)) in enumerate(teleports):
            record = {'kind': 'propylon' if propylon else origin_kind, 'to': destination,
                      'toPos': [round(x), round(y)], 'requires': requires, 'unless': unless,
                      'conditions': other, 'source': key}
            if origin_kind == 'dialogue':
                for topic_key, ctx in speakers:
                    speaker = (ctx.get('actor_key') or '').lower()
                    where = []
                    if speaker:
                        where = placements(world, profile, [speaker]).get(speaker, [])
                    elif ctx.get('cell_filter'):
                        cell = 'interior:' + ctx['cell_filter'].lower()
                        where = [(cell, None, None)] if cell in cells else []
                    if not where:
                        skipped['dialogueWithNoPlace'] += 1
                        continue
                    needed, diverting = dialogue_items(ctx)
                    found.append(record | {
                        'from': sorted({c for c, _, _ in where}),
                        'fromPos': [[round(px), round(py)] for _, px, py in where if px is not None],
                        'speaker': speaker or None, 'speakerName': names.get(speaker), 'topic': topic_key,
                        'requires': sorted(set(requires) | set(needed)),
                        'unless': sorted((set(unless) | set(diverting)) - set(needed)),
                        'conditions': other + describe_conditions(ctx),
                        'key': f'{record["kind"]}|{key}|{topic_key}|{speaker}|{index}'})
            elif origin_kind == 'activator':
                objects = [o for t, o in attached[script] if t in PLACED_TYPES]
                where = [w for obj in objects for w in placements(world, profile, [obj]).get(obj, [])]
                if not where:
                    skipped['activatorNotPlaced'] += 1
                    continue
                found.append(record | {
                    'from': sorted({c for c, _, _ in where}),
                    'fromPos': [[round(px), round(py)] for _, px, py in where if px is not None],
                    'object': objects[0], 'objectName': names.get(objects[0]),
                    'key': f'{record["kind"]}|{key}|{index}'})
            else:
                objects = [o for t, o in attached[script] if t in ITEM_TYPES]
                found.append(record | {
                    'from': [], 'fromPos': [], 'requires': sorted(set(requires) | set(objects[:1])),
                    'object': objects[0], 'objectName': names.get(objects[0]),
                    'key': f'item|{key}|{index}'})
    seen, records, matched = set(), [], set()
    for record in sorted(found, key=lambda r: r['key']):
        if record['key'] in seen:
            continue
        seen.add(record['key'])
        reason = gate_reason(record | {'profile': profile}, policy)
        record['questGated'] = reason is not None
        if reason:
            record['gatedBecause'] = reason
        for name in ('everyday', 'questOnly'):
            for number, rule in enumerate(policy.get(name, [])):
                if applies(rule, profile) and matches(record, rule):
                    matched.add((name, number))
        records.append(record)
    rules = [(name, n) for name in ('everyday', 'questOnly')
             for n, rule in enumerate(policy.get(name, [])) if applies(rule, profile)]
    unmatched = [policy[name][n]['match'] for name, n in rules if (name, n) not in matched]
    if unmatched:
        raise ExportError(f'{profile}: {len(unmatched)} rule(s) in policy/teleports.json match no '
                          f'teleport: {unmatched[:3]}\n  A renamed topic or speaker would otherwise '
                          'change what the site shows without a word. Fix or remove the rule.')
    items = sorted({i for r in records for i in r['requires'] + r['unless']})
    return records, {i: names.get(i) for i in items}, dict(skipped)


def assemble(evidence, world, services, profile, snapshot, policy=None):
    records, items, skipped = build(evidence, world, services, profile, policy)
    by_kind = defaultdict(int)
    for record in records:
        by_kind[record['kind']] += 1
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'items': items,
        'derivation': {
            'method': 'every Player->PositionCell and Player->Position in scripts and dialogue '
                      'results, with the branch conditions around it',
            'teleports': len(records), 'byKind': dict(sorted(by_kind.items())),
            'questGated': sum(1 for r in records if r['questGated']),
            'skipped': dict(sorted(skipped.items()))},
        'policyVersion': (policy or {}).get('policyVersion'),
        'coverage': 'Teleports the player can choose to take: Propylons, dialogue transports, '
                    'activators and doors, and items with one destination. `requires` lists '
                    'items the script or dialogue checks the player carries, `unless` items that '
                    'send them elsewhere first, and `conditions` every other test, unevaluated. '
                    '`questGated` marks a teleport that is not everyday travel, and '
                    '`gatedBecause` says why: conditions, a greeting, a dialogue topic only a '
                    'quest opens, an activator, or an authored rule. Activators that run without '
                    'being used (Recall blockers, traps), scripts on NPCs and creatures, and '
                    'scripts nothing starts are left out; skipped counts them.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.teleports-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--evidence-database', type=Path)
    parser.add_argument('--world-database', type=Path)
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--policy', type=Path)
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        policy = load_policy(args.policy or ROOT/'policy/teleports.json')
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        paths = (args.evidence_database or root/'script-evidence/script-evidence.sqlite',
                 args.world_database or root/'world/world.sqlite',
                 args.services_database or root/'services/services.sqlite')
        written = []
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(
                    sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                dbs.append(db)
            evidence, world, services = dbs
            snapshot = metadata(services).get('snapshotId')
            for db, name in ((evidence, 'script evidence'), (world, 'world')):
                other = metadata(db).get('snapshotId')
                if snapshot and other and other != snapshot:
                    raise ExportError(f'services ({snapshot[:12]}) and {name} ({other[:12]}) come from '
                                      'different extractions; rebuild the older one first')
            for profile in profiles:
                payload = assemble(evidence, world, services, profile, snapshot, policy)
                destination, size = publish(payload, args.output or root/'teleports', profile)
                d = payload['derivation']
                print(f'{profile}: {d["teleports"]} teleports ({d["questGated"]} quest-gated) ' + json.dumps(d['byKind'])
                      + f'; left out {sum(d["skipped"].values())} ' + json.dumps(d['skipped'])
                      + f', {size/1024:.0f} KB', flush=True)
                written.append(destination)
        print('Teleport catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Teleport catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
