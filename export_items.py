"""Export TES3 inventory definitions from the user's permitted active plugins.

Run `python export_items.py --list-plugins` to inspect the scope without parsing.
Run `python export_items.py` to populate the datasets. Game files are read-only.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

from effect_names import EFFECT_GMSTS

ROOT = Path(__file__).resolve().parent
CATEGORIES = dict(zip(
    ('WEAP', 'ARMO', 'CLOT', 'BOOK', 'ALCH', 'INGR', 'APPA', 'LOCK', 'PROB', 'REPA', 'LIGH', 'MISC'),
    ('Weapons', 'Armor', 'Clothing', 'Books', 'Potions', 'Ingredients', 'Apparatus', 'Lockpicks', 'Probes', 'RepairTools', 'Lights', 'Miscellaneous')))
WEAPONS = 'SB1H LB1H LB2H BL1H BL2C BL2W SP2H AX1H AX2H BOW CROSSBOW THROWN ARROW BOLT'.split()
ARMOR = 'helmet cuirass left_pauldron right_pauldron greaves boots left_gauntlet right_gauntlet shield left_bracer right_bracer'.split()
CLOTHING = 'pants shoes shirt belt robe right_glove left_glove skirt ring amulet'.split()
ATTRIBUTES = 'strength intelligence willpower agility speed endurance personality luck'.split()
SKILLS = ('block armorer medium_armor heavy_armor blunt_weapon long_blade axe spear athletics '
          'enchant destruction alteration illusion conjuration mysticism restoration alchemy '
          'unarmored security sneak acrobatics light_armor short_blade marksman mercantile speechcraft hand_to_hand').split()
ATTRIBUTE_EFFECTS = {17, 22, 74, 79, 85}
SKILL_EFFECTS = {21, 26, 78, 83, 89}
LIGHT_FLAGS = 'dynamic carry negative flicker fire off_default flicker_slow pulse pulse_slow'.split()


class ExportError(ValueError):
    """An input cannot be represented reliably; no output should be published."""


def unpack(fmt, data):
    if len(data) != struct.calcsize('<' + fmt):
        raise ExportError(f'Expected {struct.calcsize("<" + fmt)} bytes, got {len(data)}')
    return struct.unpack('<' + fmt, data)


def choice(values, index, label):
    if not 0 <= index < len(values):
        raise ExportError(f'Unsupported {label} index {index}')
    return values[index]


def decode(data, encoding='cp1252'):
    return data.rstrip(b'\0').decode(encoding) if data else ''


def subrecords(data):
    result = []
    position = 0
    while position < len(data):
        if len(data) - position < 8:
            raise ExportError('Truncated subrecord header')
        tag, size = struct.unpack_from('<4sI', data, position)
        position += 8
        if size > len(data) - position:
            raise ExportError(f'Truncated {tag!r} subrecord')
        result.append((tag.decode('ascii'), data[position:position + size]))
        position += size
    return result


def records(path, wanted=None):
    """Stream relevant records and seek past cells, meshes, dialogue, etc."""
    if wanted is None:
        wanted = set(CATEGORIES) | {'TES3', 'ENCH', 'GMST'}
    with path.open('rb') as stream:
        file_size = os.fstat(stream.fileno()).st_size
        first = True
        while stream.tell() < file_size:
            offset = stream.tell()
            header = stream.read(16)
            if len(header) != 16:
                raise ExportError(f'{path.name}: truncated header at {offset}')
            raw_tag, size, _unknown, _flags = unpack('4sIII', header)
            tag = raw_tag.decode('ascii')
            if first and tag != 'TES3':
                raise ExportError(f'{path.name}: not a TES3 plugin')
            first = False
            if size > file_size - stream.tell():
                raise ExportError(f'{path.name}: truncated {tag} at {offset}')
            if tag in wanted:
                yield tag, subrecords(stream.read(size))
            else:
                stream.seek(size, 1)
        if first:
            raise ExportError(f'{path.name}: empty plugin')


@dataclass(frozen=True)
class Plugin:
    path: Path
    world: str


def config_value(raw):
    """OpenMW uses & to escape quotes/ampersands inside quoted values."""
    value = raw.strip()
    if not value.startswith('"'):
        return value.split('#', 1)[0].strip()
    out = []
    i = 1
    while i < len(value):
        char = value[i]
        if char == '"':
            return ''.join(out)
        if char == '&' and i + 1 < len(value) and value[i + 1] in '&"':
            i += 1
            char = value[i]
        out.append(char)
        i += 1
    raise ExportError('Unclosed quote in openmw.cfg')


def select_plugins(settings):
    cfg = Path(settings['openmwConfig'])
    base = Path(settings['baseDataDirectory']).resolve()
    mods = Path(settings['modsDirectory']).resolve()
    directories, content = [], []
    encoding = 'cp1252'
    for line in cfg.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
            continue
        key, raw = line.split('=', 1)
        key, value = key.strip(), config_value(raw)
        if key in ('config', 'replace'):
            raise ExportError(f'Unsupported {key}= directive; supply a flattened openmw.cfg')
        if key in ('data', 'data-local'):
            path = Path(value)
            directories.append((cfg.parent / path).resolve() if not path.is_absolute() else path.resolve())
        elif key == 'content':
            content.append(value)
        elif key == 'encoding':
            encoding = {'win1250': 'cp1250', 'win1251': 'cp1251', 'win1252': 'cp1252'}.get(value, value)
    if not content:
        raise ExportError('No content= load order in the specified openmw.cfg')

    # Only enumerate files directly in approved data directories. Never recurse
    # into the other mod folders or inspect their plugins.
    available = {}
    for directory in directories:
        world = None
        if directory == base:
            world = 'vanilla'
        elif directory.is_relative_to(mods):
            parts = directory.relative_to(mods).parts
            if parts and any(parts[0].casefold().startswith(p.casefold()) for p in settings['allowedModPrefixes']):
                world = 'tamriel_rebuilt'
        if world is None:
            continue
        if not directory.is_dir():
            raise ExportError(f'Approved data directory is missing: {directory}')
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in ('.esm', '.esp'):
                # Later data directories win filename collisions, as in OpenMW.
                available[path.name.casefold()] = Plugin(path, world)
    selected, ignored, seen = [], [], set()
    allowed = {name.casefold() for name in settings['allowedPlugins']}
    for name in content:
        if Path(name).name != name:
            raise ExportError(f'content= must contain a filename: {name}')
        key = name.casefold()
        if key in allowed:
            if key not in available:
                raise ExportError(f'Approved active plugin missing from approved data directories: {name}')
            if key in seen:
                raise ExportError(f'Duplicate plugin in load order: {name}')
            selected.append(available[key])
            seen.add(key)
        else:
            ignored.append(name)
    for name in ('morrowind.esm', 'tribunal.esm', 'bloodmoon.esm'):
        if name not in seen:
            raise ExportError(f'Required base master not found in approved active data: {name}')
    return selected, ignored, encoding


@dataclass
class Record:
    tag: str
    fields: list
    source: Plugin
    origin_world: str


def load_plugins(plugins, encoding):
    winners = {}
    loaded = set()
    for plugin in plugins:
        print(f'Reading {plugin.path.name}', flush=True)
        for tag, fields in records(plugin.path):
            values = dict(fields)
            if tag == 'TES3':
                for field, payload in fields:
                    if field == 'MAST' and decode(payload, encoding).casefold() not in loaded:
                        raise ExportError(f'{plugin.path.name} needs an earlier approved master: {decode(payload, encoding)}')
                continue
            ident = decode(values.get('NAME'), encoding)
            if not ident:
                raise ExportError(f'{plugin.path.name}: {tag} record has no ID')
            key = (tag, ident.casefold())
            previous = winners.get(key)
            origin = previous.origin_world if previous else plugin.world
            # Retain tombstones until all plugins are loaded, so later undeletes
            # keep the original world's provenance.
            winners[key] = Record(tag, fields, plugin, origin)
        loaded.add(plugin.path.name.casefold())
    return {key: record for key, record in winners.items() if 'DELE' not in dict(record.fields)}


class Formatter:
    def __init__(self, winners, versions, encoding='cp1252'):
        self.winners, self.versions, self.encoding = winners, versions, encoding
        self.gmsts = {key[1]: decode(dict(record.fields).get('STRV'), encoding)
                      for key, record in winners.items() if key[0] == 'GMST'}
        self.enchantments = {}

    def effect_base(self, ident, skill, attribute):
        gmst = choice(EFFECT_GMSTS, ident, 'magic effect')
        name = self.gmsts.get(gmst)
        if not name:
            raise ExportError(f'Missing effect display name GMST: {gmst} (effect {ident})')
        return {'effectId': ident, 'name': name,
                'skill': choice(SKILLS, skill, 'skill') if ident in SKILL_EFFECTS else None,
                'attribute': choice(ATTRIBUTES, attribute, 'attribute') if ident in ATTRIBUTE_EFFECTS else None}

    def effect(self, data):
        ident, skill, attribute, target, area, duration, low, high = unpack('Hbb5i', data)
        # Preserve the stored endpoints, even when reversed. Bloodmoon's
        # shadowstrike_en, for example, stores effect 40 as min=200, max=100.
        # This exports definitions; it does not repair or simulate game data.
        return self.effect_base(ident, skill, attribute) | {
            'range': choice(('self', 'touch', 'target'), target, 'effect range'),
            'magnitude': {'min': low, 'max': high}, 'durationSeconds': duration, 'areaFeet': area}

    def enchantment(self, ident):
        if not ident:
            return None
        key = ident.casefold()
        if key not in self.enchantments:
            record = self.winners.get(('ENCH', key))
            if record is None:
                raise ExportError(f'Unresolved enchantment {ident!r}')
            data = dict(record.fields)
            kind, cost, charge, flags = unpack('4i', data['ENDT'])
            self.enchantments[key] = {
                'id': decode(data['NAME'], self.encoding),
                'castType': choice(('cast_once', 'when_strikes', 'when_used', 'constant_effect'), kind, 'enchantment'),
                'cost': cost, 'charges': charge, 'autoCalculate': bool(flags & 1),
                'effects': [self.effect(value) for field, value in record.fields if field == 'ENAM']}
        return self.enchantments[key]

    def item(self, record):
        tag, fields = record.tag, record.fields
        data = dict(fields)
        txt = lambda key: decode(data.get(key), self.encoding)
        item = {'id': txt('NAME'), 'name': txt('FNAM'),
                'gameDataVersion': {'world': record.origin_world, 'version': self.versions[record.origin_world]},
                'sourcePlugin': record.source.path.name, 'model': txt('MODL') or None,
                'icon': txt('TEXT' if tag == 'ALCH' else 'ITEX') or None, 'script': txt('SCRI') or None}
        if tag == 'WEAP':
            weight, value, kind, health, speed, reach, capacity, *tail = unpack('fiHHffH6BI', data['WPDT'])
            item.update(type=choice(WEAPONS, kind, 'weapon'), health=health, speed=speed, reach=reach,
                        enchantp=capacity, magical=bool(tail[6] & 1), silver=bool(tail[6] & 2))
            for i, attack in enumerate(('chop', 'slash', 'thrust')):
                low, high = tail[2*i:2*i+2]
                item[attack] = {'min': low, 'max': high}
        elif tag in ('ARMO', 'CLOT'):
            if tag == 'ARMO':
                kind, weight, value, health, capacity, armor = unpack('if4i', data['AODT'])
                item.update(health=health, armorRating=armor)
            else:
                kind, weight, value, capacity = unpack('ifHH', data['CTDT'])
            item.update(type=choice(ARMOR if tag == 'ARMO' else CLOTHING, kind, tag), enchantp=capacity)
            parts = []
            for field, payload in fields:
                if field == 'INDX':
                    slot, = unpack('B', payload)
                    parts.append({'slot': slot, 'male': None, 'female': None})
                elif field in ('BNAM', 'CNAM'):
                    if not parts:
                        raise ExportError('Body part reference without INDX')
                    parts[-1]['male' if field == 'BNAM' else 'female'] = decode(payload, self.encoding) or None
            item['bodyParts'] = parts
        elif tag == 'BOOK':
            weight, value, scroll, skill, capacity = unpack('f4i', data['BKDT'])
            item.update(isScroll=bool(scroll), skill=None if skill == -1 else choice(SKILLS, skill, 'book skill'),
                        enchantp=capacity, text=txt('TEXT'))
        elif tag == 'ALCH':
            weight, value, flags = unpack('fii', data['ALDT'])
            item.update(autoCalculate=bool(flags & 1), effects=[self.effect(v) for k, v in fields if k == 'ENAM'])
        elif tag == 'INGR':
            weight, value, *values = unpack('f13i', data['IRDT'])
            item['effects'] = [dict(slot=i, **self.effect_base(values[i], values[i+4], values[i+8]))
                               for i in range(4) if values[i] != -1]
        elif tag == 'APPA':
            kind, quality, weight, value = unpack('iffi', data['AADT'])
            item.update(type=choice(('mortar_and_pestle', 'alembic', 'calcinator', 'retort'), kind, 'apparatus'), quality=quality)
        elif tag in ('LOCK', 'PROB'):
            weight, value, quality, uses = unpack('fifi', data['LKDT' if tag == 'LOCK' else 'PBDT'])
            item.update(quality=quality, uses=uses)
        elif tag == 'REPA':
            weight, value, uses, quality = unpack('fiif', data['RIDT'])
            item.update(quality=quality, uses=uses)
        elif tag == 'LIGH':
            weight, value, duration, radius, color, flags = unpack('fiiiIi', data['LHDT'])
            if not flags & 2:
                return None
            item.update(durationSeconds=duration, radius=radius,
                        color={channel: (color >> (8*i)) & 255 for i, channel in enumerate(('r', 'g', 'b'))},
                        sound=txt('SNAM') or None,
                        flags=[flag for i, flag in enumerate(LIGHT_FLAGS) if flags & (1 << i)])
        elif tag == 'MISC':
            weight, value, key = unpack('fii', data['MCDT'])
            item['isKey'] = bool(key)
        else:
            raise ExportError(f'Unsupported item type {tag}')
        if tag in ('WEAP', 'ARMO', 'CLOT', 'BOOK'):
            item['enchantment'] = self.enchantment(txt('ENAM'))
        item.update(weight=weight, value=value)
        return item


def build_datasets(winners, versions, encoding):
    formatter = Formatter(winners, versions, encoding)
    datasets = {tag: {'$schema': f'./schemas/{name}.schema.json', 'schemaVersion': '1.0.0',
                      'recordType': tag, 'items': []} for tag, name in CATEGORIES.items()}
    for (tag, ident), record in winners.items():
        if tag not in CATEGORIES:
            continue
        try:
            item = formatter.item(record)
        except (ValueError, KeyError, UnicodeError) as exc:
            raise ExportError(f'{record.source.path.name}: {tag} {ident}: {exc}') from exc
        if item is not None:
            datasets[tag]['items'].append(item)
    for dataset in datasets.values():
        dataset['items'].sort(key=lambda item: item['id'].casefold())
    return datasets


def validators():
    # The local directory is optional; normal `pip install -r requirements.txt`
    # installs the dependency into the user's selected Python environment.
    sys.path.append(str(ROOT / '.validation-deps'))
    try:
        from jsonschema import Draft202012Validator
        from referencing import Registry, Resource
    except ImportError as exc:
        raise ExportError('Install dependencies first: python -m pip install -r requirements.txt') from exc
    registry = Registry()
    for path in (ROOT / 'items/schemas').glob('*.json'):
        schema = json.loads(path.read_text(encoding='utf-8'))
        Draft202012Validator.check_schema(schema)
        registry = registry.with_resource(path.as_uri(), Resource.from_contents(schema))
    return {tag: Draft202012Validator({'$ref': (ROOT / f'items/schemas/{name}.schema.json').as_uri()}, registry=registry)
            for tag, name in CATEGORIES.items()}


def publish(datasets, output, report):
    """Stage all files before replacing outputs; each replacement is atomic."""
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.export-', dir=output) as temp:
        stage = Path(temp)
        payloads = {f'{CATEGORIES[tag]}.json': value for tag, value in datasets.items()}
        payloads['export-report.json'] = report
        for filename, value in payloads.items():
            (stage / filename).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
        (output / 'schemas').mkdir(exist_ok=True)
        for path in (ROOT / 'items/schemas').glob('*.json'):
            destination = output / 'schemas' / path.name
            if path.resolve() != destination.resolve():
                destination.write_bytes(path.read_bytes())
        for filename in payloads:
            os.replace(stage / filename, output / filename)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'export_config.json')
    parser.add_argument('--output', type=Path, help='Override output directory')
    parser.add_argument('--list-plugins', action='store_true', help='Print approved active plugins; do not parse or export')
    args = parser.parse_args(argv)
    try:
        settings = json.loads(args.config.read_text(encoding='utf-8-sig'))
        plugins, ignored, encoding = select_plugins(settings)
        for plugin in plugins:
            print(f'[{plugin.world}] {plugin.path}')
        if ignored:
            print('Excluded content (outside scope or scripts): ' + ', '.join(ignored))
        if args.list_plugins:
            return 0
        checks = validators()
        winners = load_plugins(plugins, encoding)
        datasets = build_datasets(winners, settings['versions'], encoding)
        for tag, dataset in datasets.items():
            errors = sorted(checks[tag].iter_errors(dataset), key=lambda error: str(error.path))
            if errors:
                error = errors[0]
                raise ExportError(f'{CATEGORIES[tag]} schema error at {list(error.path)}: {error.message}')
        output = args.output or args.config.resolve().parent / settings['outputDirectory']
        output = output.resolve()
        # Prevent accidental writes into either of the user's game-data trees.
        for protected in (Path(settings['baseDataDirectory']), Path(settings['modsDirectory'])):
            if output.is_relative_to(protected.resolve()):
                raise ExportError(f'Output cannot be inside game data: {output}')
        counts = {CATEGORIES[tag]: len(value['items']) for tag, value in datasets.items()}
        report = {'versions': settings['versions'], 'encoding': encoding,
                  'plugins': [{'path': str(p.path), 'world': p.world} for p in plugins],
                  'excludedContent': ignored, 'counts': counts}
        publish(datasets, output, report)
        for name, count in counts.items():
            print(f'{name}.json: {count} items')
        print(f'Export complete: {output.resolve()}')
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(f'Export failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
