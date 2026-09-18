"""Derive the engine's per-effect rules from how the game's own content uses them.

Morrowind's plugin files carry only two of a magic effect's flags: whether the
Construction Set allows spellmaking and enchanting with it. Targeting, whether an
effect has a magnitude, and whether it has a duration all live in the engine, not in
the data. A spell's cost formula branches on the last two, so a calculator that
guesses them prices dozens of effects wrongly.

Bethesda authored every vanilla spell, enchantment and potion against the real engine,
so their usage is evidence. An effect with no magnitude is written with magnitude
exactly one every single time; an effect with no duration is written with duration
exactly one. An effect that uses the field varies it. One counter-example anywhere
refutes the flag, so observations are pooled across every profile in the release —
Tamriel Rebuilt's content is what shows Restore Skill to have a duration after all
1,000 vanilla spells suggested otherwise.

Nothing here is asserted without its evidence, and an effect the content never
exercises enough is reported unknown rather than guessed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'
SOURCES = ('Spells', 'Enchantments', 'Potions')
# Below this many uses in the best-covered profile, the content has not shown enough.
MINIMUM_USES = 3
# The sentinel an unused magnitude or duration field is written with.
UNUSED = 1
# Engine constants for the spell cost formula. Not game settings, not derivable from
# content: they are literals in the engine and are authored here, marked as such.
COST_FORMULA = {
    'source': 'authored',
    'note': 'Per effect: 0.5*(magMin+magMax) * 0.1*baseCost * (1+duration), plus '
            '0.05*max(1,areaFeet)*baseCost, times 1.5 when the range is target. '
            'A noMagnitude effect counts as magnitude 1 and a noDuration effect as '
            'duration 0, which is why those two flags decide the price.',
    'magnitudeAverage': 0.5, 'baseCostMultiplier': 0.1, 'areaMultiplier': 0.05,
    'targetRangeMultiplier': 1.5, 'unusedMagnitude': 1, 'unusedDuration': 0,
    'gameSettings': ['fSpellMakingValueMult', 'fSpellValueMult', 'fEnchantmentValueMult',
                     'fEnchantmentConstantDurationMult', 'fEnchantmentConstantChanceMult',
                     'fEnchantmentChanceMult', 'fEnchantmentMult', 'fPotionStrengthMult',
                     'fPotionT1MagMult', 'fPotionT1DurMult', 'iAlchemyMod'],
}


def catalog(release, profile, name):
    path = Path(release)/profile/(name+'.json')
    if not path.is_file():
        raise ExportError(f'Catalog missing from release: {path}')
    return json.loads(path.read_text(encoding='utf-8'))['records']


def observe(release, profiles):
    """Pool value sets across profiles; one counter-example anywhere refutes a flag."""
    pooled = {}
    for profile in profiles:
        for name in SOURCES:
            for record in catalog(release, profile, name):
                for effect in record.get('effects', []):
                    seen = pooled.setdefault(effect['effectId'], {
                        'magnitudes': set(), 'durations': set(), 'ranges': set(),
                        'skill': 0, 'attribute': 0, 'uses': Counter()})
                    seen['uses'][profile] += 1
                    seen['magnitudes'].add((effect['magnitude']['min'], effect['magnitude']['max']))
                    seen['durations'].add(effect['durationSeconds'])
                    if name != 'Potions':
                        # A potion is always drunk by its holder, so it proves no range.
                        seen['ranges'].add(effect['range'])
                    if effect.get('skill') is not None:
                        seen['skill'] += 1
                    if effect.get('attribute') is not None:
                        seen['attribute'] += 1
    return pooled


def fixed_at(values, sentinel):
    return len(values) == 1 and next(iter(values)) == sentinel


def rule(effect, seen):
    """One effect's rules: extracted, then derived, each with the evidence behind it."""
    row = {'key': str(effect['effectId']), 'effectId': effect['effectId'], 'name': effect['name'],
           'school': effect['school'], 'baseCost': effect['baseCost'],
           'allowSpellmaking': effect['allowSpellmaking'],
           'allowEnchanting': effect['allowEnchanting']}
    best = max(seen['uses'].values(), default=0) if seen else 0
    enough = best >= MINIMUM_USES
    row.update(
        targetsSkill=bool(seen and seen['skill']),
        targetsAttribute=bool(seen and seen['attribute']),
        noMagnitude=fixed_at(seen['magnitudes'], (UNUSED, UNUSED)) if enough else None,
        noDuration=fixed_at(seen['durations'], UNUSED) if enough else None,
        rangesObserved=sorted(seen['ranges']) if seen else [],
        evidence={'uses': sum(seen['uses'].values()) if seen else 0,
                  'bestProfileUses': best, 'byProfile': dict(seen['uses']) if seen else {},
                  'distinctMagnitudes': len(seen['magnitudes']) if seen else 0,
                  'distinctDurations': len(seen['durations']) if seen else 0,
                  'sufficient': enough})
    return row


def build(release, output, profiles):
    pooled = observe(release, profiles)
    published = []
    for profile in profiles:
        effects = catalog(release, profile, 'MagicEffects')
        records = [rule(effect, pooled.get(effect['effectId'])) for effect in
                   sorted(effects, key=lambda e: e['effectId'])]
        derived = sum(1 for r in records if r['noMagnitude'] is not None)
        payload = {
            'schemaVersion': VERSION, 'profile': profile,
            'snapshotId': json.loads((Path(release)/'manifest.json').read_text(encoding='utf-8'))['snapshotId'],
            'derivation': {'method': 'pooled usage across every profile in the release',
                           'profilesPooled': sorted(profiles), 'sources': list(SOURCES),
                           'minimumUses': MINIMUM_USES, 'effects': len(records),
                           'decided': derived, 'unknown': len(records)-derived},
            'costFormula': COST_FORMULA,
            'coverage': 'Targeting, magnitude and duration rules are inferred from how the '
                        'game\'s own content uses each effect, not read from the plugin files, '
                        'which do not carry them. rangesObserved proves a range is allowed; it '
                        'does not prove an unobserved one is forbidden. Effects the content '
                        'barely uses report null rather than a guess.',
            'builtAtUnix': time.time(), 'records': records}
        published.append((profile, payload))

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    written = []
    for profile, payload in published:
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode('utf-8')
        identifier = hashlib.sha256(body).hexdigest()[:24]
        destination = output/f'{profile}-{identifier}.json'
        handle, staging = tempfile.mkstemp(prefix='.rules-', dir=output)
        os.close(handle)
        Path(staging).write_bytes(body)
        os.replace(staging, destination)
        written.append(destination)
        decided = payload['derivation']['decided']
        print(f"{profile}: {payload['derivation']['effects']} effects, {decided} decided, "
              f"{payload['derivation']['unknown']} unknown, {len(body)/1024:.0f} KB", flush=True)
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogs', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        release = args.catalogs
        if release is None:
            pointer = root/'catalogs/current.json'
            if not pointer.is_file():
                raise ExportError('No catalog release found; pass --catalogs')
            release = root/'catalogs'/json.loads(pointer.read_text(encoding='utf-8'))['releaseId']
        elif (release/'current.json').is_file():
            release = release/json.loads((release/'current.json').read_text(encoding='utf-8'))['releaseId']
        manifest = json.loads((release/'manifest.json').read_text(encoding='utf-8'))
        available = [p['id'] for p in manifest['profiles']]
        profiles = args.profile or available
        if set(profiles) - set(available):
            raise ExportError('Unknown profile for this release')
        written = build(release, args.output or root/'rules', profiles)
        print('Rules library complete:\n  ' + '\n  '.join(str(p) for p in written), flush=True)
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError) as exc:
        print(f'Rules build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
