"""Build the journal quests as a shipped catalog.

A quest is a journal topic: its title, the stages it can reach, and which of those
finish it. That is what journal completion per character needs to track against.

Entry prose is deliberately absent. It is 691 KB gzipped for Tamriel Rebuilt against a
988 KB bundle, and completion needs stage numbers rather than the words. Books were
split the same way, into their own BookText catalog.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from build_acquisition_index import metadata
from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'
# How much of the first entry to keep when a quest never names itself. Enough to
# recognise it in a list, not enough to be a substitute for the journal.
FALLBACK_LENGTH = 120


def load_titles(path):
    titles = json.loads(Path(path).read_text(encoding='utf-8'))
    if titles.get('schemaVersion') != VERSION:
        raise ExportError(f'Unsupported journal title schema {titles.get("schemaVersion")!r}')
    if not isinstance(titles.get('titles'), dict):
        raise ExportError('Journal titles file has no titles object')
    if not isinstance(titles.get('excludedTopics'), list):
        raise ExportError('Journal titles excludedTopics must be a list, possibly empty')
    for key, value in titles['titles'].items():
        if not isinstance(value, str) or not value.strip():
            raise ExportError(f'Authored title for {key!r} is empty')
    return titles


def entries(journal, profile):
    """Every journal entry this profile can see, with the stage it sets."""
    return journal.execute(
        'SELECT pr.topic_key, r.value_raw, r.quest_status, r.response_text '
        'FROM profile_responses pr '
        'JOIN responses r ON r.topic_key = pr.topic_key AND r.info_key = pr.info_key '
        ' AND r.version_id = pr.version_id '
        'JOIN profile_topics pt ON pt.topic_key = pr.topic_key '
        ' AND pt.profile_id = pr.profile_id '
        'JOIN topics t ON t.topic_key = pt.topic_key AND t.version_id = pt.version_id '
        "WHERE pr.profile_id = ? AND t.type_name = 'journal' "
        'ORDER BY pr.topic_key, r.value_raw', (profile,)).fetchall()


def excerpt(text):
    flattened = ' '.join((text or '').split())
    if len(flattened) <= FALLBACK_LENGTH:
        return flattened or None
    return flattened[:FALLBACK_LENGTH].rstrip() + '…'


def quests(journal, profile, titles):
    """One record per journal topic, named by the game where the game names it."""
    excluded = {key.casefold() for key in titles['excludedTopics']}
    authored = {key.casefold(): value for key, value in titles['titles'].items()}
    collected = {}
    for topic, stage, status, text in entries(journal, profile):
        if topic.casefold() in excluded:
            continue
        record = collected.setdefault(topic, {
            'key': topic, 'name': None, 'nameSource': None, 'trackable': False,
            'stages': set(), 'finishesAt': set(), 'restartsAt': set(),
            'firstEntry': None, 'firstText': None, 'entries': 0})
        record['entries'] += 1
        if status == 'name':
            # The topic names itself; this entry is the title, not a stage.
            record['name'], record['nameSource'] = text, 'record'
            continue
        if record['firstText'] is None:
            record['firstText'] = text
        record['stages'].add(stage)
        if status == 'finished':
            record['finishesAt'].add(stage)
            record['trackable'] = True
        elif status == 'restart':
            record['restartsAt'].add(stage)
    used = set()
    for topic, record in collected.items():
        if record['name'] is None and topic.casefold() in authored:
            record['name'], record['nameSource'] = authored[topic.casefold()], 'authored'
            used.add(topic.casefold())
        # Bare stage numbers rather than an object each: 16,743 of them in Tamriel
        # Rebuilt, and a flag pair per stage cost more than every other field together.
        for field in ('stages', 'finishesAt', 'restartsAt'):
            record[field] = sorted(record[field], key=lambda s: (s is None, s))
        # Only a topic with no title needs something to show in its place; carrying an
        # excerpt for the 2,455 that name themselves quadrupled the catalog.
        if record['name'] is None:
            record['firstEntry'] = excerpt(record['firstText'])
        del record['firstText']
    return collected, used


def check_authored(titles, used_by_profile):
    """An authored title that names nothing is a stale entry; say so rather than keep it."""
    authored = {key.casefold() for key in titles['titles']}
    unused = sorted(authored - set().union(*used_by_profile.values()) if used_by_profile
                    else authored)
    if unused:
        raise ExportError(
            f'{len(unused)} authored journal title(s) match no untitled quest in any '
            f'profile: ' + ', '.join(unused[:6])
            + '\n  Either the quest now names itself, or the key is wrong. Remove the '
              'entry from policy/journal-titles.json, or correct it.')


def assemble(journal, profile, titles, snapshot):
    collected, _ = quests(journal, profile, titles)
    records = [collected[key] for key in sorted(collected)]
    trackable = [r for r in records if r['trackable']]
    unnamed = [r for r in records if r['name'] is None]
    return {
        'schemaVersion': VERSION, 'profile': profile, 'snapshotId': snapshot,
        'policyVersion': titles['policyVersion'],
        'derivation': {
            'method': "journal topics and the stages their entries set",
            'topics': len(records), 'trackable': len(trackable),
            'namedByRecord': sum(1 for r in records if r['nameSource'] == 'record'),
            'namedByAuthor': sum(1 for r in records if r['nameSource'] == 'authored'),
            'unnamed': len(unnamed),
            'unnamedButTrackable': sorted(r['key'] for r in unnamed if r['trackable']),
            'stages': sum(len(r['stages']) for r in records)},
        'coverage': 'Titles and stage numbers only; the entry prose is not here, because '
                    'tracking completion needs the numbers and the text would cost more '
                    'than the rest of the bundle. A topic with trackable false reaches no '
                    'finishing stage: it is a journal note rather than a quest, which is '
                    'why most untitled topics need no title. An unnamed topic publishes '
                    'name null and firstEntry, never an invented title.',
        'builtAtUnix': time.time(), 'records': records}


def publish(payload, output, profile):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8')
    identifier = hashlib.sha256(body).hexdigest()[:24]
    destination = output/f'{profile}-{identifier}.json'
    handle, staging = tempfile.mkstemp(prefix='.quests-', dir=output)
    os.close(handle)
    Path(staging).write_bytes(body)
    os.replace(staging, destination)
    return destination, len(body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--titles', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--journal-database', type=Path)
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        titles = load_titles(args.titles or ROOT/'policy/journal-titles.json')
        profiles = args.profile or ['vanilla', 'tr', 'tr_arce']
        path = args.journal_database or root/'journal/journal.sqlite'
        written, used = [], {}
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as journal:
            journal.execute('PRAGMA temp_store=MEMORY')
            snapshot = metadata(journal).get('snapshotId')
            payloads = {}
            for profile in profiles:
                payloads[profile] = assemble(journal, profile, titles, snapshot)
                used[profile] = quests(journal, profile, titles)[1]
            check_authored(titles, used)
            for profile, payload in payloads.items():
                destination, size = publish(payload, args.output or root/'quests', profile)
                counts = payload['derivation']
                print(f'{profile}: {counts["topics"]} topics, {counts["trackable"]} trackable, '
                      f'{counts["namedByRecord"]} named by the game, '
                      f'{counts["namedByAuthor"]} authored, {counts["unnamed"]} unnamed '
                      f'({len(counts["unnamedButTrackable"])} of them trackable), '
                      f'{size/1024:.0f} KB', flush=True)
                written.append(destination)
        print('Quest catalog complete:\n  ' + '\n  '.join(str(p) for p in written))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; nothing was published.')
        return 130
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f'Quest catalog build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
