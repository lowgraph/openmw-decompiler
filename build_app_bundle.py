"""Package a catalog release into the browser-facing bundle the site downloads."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from build_catalogs import BOOK_TEXT
from extract_foundation import ROOT, load_config
from export_items import ExportError

VERSION = '1.0.0'
SUPPORTED_CATALOGS = {'1.0.0', '1.1.0'}
# Book prose is the single largest catalog and no calculator reads it. It stays
# out of the eager bundle; --include-book-text publishes it as its own file.
DEFAULT_EXCLUDED = frozenset({BOOK_TEXT})
# Gear rows are built separately but ship as an ordinary catalog, keyed per row.
GEAR_ROWS = 'GearRows'
GEAR_ROW_FIELDS = ('policy', 'limits', 'categories', 'coverage')


def identity(record):
    """Records join on the canonical key; derived rows (Attributes) only have an id."""
    value = record.get('key', record.get('id'))
    if value is None:
        raise ExportError('Catalog record has neither key nor id')
    return value


def index_records(records, where):
    table = {}
    for record in records:
        name = identity(record)
        if name in table:
            raise ExportError(f'{where}: duplicate record key {name!r}')
        table[name] = record
    return table


def delta(base, target, where):
    """Changed/new records in full, plus keys the profile drops. Order is stable."""
    old = index_records(base, where)
    new = index_records(target, where)
    changed = [record for name, record in new.items() if old.get(name) != record]
    removed = sorted(name for name in old if name not in new)
    return changed, removed


def load_gear_rows(directory, profile, snapshot):
    """The newest rows file for this profile, pinned to the catalogs' own snapshot."""
    found = sorted(Path(directory).glob(profile+'-*.json'), key=lambda f: f.stat().st_mtime)
    if not found:
        return None
    path = found[-1]
    payload = json.loads(path.read_text(encoding='utf-8'))
    if payload.get('snapshotId') != snapshot:
        raise ExportError(f'{path.name} was built from a different snapshot than the catalogs; '
                          'rebuild gear rows before bundling')
    if not isinstance(payload.get('rows'), list) or not payload['rows']:
        raise ExportError(f'{path.name} has no rows')
    # The loader joins records on key, so enforce that here rather than in the browser.
    keys = [row.get('key') for row in payload['rows']]
    if not all(isinstance(key, str) and key for key in keys):
        raise ExportError(f'{path.name} has rows without a key; rebuild with build_gear_rows.py')
    if len(set(keys)) != len(keys):
        raise ExportError(f'{path.name} has duplicate row keys')
    return payload | {'sourceFile': path.name}


def read_catalog(release, profile_id, name):
    path = release/profile_id/(name+'.json')
    if not path.is_file():
        raise ExportError(f'Catalog missing from release: {path}')
    envelope = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(envelope.get('records'), list):
        raise ExportError(f'Catalog has no records array: {path}')
    return envelope


def pick_base(profile, available):
    """ARCE is a toggle over its own world, not a separate body of game data."""
    if not profile['arce']:
        return None
    for other in available:
        if (other['id'] != profile['id'] and not other['arce']
                and (other['world'], other['version']) == (profile['world'], profile['version'])):
            return other['id']
    return None


def write_payload(path, payload):
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    path.write_bytes(body)
    # The CDN negotiates its own encoding; the gzip size is recorded as the budget.
    return {'bytes': len(body), 'gzipBytes': len(gzip.compress(body, 9)),
            'sha256': hashlib.sha256(body).hexdigest()}


def load_release(source):
    """Accept either a release directory or the catalogs output holding current.json."""
    source = source.resolve()
    pointer = source/'current.json'
    if pointer.is_file():
        release = source/json.loads(pointer.read_text(encoding='utf-8'))['releaseId']
    else:
        release = source
    manifest = release/'manifest.json'
    if not manifest.is_file():
        raise ExportError(f'No catalog release found at {source}')
    return release, json.loads(manifest.read_text(encoding='utf-8'))


def build(source, output, profiles=None, include_book_text=False, gear_rows=None):
    release, catalogs = load_release(source)
    if catalogs.get('schemaVersion') not in SUPPORTED_CATALOGS:
        raise ExportError(f'Unsupported catalog schema {catalogs.get("schemaVersion")!r}')
    available = catalogs['profiles']
    by_id = {p['id']: p for p in available}
    selected = list(profiles or by_id)
    if len(set(selected)) != len(selected) or set(selected) - by_id.keys():
        raise ExportError('Unknown/duplicate selected profiles')
    names = [name for name in by_id[selected[0]]['counts']
             if include_book_text or name not in DEFAULT_EXCLUDED]
    for profile_id in selected:
        if set(by_id[profile_id]['counts']) != set(by_id[selected[0]]['counts']):
            raise ExportError(f'Profile {profile_id} has a different catalog set')
    if include_book_text and BOOK_TEXT not in names:
        raise ExportError(f'This catalog release has no {BOOK_TEXT} catalog; rebuild catalogs with schema 1.1.0')
    # All profiles or none: a catalog missing from one profile is a bundle the loader refuses.
    gear = {}
    if gear_rows is not None and Path(gear_rows).is_dir():
        found = {p: load_gear_rows(gear_rows, p, catalogs['snapshotId']) for p in selected}
        absent = sorted(p for p, rows in found.items() if rows is None)
        if absent and len(absent) != len(selected):
            raise ExportError('Gear rows found for some profiles but missing for '
                              + ', '.join(absent) + '; build the rest or pass --no-gear-rows')
        if not absent:
            gear = found
            names.append(GEAR_ROWS)

    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if release == output or release.is_relative_to(output):
        raise ExportError('Bundle output must not contain or replace the catalog release')
    lock = output/'build.lock'
    try:
        handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ExportError(f'Build lock exists: {lock}; check for another build before removing a stale lock') from exc
    os.close(handle)
    try:
        identifier = hashlib.sha256((catalogs['snapshotId'] + VERSION + catalogs['schemaVersion']
                                     + ','.join(sorted(selected)) + str(include_book_text)
                                     + ','.join(sorted(rows['sourceFile'] for rows in gear.values()))
                                     ).encode()).hexdigest()[:24]
        destination = output/identifier
        if destination.exists():
            raise ExportError(f'Bundle already exists: {destination}; use a different --output to rebuild')
        with tempfile.TemporaryDirectory(prefix='.bundle-', dir=output) as staging:
            stage = Path(staging)
            manifest = {'schemaVersion': VERSION, 'bundleId': identifier, 'snapshotId': catalogs['snapshotId'],
                        'catalogSchemaVersion': catalogs['schemaVersion'], 'catalogReleaseId': catalogs['releaseId'],
                        'catalogs': names, 'profiles': [], 'builtAtUnix': time.time()}
            cache = {}

            def records_for(profile_id, name):
                if name == GEAR_ROWS:
                    return gear[profile_id]['rows']
                if (profile_id, name) not in cache:
                    rows = read_catalog(release, profile_id, name)['records']
                    if name == 'Books':
                        # A 1.0.0 release still carries prose inside Books; never ship it here.
                        rows = [{k: v for k, v in row.items() if k != 'text'} for row in rows]
                    cache[profile_id, name] = rows
                return cache[profile_id, name]

            for profile_id in selected:
                profile = by_id[profile_id]
                base = pick_base(profile, available)
                if base not in selected:
                    base = None
                elif by_id[base]['arce']:
                    raise ExportError(f'Base profile {base} must not itself be a delta')
                folder = stage/profile_id
                folder.mkdir()
                files, inherits = {}, []
                for name in names:
                    rows = records_for(profile_id, name)
                    common = {'schemaVersion': VERSION, 'snapshotId': catalogs['snapshotId'],
                              'profile': {k: profile[k] for k in ('id', 'world', 'version', 'arce')},
                              'catalog': name}
                    if name == GEAR_ROWS:
                        # Unknown payload fields are accepted by the loader, so the policy
                        # that produced these rows travels with them.
                        common |= {k: gear[profile_id][k] for k in GEAR_ROW_FIELDS
                                   if k in gear[profile_id]}
                    if base is None:
                        payload = common | {'kind': 'full', 'records': rows}
                        entry = {'kind': 'full', 'records': len(rows)}
                    else:
                        where = f'{profile_id}/{name}'
                        changed, removed = delta(records_for(base, name), rows, where)
                        if not changed and not removed:
                            inherits.append(name)
                            continue
                        payload = common | {'kind': 'delta', 'base': base, 'changed': changed, 'removed': removed}
                        entry = {'kind': 'delta', 'base': base, 'changed': len(changed), 'removed': len(removed),
                                 'records': len(rows)}
                    path = folder/(name+'.json')
                    files[name] = entry | {'path': f'{profile_id}/{name}.json'} | write_payload(path, payload)
                if not files:
                    folder.rmdir()
                manifest['profiles'].append({k: profile[k] for k in ('id', 'world', 'version', 'arce')}
                                            | {'base': base, 'files': files, 'inherits': inherits})
                print(f'{profile_id}: {len(files)} files, {len(inherits)} inherited from {base or "-"}', flush=True)
            manifest['totals'] = {
                'files': sum(len(p['files']) for p in manifest['profiles']),
                'bytes': sum(f['bytes'] for p in manifest['profiles'] for f in p['files'].values()),
                'gzipBytes': sum(f['gzipBytes'] for p in manifest['profiles'] for f in p['files'].values())}
            write_payload(stage/'manifest.json', manifest)
            os.replace(stage, destination)
        pointer = output/'.current.tmp'
        write_payload(pointer, {'bundleId': identifier, 'manifest': identifier+'/manifest.json',
                                'snapshotId': catalogs['snapshotId']})
        os.replace(pointer, output/'current.json')
        totals = manifest['totals']
        print(f'Bundle complete: {destination}\n'
              f'{totals["files"]} files, {totals["bytes"]/1048576:.2f} MB raw, '
              f'{totals["gzipBytes"]/1048576:.2f} MB gzipped', flush=True)
        return destination
    finally:
        lock.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogs', type=Path, help='Catalog release directory, or the folder holding current.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--include-book-text', action='store_true', help='Publish book prose as its own file')
    parser.add_argument('--gear-rows', type=Path, help='Gear row directory; defaults to <root>/gear-rows')
    parser.add_argument('--no-gear-rows', action='store_true', help='Publish catalogs only')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        build(args.catalogs or root/'catalogs', args.output or root/'app-bundle',
              args.profile, args.include_book_text,
              None if args.no_gear_rows else (args.gear_rows or root/'gear-rows'))
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; previous active bundle is unchanged.')
        return 130
    except (ValueError, KeyError, OSError) as exc:
        print(f'Bundle build failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
