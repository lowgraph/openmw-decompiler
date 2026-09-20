"""Build the merchants and what barter needs to price against them.

A merchant's offer is not in the plugin files as a number. It is computed at runtime
from the haggling formula, which reads the merchant's Mercantile, Personality, Luck,
disposition and fatigue, and the player's. This publishes the merchant side of that,
with the formula's own literals authored beside it.

20% of traders are auto-calculated: the record stores no skills or attributes at all,
because the engine derives them from class and level when the game loads. Those
publish null and say so. Everything needed to derive them ships in the Races and
Classes catalogs, but deriving it here would be an unverifiable reimplementation of
engine code, so it is left to a caller who can check its answers.
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

from build_acquisition_index import metadata
from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'
CLASS = re.compile(rb'CNAM.{4}([^\x00]*)\x00', re.S)
RACE = re.compile(rb'RNAM.{4}([^\x00]*)\x00', re.S)

# MechanicsManager::getBarterOffer, apps/openmw/mwmechanics/mechanicsmanagerimp.cpp.
# Transcribed from the engine source, not from memory: the weights below are not the
# ones a reading of the wiki suggests, and creature merchants do not haggle at all.
# These are engine literals rather than game settings, so they are authored and marked.
BARTER_FORMULA = {
    'source': 'authored',
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


def merchant(actor, name, record_type, services_raw, stats, cells, flags, records):
    # The decoded service names are carried once in serviceFlags, not per record:
    # eleven strings on 2,575 merchants cost more than everything else together.
    trades = any(kind == 'trade' for bit, (_, kind) in flags.items() if services_raw & bit)
    barter = barter_stats(stats)
    identity = records.get(actor, {})
    autocalc = bool(stats.get('autocalcFlag'))
    # getBarterOffer returns basePrice unchanged for a creature, so a creature merchant
    # is exactly priceable without any stats at all: its price is the base value.
    haggles = record_type != 'CREA'
    return {
        'key': actor, 'name': name, 'recordType': record_type,
        'cells': sorted(cells),
        'trades': trades, 'servicesRaw': services_raw,
        'gold': stats.get('gold'), 'disposition': stats.get('disposition'),
        'level': stats.get('level'), 'fatigue': stats.get('fatigue'),
        # Null here means the engine decides at load time, never that it is zero.
        'mercantile': barter['mercantile'],
        'personality': barter['personality'],
        'luck': barter['luck'],
        'autocalc': autocalc, 'haggles': haggles,
        'priceable': not haggles or (not autocalc and None not in barter.values()),
        'class': identity.get('class'), 'race': identity.get('race'),
        'female': bool(stats.get('female'))}


def build(services, game, profile):
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
    return [merchant(actor, *collected[actor], cells[actor], flags, records)
            for actor in sorted(collected)]


def assemble(services, game, profile, snapshot):
    records = build(services, game, profile)
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
            'autocalc': sum(1 for r in traders if r['autocalc']),
            'creatures': sum(1 for r in traders if not r['haggles']),
            'withoutGold': sum(1 for r in records if r['gold'] is None)},
        'coverage': 'The merchant side of the haggling formula, plus which services each '
                    'provider sells and how much gold they carry. Barter stats are null '
                    'when the actor is auto-calculated: the record stores none, because '
                    'the engine derives them from class and level at load. Null means the '
                    'engine decides, never zero, and priceable false marks it. A '
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--services-database', type=Path)
    parser.add_argument('--foundation-database', type=Path)
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        paths = (args.services_database or root/'services/services.sqlite',
                 args.foundation_database or root/'game-data.sqlite')
        written = []
        with ExitStack() as stack:
            dbs = []
            for path in paths:
                db = stack.enter_context(closing(
                    sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)))
                db.execute('PRAGMA temp_store=MEMORY')
                dbs.append(db)
            services, game = dbs
            snapshot = metadata(services).get('snapshotId')
            for profile in profiles:
                payload = assemble(services, game, profile, snapshot)
                destination, size = publish(payload, args.output or root/'merchants', profile)
                counts = payload['derivation']
                share = 100*counts['autocalc']/counts['traders'] if counts['traders'] else 0
                print(f'{profile}: {counts["providers"]} providers, {counts["traders"]} trade, '
                      f'{counts["priceable"]} priceable, {counts["autocalc"]} auto-calculated '
                      f'({share:.0f}% of traders), {size/1024:.0f} KB', flush=True)
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
