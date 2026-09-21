"""Build the best late-game constant-effect gear for every build, slot by slot.

A build is one of the premade characters the site defines in lib/premade-data.mjs:
a race, favoured attributes, and major and minor skills. For each one this ranks the
items that already carry a constant effect, per equipment slot, by how well those
effects serve that build. A Battlemage wants armour rating and magicka; a Pure melee
build wants neither the magicka nor the Drain Magicka that often comes attached.

Enchantment capacity and custom enchanting are out of scope by design. Questing is
always assumed: an item a script hands to the player counts, even with no placement.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time

from build_acquisition_index import metadata
from build_app_bundle import newest
from build_gear_rows import armor_class, beast_wearable
from evaluate_policy import load_policy
from export_items import ExportError
from extract_foundation import ROOT, load_config
from query_item_sources import unified_sources

VERSION = '1.0.0'
# Equipment slots as the engine keeps them. Gloves and bracers share the gauntlet
# slot, shoes share the boots slot, and both rings draw from one pool.
SLOT_OF = {
    'helmet': 'helmet', 'cuirass': 'cuirass', 'greaves': 'greaves',
    'boots': 'boots', 'shoes': 'boots',
    'left_pauldron': 'left_pauldron', 'right_pauldron': 'right_pauldron',
    'left_gauntlet': 'left_hand', 'left_bracer': 'left_hand', 'left_glove': 'left_hand',
    'right_gauntlet': 'right_hand', 'right_bracer': 'right_hand', 'right_glove': 'right_hand',
    'shield': 'shield', 'shirt': 'shirt', 'pants': 'pants', 'skirt': 'skirt',
    'robe': 'robe', 'belt': 'belt', 'amulet': 'amulet', 'ring': 'ring'}
# The weapon's governing skill, from its type code.
WEAPON_SKILL = {
    'SB1H': 'short_blade', 'LB1H': 'long_blade', 'LB2H': 'long_blade',
    'BL1H': 'blunt_weapon', 'BL2C': 'blunt_weapon', 'BL2W': 'blunt_weapon',
    'AX1H': 'axe', 'AX2H': 'axe', 'SP2H': 'spear',
    'BOW': 'marksman', 'CROSSBOW': 'marksman', 'THROWN': 'marksman'}
ARMOUR_SKILL = {'light': 'light_armor', 'medium': 'medium_armor', 'heavy': 'heavy_armor'}
# The site's own display names for races that share one ("Khajiit" is eight records),
# mirrored from lib/character-catalogs.mjs so a build's race resolves the same way.
RACE_LABELS = {
    't_els_cathay': 'Khajiit (Cathay)', 't_els_cathay-raht': 'Khajiit (Cathay-raht)',
    't_els_dagi-raht': 'Khajiit (Dagi-raht)', 't_els_ohmes': 'Khajiit (Ohmes)',
    't_els_ohmes-raht': 'Khajiit (Ohmes-raht)', 't_els_suthay': 'Khajiit (Suthay)',
    't_els_tojay': 'Khajiit (Tojay)'}
BUILD_SETS = ('BUILDS', 'RACE_BUILDS', 'ARCE_BUILDS')
SEVERITIES = ('none', 'minor', 'significant', 'disqualifying')


def skill_label(slug):
    """The site's skill label, from character-catalogs.mjs."""
    return 'Hand-to-hand' if slug == 'hand_to_hand' else ' '.join(
        word[0].upper() + word[1:] for word in slug.split('_'))


def load_late_policy(path):
    policy = json.loads(Path(path).read_text(encoding='utf-8'))
    if policy.get('schemaVersion') != VERSION:
        raise ExportError(f'Unsupported late-game policy schema {policy.get("schemaVersion")!r}')
    tiers = policy.get('tiers') or {}
    for name, rule in (policy.get('effects') or {}).items():
        if rule.get('tier') not in tiers:
            raise ExportError(f'Effect {name!r} names tier {rule.get("tier")!r}, which is not defined')
        if rule.get('fit') not in ('all', 'caster', 'fighter'):
            raise ExportError(f'Effect {name!r} has fit {rule.get("fit")!r}')
        if not isinstance(rule.get('cap'), (int, float)) or rule['cap'] <= 0:
            raise ExportError(f'Effect {name!r} needs a positive cap')
    overlap = set(policy['effects']) & set(policy['drawbacks'])
    if overlap:
        raise ExportError('Effects cannot be both a benefit and a drawback: '
                          + ', '.join(sorted(overlap)))
    for name, rule in policy['drawbacks'].items():
        values = [v for k, v in rule.items()
                  if k not in ('rule', 'mitigation', 'note', 'zeroesAt')]
        bad = [v for v in values if v not in SEVERITIES]
        if bad:
            raise ExportError(f'Drawback {name!r} uses unknown severity {bad[0]!r}')
    return policy


def load_builds(site, builds_file=None):
    """The site's premade builds, and a digest so a stale catalog can be spotted."""
    if builds_file:
        data = json.loads(Path(builds_file).read_text(encoding='utf-8'))
        source = str(builds_file)
    else:
        module = (Path(site)/'lib/premade-data.mjs').resolve()
        if not module.is_file():
            raise ExportError(f'Build definitions not found: {module}; pass --builds or --site')
        script = (f"import({json.dumps(module.as_uri())}).then(m => console.log(JSON.stringify("
                  + '{' + ','.join(f'{name}: m.{name}' for name in BUILD_SETS) + '})))')
        # Node writes UTF-8 whatever the console code page; without the encoding, Windows
        # decodes it as cp1252 and every em dash in a build name arrives as "â€”".
        run = subprocess.run(['node', '-e', script], capture_output=True, text=True,
                             encoding='utf-8')
        if run.returncode:
            raise ExportError(f'Could not read {module}: {run.stderr.strip()[:300]}')
        data = json.loads(run.stdout)
        source = str(module)
    builds = [dict(build, set=name) for name in BUILD_SETS for build in data.get(name) or ()]
    names = [b['name'] for b in builds]
    if len(set(names)) != len(names):
        raise ExportError('Build names must be unique; they are the catalog keys')
    digest = hashlib.sha256(json.dumps(builds, sort_keys=True).encode('utf-8')).hexdigest()
    return builds, source, digest


def catalog(release, profile, name):
    return json.loads((Path(release)/profile/(name+'.json')).read_text(encoding='utf-8'))['records']


def reference(release, profile):
    """Everything a build definition needs resolving against, for one profile."""
    races = {}
    for race in catalog(release, profile, 'Races'):
        races.setdefault(RACE_LABELS.get(race['key'], race['name']).casefold(), []).append(race)
    skills = catalog(release, profile, 'Skills')
    return {'races': races,
            'skills': {skill_label(s['skill']).casefold(): s['skill'] for s in skills},
            'governs': {s['skill']: s['governingAttribute'] for s in skills},
            'allSkills': [s['skill'] for s in skills],
            'attributes': {a['name'].casefold(): a['id'] for a in catalog(release, profile, 'Attributes')},
            'settings': {r['key']: r['value'] for r in catalog(release, profile, 'GameSettings')}}


def split(text):
    return [part.strip() for part in (text or '').split(',') if part.strip()]


def traits(build, ref, policy):
    """What a build values, derived from its own definition. Returns (traits, reason)."""
    found = ref['races'].get(build['race'].casefold(), [])
    if len(found) != 1:
        return None, (f'race {build["race"]!r} resolves to {len(found)} records')
    race = found[0]
    if not race.get('playable'):
        return None, f'race {build["race"]!r} is not playable in this profile'
    resolve_skill = lambda name: ref['skills'].get(name.casefold())
    major = [resolve_skill(s) for s in split(build['maj'])]
    minor = [resolve_skill(s) for s in split(build['min'])]
    favoured = [ref['attributes'].get(a.casefold()) for a in split(build['fav'])]
    if None in major + minor or None in favoured:
        raise ExportError(f'Build {build["name"]!r} names a skill or attribute that does not exist')
    tier = {skill: 'major' if skill in major else 'minor' if skill in minor else 'misc'
            for skill in ref['allSkills']}
    classed = set(major) | set(minor)
    governing = {ref['governs'][s] for s in classed}
    rule = policy['derived']['Fortify Attribute']
    weights = {}
    for attribute in ref['attributes'].values():
        if attribute in favoured:
            weights[attribute] = rule['favoured']
        elif attribute == 'luck':
            weights[attribute] = rule['luck']
        else:
            governed = sum(1 for s in classed if ref['governs'][s] == attribute)
            weights[attribute] = min(rule['ceiling'], rule['floor'] + rule['perGovernedSkill']*governed)
    archetype = lambda name: sum(1 for s in policy['archetypes'][name]['skills'] if s in classed) \
        >= policy['archetypes'][name]['atLeast']
    caster, fighter = archetype('caster'), archetype('fighter')
    critical = set(policy['criticalAttributes']['all'])
    if caster:
        critical |= set(policy['criticalAttributes']['caster'])
    if fighter:
        critical |= set(policy['criticalAttributes']['fighter'])
    return {'key': build['name'], 'category': build.get('cat'), 'set': build['set'],
            'race': race['key'], 'beast': bool(race.get('beast')),
            'favoured': set(favoured), 'skillTier': tier, 'governing': governing,
            'critical': critical, 'attributeWeight': weights,
            'caster': caster, 'fighter': fighter}, None


def candidates(release, profile, settings):
    """Every wearable item that already carries a constant effect."""
    enchantments = {e['key']: e for e in catalog(release, profile, 'Enchantments')
                    if e['castType'] == 'constant_effect'}
    found = []
    for name in ('Armor', 'Clothing', 'Weapons'):
        for record in catalog(release, profile, name):
            enchantment = enchantments.get(record.get('enchantmentId') or '')
            if enchantment is None:
                continue
            item = {'key': record['key'], 'name': record['name'], 'recordType': record['recordType'],
                    'type': record['type'], 'value': record.get('value'),
                    'beastWearable': beast_wearable(record),
                    'effects': [{'name': e['name'], 'skill': e.get('skill'),
                                 'attribute': e.get('attribute'),
                                 'magnitude': (e['magnitude']['min'] + e['magnitude']['max']) / 2}
                                for e in enchantment['effects']]}
            if name == 'Weapons':
                skill = WEAPON_SKILL.get(record['type'])
                if skill is None:
                    continue  # Ammunition is not an equipment slot.
                item.update(slot='weapon', weaponSkill=skill,
                            damage=max(record[k]['max'] for k in ('chop', 'slash', 'thrust')))
            else:
                slot = SLOT_OF.get(record['type'])
                if slot is None:
                    continue
                item['slot'] = slot
                if name == 'Armor':
                    item.update(armorRating=record['armorRating'],
                                armorClass=armor_class(record, settings))
            found.append(item)
    return found


def sources(dbs, profile, items, early_policy, release):
    """How each item can be had: placed in the world, handed over by a script, or neither.

    Route danger is measured with the early-game evaluator because it already knows how
    to walk a route and weigh what guards it; its early-game verdicts are not used.
    """
    acquisition, world, evidence, services = dbs
    for item in items:
        result = unified_sources(acquisition, world, evidence, profile, item['key'], None,
                                 2000, 5000, 12, 100, 100, 200, 100, 100,
                                 early_policy, services, release)
        routes = result['assessment'].get('routes') or []
        levels = [r['danger']['maxActorLevel'] if r.get('danger') else 0 for r in routes]
        # Only a script that gives the item to the player is a way of getting it.
        grants = sorted({str(e.get('source_key')) for e in result['script']['events']
                         if e.get('kind') == 'inventory_add' and e.get('recipient_kind') == 'player'})
        item['source'] = {
            'routes': len(routes), 'easiestLevel': min(levels) if levels else None,
            'questGrants': grants,
            'kind': 'placed' if routes else 'quest' if grants else 'unconfirmed'}


def severity(effect, rule, traits):
    """How bad this drawback is for this build.

    Magnitude only escalates what the build actually runs on. Neb-Crescen drains
    Willpower and Intelligence by 255, which ends a caster; the Mantle of Woe drains
    Personality by 100, which a caster can live with even though Personality happens to
    govern the Illusion both Conjurer builds carry.
    """
    kind = rule['rule']
    if kind == 'flat':
        return rule['severity']
    if kind == 'archetype':
        return rule['caster'] if traits['caster'] else rule['other']
    zeroes = rule.get('zeroesAt')
    if kind == 'attribute':
        attribute = effect['attribute']
        critical = attribute in traits['critical']
        if attribute in traits['favoured']:
            level = rule['favoured']
        elif critical:
            level = rule.get('critical', rule['governing'])
        elif attribute in traits['governing']:
            level = rule['governing']
        else:
            level = rule['other']
        if zeroes and critical and effect['magnitude'] >= zeroes:
            return 'disqualifying'
        return level
    if kind == 'skill':
        tier = traits['skillTier'].get(effect['skill'], 'misc')
        if zeroes and tier in ('major', 'minor') and effect['magnitude'] >= zeroes:
            return 'disqualifying'
        return rule[tier]
    raise ExportError(f'Unknown drawback rule {kind!r}')


def effect_label(effect):
    target = effect['skill'] or effect['attribute']
    name = effect['name']
    if target and name.startswith('Fortify '):
        name = 'Fortify ' + skill_label(target)
    elif target:
        name = f'{name} ({skill_label(target)})'
    return f'{name} {effect["magnitude"]:g}'


def saturate(value, cap):
    return max(0.0, min(value, cap)) / cap


def score(item, traits, policy):
    """Benefit, reasons and warnings for one item and one build; None if disqualified.

    Drawbacks are not subtracted from the benefit. The ones that ruin an item for this
    build remove it; the ones worth knowing are published beside the score.
    """
    tiers, parts, warnings = policy['tiers'], [], []
    for effect in item['effects']:
        name = effect['name']
        rule = policy['drawbacks'].get(name)
        if rule is not None:
            level = severity(effect, rule, traits)
            if level == 'disqualifying':
                return None
            if level == 'significant':
                warnings.append(effect_label(effect)
                                + (f' (cancelled by {rule["mitigation"]})' if rule.get('mitigation') else ''))
            continue
        if name == 'Fortify Skill':
            derived = policy['derived'][name]
            weight = derived[traits['skillTier'].get(effect['skill'], 'misc')]
            value = weight * saturate(effect['magnitude'], derived['cap'])
        elif name == 'Fortify Attribute':
            derived = policy['derived'][name]
            weight = traits['attributeWeight'].get(effect['attribute'], derived['floor'])
            value = weight * saturate(effect['magnitude'], derived['cap'])
        else:
            rule = policy['effects'][name]
            if rule['fit'] != 'all' and not traits[rule['fit']]:
                continue
            value = tiers[rule['tier']] * saturate(effect['magnitude'], rule['cap'])
        if value:
            parts.append((effect_label(effect), value))
    if item.get('armorRating') is not None:
        armour = policy['armour']
        tier = traits['skillTier'][ARMOUR_SKILL[item['armorClass']]]
        value = armour[tier] * saturate(item['armorRating'], armour['ratingCap'])
        if value:
            parts.append((f'{item["armorClass"].title()} armour {item["armorRating"]}', value))
    if item.get('weaponSkill'):
        weapons = policy['weapons']
        value = weapons[traits['skillTier'][item['weaponSkill']]] * saturate(
            item['damage'], weapons['damageCap'])
        if value:
            parts.append((f'{skill_label(item["weaponSkill"])} damage {item["damage"]}', value))
    parts.sort(key=lambda part: -part[1])
    return round(sum(v for _, v in parts), 2), parts, warnings


def eligible(item, traits, allow_formidable, formidable_level):
    source = item['source']
    if source['kind'] == 'unconfirmed':
        return False
    if traits['beast'] and not item['beastWearable']:
        return False
    if not allow_formidable and not source['questGrants'] \
            and (source['easiestLevel'] or 0) > formidable_level:
        return False
    return True


def rank(items, traits, policy, allow_formidable):
    toggle = policy['toggles']['allowFormidableSources']
    slots = {}
    for item in items:
        if not eligible(item, traits, allow_formidable, toggle['formidableLevel']):
            continue
        scored = score(item, traits, policy)
        if scored is None or scored[0] <= 0:
            continue
        slots.setdefault(item['slot'], []).append((scored, item))
    picks = {}
    for slot, entries in sorted(slots.items()):
        # Best first; among equals the one easier to get, then the name for stability.
        entries.sort(key=lambda entry: (-entry[0][0], entry[1]['source']['easiestLevel'] or 0,
                                        entry[1]['key']))
        # The same item often has several records -- helm_bearclaw_unique and
        # helm_bearclaw_unique_x are one helm to a player. Showing both would spend two
        # of the three picks saying the same thing, so keep the best-scoring, easiest
        # copy of each name.
        seen, unique = set(), []
        for entry in entries:
            name = entry[1]['name'].casefold()
            if name in seen:
                continue
            seen.add(name)
            unique.append(entry)
        chosen = []
        for position, ((value, parts, warnings), item) in enumerate(unique[:policy['picksPerSlot']]):
            pick = {'item': item['key'], 'score': value}
            if position == 0:
                pick['reasons'] = [[label, round(points, 2)] for label, points in parts[:3]]
            if warnings:
                pick['warnings'] = warnings
            chosen.append(pick)
        picks[slot] = chosen
    return picks


def check_coverage(policy, used):
    """Both directions: nothing real goes unmapped, and nothing mapped is imaginary."""
    covered = set(policy['effects']) | set(policy['derived']) | set(policy['drawbacks'])
    everywhere = set().union(*used.values()) if used else set()
    unmapped = sorted(everywhere - covered)
    if unmapped:
        raise ExportError(
            f'{len(unmapped)} constant effect(s) appear on candidates but the late-game policy '
            'does not cover them: ' + ', '.join(unmapped)
            + '\n  Place each in policy/late-game.json; an unmapped effect would score zero.')
    # Somewhere, not everywhere: many effects exist only on Tamriel Rebuilt items.
    absent = sorted(covered - everywhere)
    if absent:
        raise ExportError(
            f'{len(absent)} effect(s) in policy/late-game.json appear on no candidate in any '
            'profile: ' + ', '.join(absent))


def assemble(profile, builds, items, ref, policy, snapshot, builds_source, builds_digest):
    records, skipped = [], []
    for build in builds:
        found, reason = traits(build, ref, policy)
        if found is None:
            skipped.append({'build': build['name'], 'reason': reason})
            continue
        for allow in (False, True):
            records.append({'key': f'{found["key"]}/{int(allow)}', 'build': found['key'],
                            'category': found['category'], 'set': found['set'],
                            'race': found['race'], 'beast': found['beast'],
                            'caster': found['caster'], 'fighter': found['fighter'],
                            'toggles': {'allowFormidableSources': allow},
                            'slots': rank(items, found, policy, allow)})
    kinds = {}
    for item in items:
        kinds[item['source']['kind']] = kinds.get(item['source']['kind'], 0) + 1
    level = policy['toggles']['allowFormidableSources']['formidableLevel']
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'policyVersion': policy['policyVersion'],
        'builds': {'source': builds_source, 'digest': builds_digest,
                   'applied': len(records)//2, 'skipped': skipped},
        'toggles': policy['toggles'],
        'model': {k: policy[k] for k in ('tiers', 'effects', 'derived', 'armour', 'weapons',
                                         'archetypes', 'criticalAttributes', 'drawbacks',
                                         'picksPerSlot')},
        'items': {item['key']: item for item in items},
        'derivation': {
            'method': 'constant-effect items ranked per build and slot by the build\'s own '
                      'skills, attributes and archetype',
            'candidates': len(items), 'bySource': kinds,
            'formidableOnly': sum(1 for i in items if not i['source']['questGrants']
                                  and (i['source']['easiestLevel'] or 0) > level),
            'records': len(records)},
        'coverage': 'Items that already carry a constant effect, ranked by what each build '
                    'values. Drawbacks are never subtracted: the ones that ruin an item for a '
                    'build remove it, and the ones worth knowing ride along as warnings. '
                    'Enchantment capacity and custom enchanting are not modelled. Quests are '
                    'assumed done, so a scripted grant counts as a source. Two-handed weapons '
                    'and shields are ranked independently; the site must not pair them.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.best-in-slot-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


# Where a builds digest is published, in the order a change to the builds travels.
STAGES = ('catalog', 'bundle', 'site')


def catalog_digests(directory, profiles):
    """The builds digest in the file bundling would take next, per profile."""
    found = {}
    for profile in profiles:
        path = newest(directory, profile)
        found[profile] = None if path is None else (
            json.loads(path.read_text(encoding='utf-8')).get('builds', {}).get('digest'))
    return found


def published_digests(directory):
    """The builds digest per profile in the bundle a current.json points at, or None when
    nothing is published there. A profile that inherits BestInSlot from its base reports
    the base's digest, because that is what the site loads for it."""
    pointer = Path(directory)/'current.json'
    if not pointer.is_file():
        return None
    current = json.loads(pointer.read_text(encoding='utf-8'))
    if not current.get('manifest'):
        raise ExportError(f'{pointer} names no manifest')
    manifest = Path(directory)/current['manifest']
    profiles = {p['id']: p for p in json.loads(manifest.read_text(encoding='utf-8'))['profiles']}
    found = {}
    for profile_id, profile in profiles.items():
        entry, seen = None, set()
        while profile is not None and profile['id'] not in seen:
            seen.add(profile['id'])
            entry = profile['files'].get('BestInSlot')
            if entry is not None:
                break
            profile = profiles.get(profile.get('base'))
        found[profile_id] = None if entry is None else (
            json.loads((manifest.parent/entry['path']).read_text(encoding='utf-8'))
            .get('builds', {}).get('digest'))
    return found


def stale_from(digest, found):
    """The first stage still carrying other builds than the site's, or None when every
    stage matches. Nothing published, or a profile without a digest, counts as stale:
    nothing there reflects the current builds."""
    for stage in STAGES:
        digests = found.get(stage)
        if not digests or any(value != digest for value in digests.values()):
            return stage
    return None


def rerun(stage, site):
    """The commands that carry the current builds on from `stage`, in order."""
    commands = ['python build_best_in_slot_catalog.py', 'python build_app_bundle.py',
                f'node {Path(site)/"scripts/stage-game-data.mjs"}']
    return commands[STAGES.index(stage):]


def check(digest, source, found, site):
    """Say how far the site's current builds have travelled; 0 when all the way."""
    print(f'Builds in {source}: {digest[:12]}')
    for stage in STAGES:
        digests = found.get(stage)
        if not digests:
            print(f'  {stage:8} nothing published')
            continue
        print(f'  {stage:8} ' + '  '.join(
            f'{profile} {"ok" if value == digest else "stale" if value else "missing"}'
            for profile, value in digests.items()))
    stage = stale_from(digest, found)
    if stage is None:
        print('Best-in-slot matches the current builds everywhere.')
        return 0
    print(f'Stale from the {stage} onward. To bring it up to date, run in order:')
    for command in rerun(stage, site):
        print('  ' + command)
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--policy', type=Path)
    parser.add_argument('--builds', type=Path, help='A JSON file of builds instead of the site')
    parser.add_argument('--site', type=Path, help='The site repository, for its premade builds')
    parser.add_argument('--catalogs', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true',
                        help="Build nothing: report whether the site's current builds have "
                             'reached the catalog, the bundle and the site, and what to rerun')
    args = parser.parse_args(argv)
    try:
        _, source, root = load_config(ROOT/'foundation_config.json')
        site = args.site or source.get('siteRepository') or 'A:/Claude/morrowind-tools'
        builds, builds_source, digest = load_builds(site, args.builds)
        if args.check:
            found = {'catalog': catalog_digests(args.output or root/'best-in-slot',
                                                args.profile or ['vanilla', 'tr', 'tr_arce']),
                     'bundle': published_digests(root/'app-bundle'),
                     'site': published_digests(Path(site)/'public/game-data')}
            return check(digest, builds_source, found, site)
        policy = load_late_policy(args.policy or ROOT/'policy/late-game.json')
        early = load_policy(ROOT/'policy/early-game.json')
        release = args.catalogs
        if release is None:
            pointer = root/'catalogs/current.json'
            if not pointer.is_file():
                raise ExportError('No catalog release found; pass --catalogs')
            release = root/'catalogs'/json.loads(pointer.read_text(encoding='utf-8'))['releaseId']
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        paths = [root/'acquisition/acquisition.sqlite', root/'world/world.sqlite',
                 root/'script-evidence/script-evidence.sqlite', root/'services/services.sqlite']
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(
                    sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                db.execute('PRAGMA cache_size=-16384')
                dbs.append(db)
            snapshot = metadata(dbs[1]).get('snapshotId')
            # Coverage is judged across every profile, even when building one: a single
            # vanilla build would otherwise call every Tamriel Rebuilt effect imaginary.
            # Listing candidates is cheap; only the source queries below are not.
            prepared, used = {}, {}
            for profile in ('vanilla', 'tr', 'tr_arce'):
                ref = reference(release, profile)
                items = candidates(release, profile, ref['settings'])
                used[profile] = {e['name'] for i in items for e in i['effects']}
                if profile in profiles:
                    prepared[profile] = (ref, items)
            check_coverage(policy, used)
            for profile, (_, items) in prepared.items():
                sources(dbs, profile, items, early, release)
            written = []
            for profile, (ref, items) in prepared.items():
                payload = assemble(profile, builds, items, ref, policy, snapshot,
                                   builds_source, digest)
                destination, size = publish(payload, args.output or root/'best-in-slot', profile)
                counts = payload['derivation']
                print(f'{profile}: {payload["builds"]["applied"]} builds, {counts["candidates"]} '
                      f'candidates {counts["bySource"]}, {counts["formidableOnly"]} formidable-only, '
                      f'{len(payload["builds"]["skipped"])} builds skipped, {size/1024:.0f} KB',
                      flush=True)
                written.append(destination)
        print('Best-in-slot catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f'Best-in-slot catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
