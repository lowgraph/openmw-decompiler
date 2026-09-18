"""Export static item locations and separate script leads from approved TES3 plugins.

Run after export_items.py. Writes ItemLocations.json, never changes item tables.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import time

from export_items import ROOT, CATEGORIES, ExportError, decode, unpack, records, select_plugins

HOLDERS = {'CONT', 'NPC_', 'CREA'}
LISTS = {'LEVI', 'LEVC'}
TOKEN = re.compile(r'"([^"\r\n]*)"|([^\s,()]+)')


def text(data, key, encoding):
    return decode(data.get(key), encoding)


def number(data, key, fmt, default):
    return unpack(fmt, data[key])[0] if key in data else default


def read_catalog(directory):
    catalog = {}
    for name in CATEGORIES.values():
        path = directory / f'{name}.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        for item in data['items']:
            key = item['id'].casefold()
            if key in catalog:
                raise ExportError(f'Duplicate item ID across tables: {item["id"]}')
            catalog[key] = {'itemId': item['id'], 'gameDataVersion': item['gameDataVersion'],
                            'locations': [], 'scriptReferences': []}
    if not catalog:
        raise ExportError('Item tables are empty. Run python export_items.py first.')
    return catalog


def script_leads(source, catalog):
    """Lexical evidence only. A mention is never asserted to execute or grant loot."""
    result = defaultdict(list)
    for line_number, line in enumerate(source.splitlines(), 1):
        # Preserve semicolons inside quoted strings, remove actual comments.
        quoted = False
        end = len(line)
        for i, char in enumerate(line):
            if char == '"':
                quoted = not quoted
            elif char == ';' and not quoted:
                end = i
                break
        tokens = [a if a else b for a, b in TOKEN.findall(line[:end])]
        for ident in set(token.casefold() for token in tokens) & catalog.keys():
            result[ident].append({'line': line_number, 'text': line.strip()})
    return result


def load_definitions(plugins, encoding, catalog):
    definitions, scripts, dialogs = {}, {}, {}
    loaded = set()
    for plugin in plugins:
        print(f'Loading inventories and lists: {plugin.path.name}', flush=True)
        topic = ''
        for tag, fields in records(plugin.path, HOLDERS | LISTS | set(CATEGORIES) | {'TES3', 'SCPT', 'DIAL', 'INFO'}):
            data = dict(fields)
            if tag == 'TES3':
                for key, value in fields:
                    if key == 'MAST' and decode(value, encoding).casefold() not in loaded:
                        raise ExportError(f'{plugin.path.name}: missing earlier approved master {decode(value, encoding)}')
                continue
            if tag == 'DIAL':
                topic = text(data, 'NAME', encoding)
                continue
            if tag == 'SCPT':
                if 'SCHD' not in data:
                    raise ExportError(f'{plugin.path.name}: SCPT missing SCHD')
                ident = decode(data['SCHD'][:32], encoding)
                scripts[ident.casefold()] = {'id': ident, 'sourcePlugin': plugin.path.name,
                    'source': text(data, 'SCTX', encoding), 'deleted': 'DELE' in data}
                continue
            if tag == 'INFO':
                ident = text(data, 'INAM', encoding)
                dialogs[(topic.casefold(), ident.casefold())] = {
                    'id': ident, 'topic': topic, 'actorId': text(data, 'ONAM', encoding) or None,
                    'sourcePlugin': plugin.path.name, 'source': text(data, 'BNAM', encoding),
                    'deleted': 'DELE' in data}
                continue
            ident = text(data, 'NAME', encoding)
            if not ident:
                raise ExportError(f'{plugin.path.name}: {tag} missing NAME')
            obj = {'id': ident, 'kind': tag, 'name': text(data, 'FNAM', encoding) or ident,
                   'sourcePlugin': plugin.path.name, 'scriptId': text(data, 'SCRI', encoding) or None,
                   'deleted': 'DELE' in data, 'entries': []}
            if tag in HOLDERS:
                for key, value in fields:
                    if key == 'NPCO':
                        if len(value) < 5:
                            raise ExportError(f'{ident}: malformed NPCO')
                        count, = unpack('i', value[:4])
                        obj['entries'].append({'id': decode(value[4:], encoding), 'count': count})
            elif tag in LISTS:
                obj['chanceNone'] = number(data, 'NNAM', 'B', 0)
                obj['flags'] = number(data, 'DATA', 'I', 0)
                entry_tag = 'INAM' if tag == 'LEVI' else 'CNAM'
                pending = None
                for key, value in fields:
                    if key == entry_tag:
                        if pending is not None:
                            raise ExportError(f'{ident}: list entry lacks level')
                        pending = decode(value, encoding)
                    elif key == 'INTV' and pending is not None:
                        level, = unpack('h', value)
                        obj['entries'].append({'id': pending, 'level': level})
                        pending = None
                if pending is not None or len(obj['entries']) != number(data, 'INDX', 'I', 0):
                    raise ExportError(f'{ident}: leveled-list count/level mismatch')
            definitions[ident.casefold()] = obj
        loaded.add(plugin.path.name.casefold())
    definitions = {k: v for k, v in definitions.items() if not v['deleted']}
    unavailable_scripts = []
    for kind, collection in (('script', scripts), ('dialogue_result', dialogs)):
        for script in collection.values():
            if script['deleted']:
                continue
            if kind == 'script' and not script['source']:
                unavailable_scripts.append(script['id'])
            for ident, lines in script_leads(script['source'], catalog).items():
                catalog[ident]['scriptReferences'].append({
                    'kind': kind, 'id': script['id'], 'sourcePlugin': script['sourcePlugin'],
                    'topic': script.get('topic'), 'actorId': script.get('actorId'),
                    'evidence': lines, 'interpretation': 'unverified_text_reference'})
    return definitions, unavailable_scripts


def ref_key(raw, plugin_name, masters):
    value, = unpack('I', raw)
    index = value >> 24
    if 0 < index <= len(masters):
        owner, number_value = masters[index - 1], value & 0xffffff
    else:
        # Match OpenMW's treatment of faulty out-of-range master indices.
        owner, number_value = plugin_name, value
    return f'{owner.casefold()}:{number_value:08x}'


def split_cell(fields):
    header, refs = [], []
    current = None
    moved_id, destination = None, None
    for key, value in fields:
        if key == 'MVRF':
            if current is not None:
                refs.append(current)
                current = None
            moved_id, destination = value, None
        elif key == 'CNDT' and moved_id is not None and current is None:
            destination = unpack('ii', value)
        elif key == 'FRMR':
            if current is not None:
                refs.append(current)
            current = {'raw': value, 'fields': [], 'movedId': moved_id, 'destination': destination}
            moved_id, destination = None, None
        elif current is not None:
            current['fields'].append((key, value))
        elif moved_id is None:
            header.append((key, value))
    if current is not None:
        refs.append(current)
    if moved_id is not None:
        raise ExportError('MVRF has no paired FRMR')
    return dict(header), refs


def load_placements(plugins, encoding, definitions, catalog):
    cells, references = {}, {}
    relevant = set(catalog) | {key for key, obj in definitions.items() if obj['kind'] in HOLDERS | LISTS}
    for plugin in plugins:
        print(f'Loading cell references: {plugin.path.name}', flush=True)
        masters = []
        for tag, fields in records(plugin.path, {'TES3', 'CELL'}):
            if tag == 'TES3':
                masters = [decode(v, encoding) for k, v in fields if k == 'MAST']
                continue
            header, refs = split_cell(fields)
            flags, x, y = unpack('Iii', header['DATA'])
            interior = bool(flags & 1)
            name = text(header, 'NAME', encoding)
            cell_id = 'interior:' + name.casefold() if interior else f'exterior:{x},{y}'
            cells[cell_id] = {'id': cell_id, 'name': name or None, 'interior': interior,
                'grid': None if interior else {'x': x, 'y': y},
                'regionId': text(header, 'RGNN', encoding) or None, 'deleted': 'DELE' in header}
            for raw in refs:
                key = ref_key(raw['raw'], plugin.path.name, masters)
                data = dict(raw['fields'])
                previous = references.get(key)
                ident = text(data, 'NAME', encoding) or (previous['baseId'] if previous else '')
                if ident.casefold() not in relevant:
                    # A winning reference can replace a previously relevant object.
                    references.pop(key, None)
                    continue
                target = cell_id
                if raw['movedId'] is not None:
                    if ref_key(raw['movedId'], plugin.path.name, masters) != key:
                        raise ExportError(f'{plugin.path.name}: mismatched MVRF/FRMR')
                    dx, dy = raw['destination'] or (0, 0)
                    target = f'exterior:{dx},{dy}'
                position = unpack('6f', data['DATA']) if 'DATA' in data else None
                references[key] = {'id': key, 'baseId': ident, 'cellId': target,
                    'sourcePlugin': plugin.path.name, 'world': plugin.world,
                    'deleted': 'DELE' in data, 'count': number(data, 'NAM9', 'i', 1),
                    'position': dict(zip(('x', 'y', 'z'), position[:3])) if position else None,
                    'rotation': dict(zip(('x', 'y', 'z'), position[3:])) if position else None,
                    'ownerId': text(data, 'ANAM', encoding) or None,
                    'factionId': text(data, 'CNAM', encoding) or None,
                    'requiredFactionRank': number(data, 'INDX', 'i', -2),
                    'ownershipGlobal': text(data, 'BNAM', encoding) or None,
                    'lockLevel': number(data, 'FLTV', 'i', 0),
                    'keyId': text(data, 'KNAM', encoding) or None,
                    'trapId': text(data, 'TNAM', encoding) or None,
                    'soulId': text(data, 'XSOL', encoding) or None}
    return cells, {k: v for k, v in references.items() if not v['deleted']}


def expand(ident, definitions, catalog, warnings, path=(), active=()):
    key = ident.casefold()
    if key in catalog:
        yield key, list(path)
        return
    if key in active:
        warnings.add('Inventory/list cycle: ' + ' -> '.join((*active, key)))
        return
    obj = definitions.get(key)
    if obj is None:
        warnings.add(f'Unresolved inventory/list entry: {ident}')
        return
    if obj['kind'] not in HOLDERS | LISTS:
        return
    if obj['kind'] in LISTS and obj['chanceNone'] >= 100:
        return
    for i, entry in enumerate(obj['entries']):
        step = {'id': obj['id'], 'kind': obj['kind'], 'name': obj['name'],
                'sourcePlugin': obj['sourcePlugin'], 'entryIndex': i,
                'entryId': entry['id'], 'count': entry.get('count', 1),
                'minimumLevel': entry.get('level'), 'chanceNone': obj.get('chanceNone'),
                'flags': obj.get('flags'), 'scriptId': obj['scriptId']}
        yield from expand(entry['id'], definitions, catalog, warnings, (*path, step), (*active, key))


def build_locations(catalog, definitions, cells, references, versions, sink=None, show_progress=False):
    warnings = set()
    started = last_update = time.monotonic()
    generated = 0
    total = len(references)
    if show_progress:
        print(f'Expanding {total:,} references; storing location rows on disk...', flush=True)

    def progress(processed, force=False):
        nonlocal last_update
        now = time.monotonic()
        if show_progress and (force or now - last_update >= 3):
            print(f'  References {processed:,}/{total:,} | location paths {generated:,} | elapsed {now-started:.0f}s', flush=True)
            last_update = now

    for processed, reference in enumerate(references.values(), 1):
        progress(processed - 1)
        cell = cells.get(reference['cellId'])
        if cell and cell['deleted']:
            continue
        if cell is None:
            # Moved references can point into an otherwise undeclared exterior.
            if not reference['cellId'].startswith('exterior:'):
                raise ExportError(f'Missing cell {reference["cellId"]}')
            x, y = map(int, reference['cellId'].split(':', 1)[1].split(','))
            cell = {'id': reference['cellId'], 'name': None, 'interior': False,
                    'grid': {'x': x, 'y': y}, 'regionId': None, 'deleted': False}
        if reference['count'] == 0:
            continue
        for item_id, path in expand(reference['baseId'], definitions, catalog, warnings):
            holder = next((step for step in reversed(path) if step['kind'] in HOLDERS), None)
            source_type = {'CONT': 'container', 'NPC_': 'npc_inventory', 'CREA': 'creature_inventory'}.get(holder['kind'] if holder else '', 'placed')
            random = any(step['kind'] in LISTS for step in path)
            count = abs(reference['count'])
            for step in path:
                count *= abs(step['count'])
            if count == 0:
                continue
            actor_inventory = source_type in ('npc_inventory', 'creature_inventory')
            attached = sorted({step['scriptId'] for step in path if step['scriptId']} |
                {obj['scriptId'] for obj in (definitions.get(reference['baseId'].casefold(), {}), definitions.get(item_id, {})) if obj.get('scriptId')})
            owned = bool(reference['ownerId'] or reference['factionId'] or reference['ownershipGlobal'])
            label = cell['name'] or cell['regionId'] or cell['id']
            if not cell['interior']:
                label += f' ({cell["grid"]["x"]}, {cell["grid"]["y"]})'
            label += ' — ' + (holder['name'] if holder else catalog[item_id]['itemId'])
            location = {
                'referenceId': reference['id'], 'sourcePlugin': reference['sourcePlugin'],
                'gameDataVersion': {'world': reference['world'], 'version': versions[reference['world']]},
                'cell': {k: v for k, v in cell.items() if k != 'deleted'},
                'position': reference['position'], 'rotation': reference['rotation'],
                'sourceType': source_type, 'rootObjectId': reference['baseId'],
                'containerId': holder['id'] if source_type == 'container' else None,
                'actorId': holder['id'] if actor_inventory else None,
                'count': count, 'restocking': any(step['count'] < 0 for step in path),
                'availability': 'leveled_chance' if random else 'static_definition',
                'path': path, 'scriptIds': attached, 'soulId': reference['soulId'],
                'access': {'ownerId': reference['ownerId'], 'factionId': reference['factionId'],
                    'requiredFactionRank': None if reference['requiredFactionRank'] == -2 else reference['requiredFactionRank'],
                    'ownershipGlobal': reference['ownershipGlobal'],
                    'takingIsTheft': 'conditional' if owned or actor_inventory else 'not_marked_owned',
                    'lockLevel': reference['lockLevel'], 'keyId': reference['keyId'], 'trapId': reference['trapId'],
                    'saleStatus': 'not_determined'}, 'label': label}
            if sink is None:
                catalog[item_id]['locations'].append(location)
            else:
                sink(item_id, location)
            generated += 1
            progress(processed)
    for item in catalog.values():
        item['locations'].sort(key=lambda v: (v['cell']['id'], v['referenceId'], json.dumps(v['path'], sort_keys=True)))
        item['scriptReferences'].sort(key=lambda v: (v['kind'], v['id'].casefold(), v['sourcePlugin'].casefold()))
    progress(total, force=True)
    return sorted(warnings)


def schema_validators():
    sys.path.append(str(ROOT / '.validation-deps'))
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise ExportError('Run python -m pip install -r requirements.txt first.') from exc
    schema = json.loads((ROOT / 'location-schema.json').read_text(encoding='utf-8'))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    row_validator = Draft202012Validator({'$defs': schema['$defs'], **schema['properties']['items']['items']})
    location_schema = schema['properties']['items']['items']['properties']['locations']['items']
    location_validator = Draft202012Validator({'$defs': schema['$defs'], **location_schema})
    return validator, row_validator, location_validator


def validate_output(output):
    validator, row_validator, _ = schema_validators()
    # Validate rows separately to avoid constructing enormous error paths.
    validator.validate({**output, 'items': []})
    for item in output['items']:
        errors = list(row_validator.iter_errors(item))
        if errors:
            raise ExportError(f'{item["itemId"]}: {errors[0].message}')


class LocationSpool:
    """Disk-backed rows: RAM use does not grow with expanded location count."""

    def __init__(self, path):
        self.connection = sqlite3.connect(path)
        # Disposable staging database; the final JSON still publishes atomically.
        self.connection.execute('PRAGMA journal_mode=OFF')
        self.connection.execute('PRAGMA synchronous=OFF')
        self.connection.execute('PRAGMA cache_size=-8192')
        # Queries use item_order; keep any auxiliary SQLite temp structures off
        # the system temp drive. The large row payloads live in this database.
        self.connection.execute('PRAGMA temp_store=MEMORY')
        self.connection.execute('CREATE TABLE locations (item TEXT, cell TEXT, ref TEXT, payload TEXT)')
        self.connection.execute('CREATE INDEX item_order ON locations(item, cell, ref)')
        self.count = 0
        self.found = set()
        self.validator = schema_validators()[2]

    def add(self, item_id, location):
        error = next(self.validator.iter_errors(location), None)
        if error is not None:
            raise ExportError(f'{item_id}: {error.message}')
        payload = json.dumps(location, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        self.connection.execute('INSERT INTO locations VALUES (?, ?, ?, ?)',
                                (item_id, location['cell']['id'], location['referenceId'], payload))
        self.count += 1
        self.found.add(item_id)
        if self.count % 2000 == 0:
            self.connection.commit()

    def rows(self, item_id):
        for row in self.connection.execute('SELECT payload FROM locations WHERE item=? ORDER BY cell, ref, rowid', (item_id,)):
            yield row[0]

    def close(self):
        self.connection.close()


def write_spooled_output(path, output, spool):
    """Stream JSON from validated disk rows; never materialize a full item list."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    started = last_update = time.monotonic()
    written = 0
    print(f'Writing {spool.count:,} validated location paths to JSON...', flush=True)
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.locations-', suffix='.tmp', delete=False) as stream:
            temp_path = Path(stream.name)
            header = {k: v for k, v in output.items() if k != 'items'}
            stream.write(json.dumps(header, ensure_ascii=False, allow_nan=False)[:-1] + ',\n"items":[\n')
            for index, item in enumerate(output['items']):
                if index:
                    stream.write(',\n')
                if item['locations']:
                    raise ExportError('Streaming output requires an empty in-memory location list')
                fields = {k: v for k, v in item.items() if k != 'locations'}
                stream.write(json.dumps(fields, ensure_ascii=False, allow_nan=False)[:-1] + ',"locations":[\n')
                first = True
                for payload in spool.rows(item['itemId'].casefold()):
                    if not first:
                        stream.write(',\n')
                    stream.write(payload)
                    first = False
                    written += 1
                    now = time.monotonic()
                    if now - last_update >= 3:
                        print(f'  Written {written:,}/{spool.count:,} location paths | elapsed {now-started:.0f}s', flush=True)
                        last_update = now
                stream.write('\n]}')
            stream.write('\n]}\n')
        if written != spool.count:
            raise ExportError(f'Staged location count mismatch: {written} != {spool.count}')
        os.replace(temp_path, path)
        print(f'  Written {written:,}/{spool.count:,} location paths', flush=True)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def write_output(path, output):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.locations-', suffix='.tmp', delete=False) as stream:
            temp_path = Path(stream.name)
            json.dump(output, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'export_config.json')
    parser.add_argument('--items-dir', type=Path, help='Directory containing the populated item tables')
    parser.add_argument('--output', type=Path, help='Override the configured location JSON output path')
    parser.add_argument('--cache-dir', type=Path, help='Override the configured temporary database directory')
    parser.add_argument('--list-plugins', action='store_true')
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.config.read_text(encoding='utf-8-sig'))
        plugins, ignored, encoding = select_plugins(settings)
        if args.list_plugins:
            for plugin in plugins:
                print(plugin.path)
            return 0
        directory = (args.items_dir or args.config.resolve().parent / settings['outputDirectory']).resolve()
        output_directory = Path(settings.get('locationOutputDirectory', str(directory)))
        if not output_directory.is_absolute():
            output_directory = args.config.resolve().parent / output_directory
        destination = (args.output or output_directory / 'ItemLocations.json').resolve()
        cache_directory = args.cache_dir or Path(settings.get('locationCacheDirectory', 'A:/Cache'))
        if not cache_directory.is_absolute():
            cache_directory = args.config.resolve().parent / cache_directory
        cache_directory = cache_directory.resolve()
        if destination in {(directory / f'{name}.json').resolve() for name in CATEGORIES.values()}:
            raise ExportError('Location output must not overwrite an item table.')
        for protected in (settings['baseDataDirectory'], settings['modsDirectory']):
            if destination.is_relative_to(Path(protected).resolve()) or cache_directory.is_relative_to(Path(protected).resolve()):
                raise ExportError('Location output cannot be inside game data.')
        report = json.loads((directory / 'export-report.json').read_text(encoding='utf-8'))
        if [str(p.path).casefold() for p in plugins] != [p['path'].casefold() for p in report['plugins']] or report['versions'] != settings['versions']:
            raise ExportError('Item export uses a different load order/version. Rerun export_items.py first.')
        catalog = read_catalog(directory)
        definitions, no_source = load_definitions(plugins, encoding, catalog)
        cells, refs = load_placements(plugins, encoding, definitions, catalog)
        destination.parent.mkdir(parents=True, exist_ok=True)
        cache_directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='openmw-locations-', dir=cache_directory) as staging:
            print(f'Temporary disk storage: {staging}', flush=True)
            spool = LocationSpool(Path(staging) / 'locations.sqlite')
            try:
                warnings = build_locations(catalog, definitions, cells, refs, settings['versions'],
                                           sink=spool.add, show_progress=True)
                # Release reference and definition maps before final JSON writing.
                del definitions, cells, refs
                output = {'schemaVersion': '1.0.0', 'coverage': {
            'mode': 'static_plugin_analysis', 'plugins': [p.path.name for p in plugins],
            'excludedContent': ignored, 'warnings': warnings, 'scriptsWithoutSource': no_source,
            'limitations': ['Runtime scripts and quest conditions are not evaluated.',
                'Script/dialogue mentions are leads, not confirmed acquisition locations.',
                'Leveled paths describe possibilities, not exact probabilities.',
                'Merchant sales, actor travel, respawns and save-game changes are not simulated.']},
                    'items': sorted(catalog.values(), key=lambda row: row['itemId'].casefold())}
                print('Validating item metadata (location rows already validated)...', flush=True)
                validate_output(output)
                write_spooled_output(destination, output, spool)
                count, found = spool.count, len(spool.found)
            finally:
                spool.close()
        print(f'Exported {count} location paths for {found}/{len(catalog)} items to {destination}')
        print(f'{len(warnings)} coverage warnings; see coverage in the output.')
        return 0
    except KeyboardInterrupt:
        print('\nExport cancelled. Existing item tables and completed location output were not changed.', flush=True)
        return 130
    except (OSError, ValueError, KeyError, RecursionError, sqlite3.Error) as exc:
        print(f'Location export failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
