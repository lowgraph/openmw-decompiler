"""Build the merchants and what barter needs to price against them.

A merchant's offer is not in the plugin files as a number. It is computed at runtime
from the haggling formula, which reads the merchant's Mercantile, Personality, Luck,
disposition and fatigue, and the player's. This publishes the merchant side of that,
with the formula's own literals authored beside it.

20% of traders are auto-calculated: the record stores no skills or attributes at all,
because the engine derives them from class and level when the game loads. Those are
derived here by rerunning the engine's own routines -- see autocalc.py -- and
statsSource says whether a merchant's stats were read or worked out.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

import autocalc
from build_acquisition_index import metadata
from export_items import ExportError
from extract_foundation import ROOT, label_carries, load_config

VERSION = '1.0.0'
CLASS = re.compile(rb'CNAM.{4}([^\x00]*)\x00', re.S)
RACE = re.compile(rb'RNAM.{4}([^\x00]*)\x00', re.S)

# The OpenMW release both transcriptions below were checked against, line by line, at
# tag openmw-0.51.0 (commit f4bec41444): these literals against getBarterOffer, and
# autocalc.py against autoCalculateAttributes and autoCalculateSkills, including
# npc.cpp's own round_ieee_754, which rounds ties to even as Python's round() does.
# They are code, not data, so no rebuild can update them; check_transcription stops the
# build when the extraction names another release.
TRANSCRIBED_FROM = '0.51.0'

# MechanicsManager::getBarterOffer, apps/openmw/mwmechanics/mechanicsmanagerimp.cpp.
# Transcribed from the engine source, not from memory: the weights below are not the
# ones a reading of the wiki suggests, and creature merchants do not haggle at all.
# These are engine literals rather than game settings, so they are authored and marked.
BARTER_FORMULA = {
    'source': 'authored',
    'transcribedFrom': f'OpenMW {TRANSCRIBED_FROM}',
    'note': "OpenMW's getBarterOffer. Each side contributes capped Mercantile, Luck and "
            'Personality; disposition moves only the player side. The offer is a '
            'percentage of base value, truncated, then floored at 1 gold.',
    'mercantileCap': 100.0,
    'luckWeight': 0.1, 'luckCap': 10.0,
    'personalityWeight': 0.2, 'personalityCap': 10.0,
    'dispositionBaseline': 50,
    'buyBase': 100.0,
    'sellBase': 50.0,
    'termWeight': 0.5,
    'percentScale': 0.01,
    'minimumPrice': 1,
    # Two cases never reach the formula at all.
    'creaturesDoNotHaggle': True,
    'zeroBasePriceStaysZero': True,
    # getFatigueTerm: fFatigueBase - fFatigueMult * (1 - current/maximum fatigue).
    'gameSettings': ['fFatigueBase', 'fFatigueMult', 'fBargainOfferBase',
                     'fBargainOfferMulti', 'fDispositionMod', 'iBarterSuccessDisposition',
                     'iBarterFailDisposition', 'fBarterGoldResetDelay'],
}


def service_flags(services):
    """Decode the service bitfield once here rather than in every consumer."""
    return {bit: (code, kind) for bit, code, kind in services.execute(
        'SELECT bit, code, kind FROM service_flags')}


def actor_records(game, profile):
    """Class and race per actor, which the provider table does not carry."""
    found = {}
    for key, payload in game.execute(
            'SELECT rv.record_key, rv.payload FROM resolved_records rr '
            'JOIN record_versions rv ON rv.id = rr.winner_id '
            "WHERE rr.profile_id = ? AND rv.record_type IN ('NPC_', 'CREA')", (profile,)):
        klass, race = CLASS.search(payload), RACE.search(payload)
        found[key] = {
            'class': klass.group(1).decode('cp1252', 'replace') if klass else None,
            'race': race.group(1).decode('cp1252', 'replace') if race else None}
    return found


def barter_stats(stats):
    """Mercantile, Personality and Luck, or nulls when the engine works them out.

    An auto-calculated NPC stores no skills and no attributes. That is not a gap in the
    extraction: there is nothing in the record to extract.
    """
    skills = stats.get('skills') if isinstance(stats.get('skills'), dict) else {}
    attributes = stats.get('attributes') if isinstance(stats.get('attributes'), dict) else {}
    return {'mercantile': skills.get('mercantile'),
            'personality': attributes.get('personality'),
            'luck': attributes.get('luck')}


def merchant(actor, name, record_type, services_raw, stats, cells, flags, records,
             reference=None):
    # The decoded service names are carried once in serviceFlags, not per record:
    # eleven strings on 2,575 merchants cost more than everything else together.
    trades = any(kind == 'trade' for bit, (_, kind) in flags.items() if services_raw & bit)
    barter = barter_stats(stats)
    identity = records.get(actor, {})
    autocalc_flag = bool(stats.get('autocalcFlag'))
    # getBarterOffer returns basePrice unchanged for a creature, so a creature merchant
    # is exactly priceable without any stats at all: its price is the base value.
    haggles = record_type != 'CREA'
    stored = None not in barter.values()
    source = 'record' if stored else None
    if not stored and reference is not None:
        # Nothing was stored because the engine works it out. Work it out the same way.
        derived = autocalc.derive(reference, identity.get('race'), identity.get('class'),
                                  stats.get('level'), bool(stats.get('female')))
        if derived and None not in derived.values():
            barter, source = derived, 'derived'
    return {
        'key': actor, 'name': name, 'recordType': record_type,
        'cells': sorted(cells),
        'trades': trades, 'servicesRaw': services_raw,
        'gold': stats.get('gold'), 'disposition': stats.get('disposition'),
        'level': stats.get('level'), 'fatigue': stats.get('fatigue'),
        # Null only when the record stored nothing and the derivation could not run.
        'mercantile': barter['mercantile'],
        'personality': barter['personality'],
        'luck': barter['luck'],
        # Where those three came from: the record, or OpenMW's own autocalc rerun here.
        'statsSource': source,
        'autocalc': autocalc_flag, 'haggles': haggles,
        'priceable': not haggles or source is not None,
        'class': identity.get('class'), 'race': identity.get('race'),
        'female': bool(stats.get('female'))}


def build(services, game, profile, reference=None):
    flags = service_flags(services)
    records = actor_records(game, profile)
    rows = services.execute(
        'SELECT pp.actor_key, pr.name, pr.record_type, pr.services_raw, pr.stats_json, '
        ' pl.cell_key '
        'FROM profile_providers pp '
        'JOIN providers pr ON pr.version_id = pp.version_id '
        'LEFT JOIN provider_locations pl ON pl.provider_version_id = pp.version_id '
        ' AND pl.profile_id = pp.profile_id '
        'WHERE pp.profile_id = ? AND pr.services_raw > 0', (profile,)).fetchall()
    collected, cells = {}, {}
    for actor, name, record_type, services_raw, stats_json, cell in rows:
        cells.setdefault(actor, set())
        if cell:
            cells[actor].add(cell)
        collected[actor] = (name, record_type, services_raw, json.loads(stats_json or '{}'))
    return [merchant(actor, *collected[actor], cells[actor], flags, records, reference)
            for actor in sorted(collected)]


def assemble(services, game, profile, snapshot, reference=None):
    records = build(services, game, profile, reference)
    traders = [r for r in records if r['trades']]
    priceable = [r for r in traders if r['priceable']]
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'barterFormula': BARTER_FORMULA,
        'serviceFlags': [{'bit': bit, 'code': code, 'kind': kind}
                         for bit, (code, kind) in sorted(service_flags(services).items())],
        'derivation': {
            'method': 'service flags and stored actor stats; the offer itself is computed '
                      'at runtime and is not in any record',
            'providers': len(records), 'traders': len(traders),
            'priceable': len(priceable),
            'statsFromRecord': sum(1 for r in traders if r['statsSource'] == 'record'),
            'statsDerived': sum(1 for r in traders if r['statsSource'] == 'derived'),
            'statsUnknown': sum(1 for r in traders if r['statsSource'] is None and r['haggles']),
            'autocalc': sum(1 for r in traders if r['autocalc']),
            'creatures': sum(1 for r in traders if not r['haggles']),
            'withoutGold': sum(1 for r in records if r['gold'] is None)},
        'coverage': 'The merchant side of the haggling formula, plus which services each '
                    'provider sells and how much gold they carry. Barter stats are read '
                    'from the record where it stores them. Where it does not -- an '
                    'auto-calculated actor stores no skills or attributes at all -- they '
                    'are derived by rerunning the engine\'s own autoCalculateAttributes and '
                    'autoCalculateSkills, and statsSource says which of the two happened. '
                    'Null on all three means neither worked, never that the value is '
                    'zero. A '
                    'creature merchant never haggles -- the engine returns the base '
                    'price unchanged -- so it is priceable with no stats at all. Nothing '
                    'here evaluates disposition changes, bargaining attempts, restocking '
                    'or dialogue conditions.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.merchants-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def check_transcription(versions):
    """Refuse to price with formulas copied from a different engine release.

    `versions` maps each world to the label the extraction recorded; the vanilla one
    names the OpenMW release, and extraction has already checked it against the binary.
    """
    labelled = versions.get('vanilla', '')
    if not label_carries(labelled, TRANSCRIBED_FROM):
        raise ExportError(
            f'The barter formula and autocalc were transcribed from OpenMW '
            f'{TRANSCRIBED_FROM}, but this extraction is for {labelled!r}.\n  Compare '
            'MechanicsManager::getBarterOffer (apps/openmw/mwmechanics/mechanicsmanagerimp.cpp)'
            ' and autoCalculateAttributes and autoCalculateSkills (apps/openmw/mwclass/npc.cpp)'
            ' between the two releases. If they are unchanged, set TRANSCRIBED_FROM in '
            'build_merchant_catalog.py to the new version; if not, transcribe them again.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--foundation-database', type=Path)
    parser.add_argument('--catalogs', type=Path, help='Catalog release, for autocalc inputs')
    parser.add_argument('--no-autocalc', action='store_true',
                        help='Leave auto-calculated merchants unpriceable')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        paths = (args.services_database or root/'services/services.sqlite',
                 args.foundation_database or root/'game-data.sqlite')
        catalogs = args.catalogs
        if catalogs is None and not args.no_autocalc:
            pointer = root/'catalogs/current.json'
            if not pointer.is_file():
                raise ExportError('No catalog release found; pass --catalogs or --no-autocalc')
            catalogs = root/'catalogs'/json.loads(pointer.read_text(encoding='utf-8'))['releaseId']
        written = []
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(
                    sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                dbs.append(db)
            services, game = dbs
            check_transcription({p['world']: p['version'] for p in metadata(game)['profiles']})
            snapshot = metadata(services).get('snapshotId')
            for profile in profiles:
                reference = None if args.no_autocalc else autocalc.reference(catalogs, profile)
                payload = assemble(services, game, profile, snapshot, reference)
                destination, size = publish(payload, args.output or root/'merchants', profile)
                counts = payload['derivation']
                print(f'{profile}: {counts["providers"]} providers, {counts["traders"]} trade, '
                      f'{counts["priceable"]} priceable ({counts["statsFromRecord"]} from the '
                      f'record, {counts["statsDerived"]} derived, {counts["statsUnknown"]} '
                      f'still unknown), {size/1024:.0f} KB', flush=True)
                written.append(destination)
        print('Merchant catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Merchant catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
