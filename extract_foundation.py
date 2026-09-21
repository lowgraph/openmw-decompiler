"""Build a plugin-preserving TES3 archive and three resolved game profiles.

Uses Python's standard library only. No location-path expansion or game writes.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time

from export_items import ExportError, config_value, decode

ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = 1
# Everything OpenMW can load as content: plugins, and the Lua scripts TR registers with.
CONTENT_SUFFIXES = frozenset({'.esm', '.esp', '.omwaddon', '.omwgame', '.omwscripts'})
# How a release states its version in the plugin header: "Main File v. 26.08".
HEADER_VERSION = re.compile(r'\bv\.?\s*(\d+(?:\.\d+)+[a-z]?)', re.IGNORECASE)
NAMED = set('GMST GLOB CLAS FACT RACE SOUN REGN BSGN LTEX SPEL ACTI ALCH APPA ARMO BODY BOOK CLOT CONT CREA DOOR ENCH INGR LEVC LEVI LIGH LOCK MISC NPC_ PROB REPA STAT WEAP DIAL SNDG'.split())


def json_text(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def fields(payload):
    """Yield byte views and offsets without copying entire records into subrecords."""
    view = memoryview(payload)
    offset = 0
    while offset < len(view):
        if len(view) - offset < 8:
            raise ExportError(f'Truncated subrecord header at payload offset {offset}')
        raw, size = struct.unpack_from('<4sI', view, offset)
        start = offset
        offset += 8
        if size > len(view) - offset:
            raise ExportError(f'Truncated subrecord {raw!r} at {start}')
        yield raw.decode('ascii'), view[offset:offset+size], start, offset + size
        offset += size


def txt(value, encoding):
    return decode(bytes(value), encoding)


def integer(value, fmt='I'):
    if len(value) != struct.calcsize('<' + fmt):
        raise ExportError(f'Invalid {fmt} field size {len(value)}')
    return struct.unpack('<' + fmt, value)[0]


def record_identity(tag, payload, encoding, topic):
    data = {}
    deleted = False
    for key, value, _, _ in fields(payload):
        if tag == 'CELL' and key in ('FRMR', 'MVRF'):
            break
        if key == 'DELE':
            deleted = True
        if key in ('NAME', 'INAM', 'INDX', 'INTV', 'SCHD', 'DATA'):
            data.setdefault(key, value)
    if tag in NAMED:
        if 'NAME' not in data:
            raise ExportError(f'{tag} missing NAME')
        ident = txt(data['NAME'], encoding)
        return ident.casefold(), ident, deleted
    if tag == 'SCPT':
        if 'SCHD' not in data or len(data['SCHD']) < 32:
            raise ExportError('SCPT missing/short SCHD')
        ident = txt(data['SCHD'][:32], encoding)
        return ident.casefold(), ident, deleted
    if tag in ('SKIL', 'MGEF'):
        ident = str(integer(data['INDX'], 'i'))
        return ident, ident, deleted
    if tag == 'INFO':
        if topic is None:
            raise ExportError('INFO appears before a DIAL record')
        ident = txt(data['INAM'], encoding)
        return json_text([topic.casefold(), ident.casefold()]), ident, deleted
    if tag == 'CELL':
        if len(data['DATA']) != 12:
            raise ExportError('CELL DATA is not 12 bytes')
        flags, x, y = struct.unpack('<Iii', data['DATA'])
        name = txt(data.get('NAME', b''), encoding)
        key = 'interior:' + name.casefold() if flags & 1 else f'exterior:{x},{y}'
        return key, name or key, deleted
    if tag == 'LAND':
        if len(data['INTV']) != 8:
            raise ExportError('LAND INTV is not 8 bytes')
        x, y = struct.unpack('<ii', data['INTV'])
        return f'exterior:{x},{y}', f'{x},{y}', deleted
    # PGRD and unknown record types are preserved byte-for-byte but not guessed
    # into a semantic identity. Their future decoder can use the archived bytes.
    return None, None, deleted


def reference_identity(value, plugin, masters):
    number = integer(value)
    parent = number >> 24
    if 0 < parent <= len(masters):
        owner, number = masters[parent-1], number & 0xffffff
    else:
        owner = plugin
    return f'{owner.casefold()}:{number:08x}'


def cell_references(payload, cell_key, plugin, masters, encoding):
    current = None
    moved = None
    target = None
    for tag, value, start, end in fields(payload):
        if tag in ('MVRF', 'FRMR') and current is not None:
            current['length'] = start - current['offset']
            yield current
            current = None
        if tag == 'MVRF':
            moved = reference_identity(value, plugin, masters)
            target = 'exterior:0,0'
        elif tag == 'CNDT' and moved is not None:
            if len(value) != 8:
                raise ExportError('Invalid moved-reference destination')
            x, y = struct.unpack('<ii', value)
            target = f'exterior:{x},{y}'
        elif tag == 'FRMR':
            key = reference_identity(value, plugin, masters)
            if moved is not None and moved != key:
                raise ExportError('MVRF/FRMR reference IDs disagree')
            current = {'key': key, 'target': target if moved else cell_key,
                       'object': None, 'deleted': False, 'offset': start, 'moved': moved is not None}
            moved = target = None
        elif current is not None:
            if tag == 'NAME':
                current['object'] = txt(value, encoding)
            elif tag == 'DELE':
                current['deleted'] = True
    if moved is not None:
        raise ExportError('MVRF lacks a following FRMR')
    if current is not None:
        current['length'] = len(payload) - current['offset']
        yield current


def load_config(path):
    path = path.resolve()
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    source = json.loads((path.parent / config['sourceConfig']).read_text(encoding='utf-8-sig'))
    profiles = config['profiles']
    if {p['id'] for p in profiles} != {'vanilla', 'tr', 'tr_arce'} or len(profiles) != 3:
        raise ExportError('Define exactly vanilla, tr, and tr_arce profiles')
    for p in profiles:
        if p['world'] not in source['versions'] or (p['arce'] and p['world'] != 'tamriel_rebuilt'):
            raise ExportError(f'Invalid world/ARCE profile {p["id"]}')
        names = [name.casefold() for name in p['plugins']]
        if not names or len(names) != len(set(names)):
            raise ExportError(f'Empty/duplicate plugin list in {p["id"]}')
        if any(Path(name).name != name for name in p['plugins']):
            raise ExportError('Profile plugins must be filenames')
        p['version'] = source['versions'][p['world']]
    output = Path(config['outputDirectory'])
    if not output.is_absolute():
        output = path.parent / output
    output = output.resolve()
    for protected in (source['baseDataDirectory'], source['modsDirectory']):
        if output.is_relative_to(Path(protected).resolve()):
            raise ExportError('Foundation output must not be inside game data')
    return config, source, output


def discover(config, source):
    """Discover configured profiles, including ARCE when disabled in openmw.cfg."""
    cfg = Path(source['openmwConfig'])
    base, mods = Path(source['baseDataDirectory']).resolve(), Path(source['modsDirectory']).resolve()
    wanted = {name.casefold() for p in config['profiles'] for name in p['plugins']}
    allowed = {name.casefold() for name in source['allowedPlugins']}
    if not wanted <= allowed:
        raise ExportError('Profile requests plugins outside allowedPlugins: ' + ', '.join(sorted(wanted-allowed)))
    directories = []
    encoding = 'cp1252'
    for line in cfg.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), config_value(value)
        if key in ('config', 'replace'):
            raise ExportError(f'Flatten the openmw.cfg {key}= directives before extraction')
        if key in ('data', 'data-local'):
            directory = Path(value)
            directory = (cfg.parent / directory).resolve() if not directory.is_absolute() else directory.resolve()
            permitted = directory == base
            if directory.is_relative_to(mods):
                parts = directory.relative_to(mods).parts
                permitted |= bool(parts and any(parts[0].casefold().startswith(p.casefold()) for p in source['allowedModPrefixes']))
            if permitted:
                directories.append(directory)
        elif key == 'encoding':
            encoding = {'win1250':'cp1250', 'win1251':'cp1251', 'win1252':'cp1252'}.get(value, value)
    # A release that ships a new plugin would otherwise be extracted without it, quietly:
    # nothing above can ask for a file nobody listed. Leaving one out has to be said.
    accounted = wanted | {name.casefold() for p in config['profiles']
                          for name in p.get('runtimeContent', ())} \
        | {name.casefold() for name in source.get('ignoredPlugins', ())}
    available, unlisted = {}, set()
    for directory in directories:
        if not directory.is_dir():
            raise ExportError(f'Approved data directory missing: {directory}')
        for path in directory.iterdir():
            if path.is_file() and path.name.casefold() in wanted:
                available[path.name.casefold()] = path
            elif (path.is_file() and path.suffix.casefold() in CONTENT_SUFFIXES
                    and path.name.casefold() not in accounted):
                unlisted.add(path.name)
    if unlisted:
        raise ExportError(
            f'{len(unlisted)} content file(s) in approved folders belong to no profile: '
            + ', '.join(sorted(unlisted))
            + '\n  A new release may have added them. Add each to a profile in '
              'foundation_config.json, or to ignoredPlugins in export_config.json to leave '
              'it out on purpose.')
    if wanted - available.keys():
        raise ExportError('Missing approved profile plugins: ' + ', '.join(sorted(wanted-available.keys())))
    names = list(dict.fromkeys(name.casefold() for p in config['profiles'] for name in p['plugins']))
    return [available[name] for name in names], encoding


def plugin_description(path):
    """The description in a TES3 plugin's header, which is where a release names itself."""
    with open(path, 'rb') as stream:
        head = stream.read(320)
    # Record header (16), then HEDR's own (8): version, flags, company[32], description[256].
    if head[:4] != b'TES3' or head[16:20] != b'HEDR':
        raise ExportError(f'{Path(path).name} has no TES3 header')
    return ' '.join(head[64:320].split(b'\0')[0].decode('cp1252', 'replace').split())


def openmw_version(executable):
    """What the OpenMW binary says it is, e.g. '0.51.0'. It prints and exits; no window."""
    run = subprocess.run([str(executable), '--version'], capture_output=True, text=True,
                         encoding='utf-8', errors='replace', timeout=120)
    found = re.search(r'OpenMW version (\S+)', run.stdout)
    if not found:
        raise ExportError(f'{executable} --version did not report a version')
    return found.group(1)


def label_carries(label, version):
    """Whether a hand-typed label names this version: 'Tamriel Rebuilt 26.08.23' carries the
    26.08 its header states, and does not carry 26.0 or 6.08."""
    return re.search(rf'(?<![\d.]){re.escape(version)}(?!\d)', label) is not None


def check_versions(source, paths, running=None):
    """Refuse a version label the files themselves contradict.

    The labels are typed by hand and every record carries one, so a stale label would
    mislabel a whole extraction. Each world names its evidence in versionEvidence:
    'openmw' for what the binary reports, or a plugin whose header states the release.
    """
    by_name = {Path(path).name.casefold(): Path(path) for path in paths}
    problems = []
    for world, evidence in source.get('versionEvidence', {}).items():
        label = source['versions'][world]
        if evidence == 'openmw':
            stated = running or openmw_version(source['openmwExecutable'])
            origin = f'{source["openmwExecutable"]} reports {stated}'
        else:
            plugin = by_name.get(evidence.casefold())
            if plugin is None:
                raise ExportError(f'versionEvidence names {evidence}, which no profile loads')
            description = plugin_description(plugin)
            found = HEADER_VERSION.search(description)
            if not found:
                raise ExportError(f'{plugin.name} states no version to check the '
                                  f'{world} label against: {description!r}')
            stated = found.group(1)
            origin = f'{plugin.name} says {description[:60]!r}'
        if not label_carries(label, stated):
            problems.append(f'versions.{world} is {label!r}, but {origin}')
    if problems:
        raise ExportError('A version label in export_config.json is stale:\n  '
                          + '\n  '.join(problems)
                          + '\n  Every record carries this label; update it before extracting.')


def extracted_snapshot(root, config, source):
    """The snapshot of the current extraction, after checking that the plugins OpenMW would
    load now are the very files it read. Anything taken from the running game — the effect
    dump — is only comparable with an extraction of the same files."""
    database = Path(root)/'game-data.sqlite'
    if not database.is_file():
        raise ExportError(f'No extraction at {database}; run extract_foundation.py first')
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        snapshot = json.loads(db.execute(
            "SELECT value FROM metadata WHERE key='snapshotId'").fetchone()[0])
        extracted = {name.casefold(): (size, mtime, digest) for name, size, mtime, digest
                     in db.execute('SELECT name, byte_size, mtime_ns, sha256 FROM plugins')}
    changed = []
    for path in discover(config, source)[0]:
        stat = path.stat()
        size, mtime, digest = extracted.get(path.name.casefold(), (None, None, None))
        if (stat.st_size, stat.st_mtime_ns) == (size, mtime):
            continue
        # Copied or touched but identical is fine; the extraction hashed every byte.
        if stat.st_size == size and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
            continue
        changed.append(path.name)
    if changed:
        raise ExportError('These plugins changed since the last extraction: '
                          + ', '.join(changed) + '\n  Run extract_foundation.py first.')
    return snapshot


def extraction_versions(root):
    """The label each world was extracted under, as its records carry it. This, not the
    config, is what to compare the running engine with: the config can be edited after."""
    database = Path(root)/'game-data.sqlite'
    if not database.is_file():
        raise ExportError(f'No extraction at {database}; run extract_foundation.py first')
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        profiles = json.loads(db.execute(
            "SELECT value FROM metadata WHERE key='profiles'").fetchone()[0])
    return {profile['world']: profile['version'] for profile in profiles}


def archive_plugin(db, path, plugin_id, encoding):
    before = path.stat()
    db.execute('INSERT INTO plugins(id,name,path,byte_size,mtime_ns) VALUES (?,?,?,?,?)',
               (plugin_id, path.name, str(path), before.st_size, before.st_mtime_ns))
    digest = hashlib.sha256()
    ordinal = refs_count = 0
    masters = []
    topic = None
    started = last = time.monotonic()
    print(f'Archiving {path.name} ({before.st_size/1048576:.1f} MiB)', flush=True)
    with path.open('rb') as stream:
        while stream.tell() < before.st_size:
            offset = stream.tell()
            header = stream.read(16)
            if len(header) != 16:
                raise ExportError(f'{path.name}: truncated header at {offset}')
            raw_tag, size, unknown, flags = struct.unpack('<4sIII', header)
            tag = raw_tag.decode('ascii')
            if ordinal == 0 and tag != 'TES3':
                raise ExportError(f'{path.name}: not a TES3 plugin')
            if size > before.st_size-stream.tell():
                raise ExportError(f'{path.name}: truncated {tag} at {offset}')
            payload = stream.read(size)
            if len(payload) != size:
                raise ExportError(f'{path.name} changed/truncated during reading')
            digest.update(header)
            digest.update(payload)
            try:
                key, display, deleted = record_identity(tag, payload, encoding, topic)
                if tag == 'TES3':
                    masters = [txt(value, encoding) for name, value, _, _ in fields(payload) if name == 'MAST']
                if tag == 'DIAL':
                    topic = display
                rec_id = db.execute('INSERT INTO record_versions(plugin_id,ordinal,file_offset,record_type,record_key,display_id,deleted,header_unknown,header_flags,payload) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (plugin_id, ordinal, offset, tag, key, display, deleted, unknown, flags, payload)).lastrowid
                if tag == 'CELL':
                    for ref in cell_references(payload, key, path.name, masters, encoding):
                        db.execute('INSERT INTO reference_versions(plugin_id,record_id,reference_key,source_cell_key,target_cell_key,object_id,deleted,payload_offset,payload_length,moved) VALUES (?,?,?,?,?,?,?,?,?,?)',
                            (plugin_id, rec_id, ref['key'], key, ref['target'], ref['object'], ref['deleted'], ref['offset'], ref['length'], ref['moved']))
                        refs_count += 1
                ordinal += 1
            except (ValueError, KeyError) as exc:
                raise ExportError(f'{path.name}: {tag} at byte {offset}: {exc}') from exc
            if ordinal % 2000 == 0:
                db.commit()
            now = time.monotonic()
            if now-last >= 3:
                print(f'  {stream.tell()/max(1,before.st_size):.1%} | {ordinal:,} records | {refs_count:,} references | {now-started:.0f}s', flush=True)
                last = now
    if ordinal == 0:
        raise ExportError(f'{path.name}: empty file')
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ExportError(f'{path.name} changed during extraction; rerun when files are stable')
    db.execute('UPDATE plugins SET sha256=?,masters_json=? WHERE id=?', (digest.hexdigest(), json_text(masters), plugin_id))
    db.commit()
    print(f'  Done: {ordinal:,} records, {refs_count:,} references', flush=True)


def resolve_profiles(db, profiles):
    plugins = {row[1].casefold(): row for row in db.execute('SELECT id,name,masters_json FROM plugins')}
    for profile in profiles:
        db.execute('INSERT INTO profiles VALUES (?,?,?,?)', (profile['id'],profile['world'],profile['version'],profile['arce']))
        loaded = set()
        for order, name in enumerate(profile['plugins']):
            plugin_id, actual_name, masters_json = plugins[name.casefold()]
            missing = {master.casefold() for master in json.loads(masters_json)} - loaded
            if missing:
                raise ExportError(f'{profile["id"]}: {actual_name} requires earlier masters: {", ".join(sorted(missing))}')
            print(f'Resolving {profile["id"]}: {actual_name}', flush=True)
            db.execute('INSERT INTO profile_plugins VALUES (?,?,?)', (profile['id'],plugin_id,order))
            # Process revisions in original order, preserving origin and updating
            # the winner, including deletion tombstones. No BLOBs are duplicated.
            cursor = db.execute('SELECT id,record_type,record_key FROM record_versions WHERE plugin_id=? AND record_key IS NOT NULL ORDER BY ordinal', (plugin_id,))
            last = time.monotonic()
            count = 0
            for rec_id, tag, key in cursor:
                db.execute('INSERT INTO resolved_records VALUES (?,?,?,?,?) ON CONFLICT(profile_id,record_type,record_key) DO UPDATE SET winner_id=excluded.winner_id',
                           (profile['id'],tag,key,plugin_id,rec_id))
                count += 1
                if time.monotonic()-last >= 3:
                    print(f'  {count:,} record revisions resolved', flush=True)
                    last = time.monotonic()
            cursor = db.execute('SELECT id,reference_key FROM reference_versions WHERE plugin_id=? ORDER BY id', (plugin_id,))
            last = time.monotonic()
            count = 0
            for ref_id, key in cursor:
                db.execute('INSERT INTO resolved_references VALUES (?,?,?,?) ON CONFLICT(profile_id,reference_key) DO UPDATE SET winner_id=excluded.winner_id',
                           (profile['id'],key,plugin_id,ref_id))
                count += 1
                if time.monotonic()-last >= 3:
                    print(f'  {count:,} reference revisions resolved', flush=True)
                    last = time.monotonic()
            loaded.add(name.casefold())
            db.commit()


def build(config, paths, encoding, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    lock_path = target.with_suffix('.lock')
    try:
        lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ExportError(f'Build lock exists: {lock_path}. Check for another running build before removing a stale lock.') from exc
    stage = None
    db = None
    try:
        os.write(lock, str(os.getpid()).encode('ascii'))
        os.close(lock)
        handle, filename = tempfile.mkstemp(prefix='.foundation-', suffix='.sqlite', dir=target.parent)
        os.close(handle)
        stage = Path(filename)
        db = sqlite3.connect(stage)
        db.execute('PRAGMA cache_size=-32768')
        db.execute('PRAGMA temp_store=MEMORY')
        db.execute('PRAGMA journal_mode=DELETE')
        db.executescript((ROOT / 'foundation_schema.sql').read_text())
        for plugin_id, path in enumerate(paths, 1):
            archive_plugin(db, path, plugin_id, encoding)
        resolve_profiles(db, config['profiles'])
        fingerprints = list(db.execute('SELECT name,sha256 FROM plugins ORDER BY id'))
        snapshot = hashlib.sha256(json_text({'schema': SCHEMA_VERSION, 'encoding': encoding,
            'profiles': config['profiles'], 'plugins': fingerprints}).encode()).hexdigest()
        for key, value in {'schemaVersion': SCHEMA_VERSION, 'snapshotId': snapshot, 'encoding': encoding,
                           'builtAtUnix': time.time(), 'profiles': config['profiles']}.items():
            db.execute('INSERT INTO metadata VALUES (?,?)', (key,json_text(value)))
        db.commit()
        print('Checking database integrity...', flush=True)
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
            raise ExportError('Database integrity validation failed')
        unkeyed = list(db.execute("SELECT record_type,COUNT(*) FROM record_versions WHERE record_key IS NULL AND record_type != 'TES3' GROUP BY record_type"))
        print(f'Preserved without semantic resolution: {unkeyed or "none"}', flush=True)
        db.close()
        db = None
        os.replace(stage,target)
        print(f'Foundation complete: {target}\nSnapshot: {snapshot}', flush=True)
    finally:
        if db is not None:
            db.close()
        if stage is not None:
            for path in (stage, Path(str(stage)+'-journal')):
                if path.exists():
                    path.unlink()
        lock_path.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'foundation_config.json')
    parser.add_argument('--list-plugins', action='store_true', help='Preview configured profile inputs without reading plugin records')
    args = parser.parse_args(argv)
    try:
        config, source, output = load_config(args.config)
        paths, encoding = discover(config, source)
        check_versions(source, paths)
        for profile in config['profiles']:
            print(f'{profile["id"]}: ' + ' -> '.join(profile['plugins']))
        if args.list_plugins:
            for path in paths:
                print(path)
            print(f'Output: {output / "game-data.sqlite"}')
            return 0
        build(config, paths, encoding, output/'game-data.sqlite')
        return 0
    except KeyboardInterrupt:
        print('\nCancelled; previously published foundation is unchanged.', flush=True)
        return 130
    except (OSError, ValueError, KeyError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print(f'Foundation extraction failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
