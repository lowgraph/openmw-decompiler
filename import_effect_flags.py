"""Read the engine's magic effect flags out of openmw.log and publish them as facts.

`openmw_effect_dump` prints one JSON object per effect to the log, because OpenMW's
Lua sandbox has no io and its vfs is read-only. This reads the last complete block and
writes it where `build_rules_library.py` can pick it up.

What arrives here is ground truth from the engine, not inference: harmful, targeting,
and whether an effect uses magnitude or duration at all.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile
import time

from export_items import ExportError
from extract_foundation import ROOT, load_config

VERSION = '1.0.0'
SUPPORTED_DUMP = 2
MARKER = 'SILTDUMP'
BEGIN = re.compile(re.escape(MARKER)+r' BEGIN (\d+) (\w+) (\d+)(?: unmapped=(\d+))?\s*$')
END = re.compile(re.escape(MARKER)+r' END (\d+)\s*$')
RECORD = re.compile(re.escape(MARKER)+r' (\{.*\})\s*$')
ERROR = re.compile(re.escape(MARKER)+r' ERROR (\w+) (.*)$')
REQUIRED = ('harmful', 'hasDuration', 'hasMagnitude', 'hasSkill', 'hasAttribute',
            'onSelf', 'onTouch', 'onTarget')
LIKELY_LOGS = (
    Path.home()/'OneDrive/Documents/My Games/OpenMW/openmw.log',
    Path.home()/'Documents/My Games/OpenMW/openmw.log',
)


def find_log(explicit):
    if explicit is not None:
        if not Path(explicit).is_file():
            raise ExportError(f'No log at {explicit}')
        return Path(explicit)
    for candidate in LIKELY_LOGS:
        if candidate.is_file():
            return candidate
    raise ExportError('Could not find openmw.log; pass --log with its path. Tried:\n  '
                      + '\n  '.join(str(p) for p in LIKELY_LOGS))


def parse(text):
    """The last complete block wins, so re-running the game simply supersedes."""
    blocks, current, errors = [], None, []
    for line in text.splitlines():
        line = line.strip()
        if MARKER not in line:
            continue
        # Log lines carry a timestamp and level before the marker.
        line = line[line.index(MARKER):]
        start = BEGIN.match(line)
        if start:
            current = {'dumpVersion': int(start.group(1)), 'context': start.group(2),
                       'declared': int(start.group(3)),
                       'unmapped': int(start.group(4) or 0), 'effects': []}
            continue
        failure = ERROR.match(line)
        if failure:
            errors.append(f'{failure.group(1)}: {failure.group(2)}')
            continue
        finish = END.match(line)
        if finish and current is not None:
            current['ended'] = int(finish.group(1))
            blocks.append(current)
            current = None
            continue
        entry = RECORD.match(line)
        if entry and current is not None:
            try:
                current['effects'].append(json.loads(entry.group(1)))
            except ValueError as exc:
                raise ExportError(f'Malformed dump record in the log: {exc}') from exc
    return blocks, errors


def validate(block):
    if block['dumpVersion'] != SUPPORTED_DUMP:
        raise ExportError(
            f'Unsupported dump version {block["dumpVersion"]}; this tool reads version '
            f'{SUPPORTED_DUMP}. Version 1 keyed effects by their position in the record '
            'list rather than their id, which is off by one. Reinstall the mod from '
            'openmw_effect_dump and run OpenMW again.')
    if not (len(block['effects']) == block['declared'] == block['ended']):
        raise ExportError(f'Truncated dump: {len(block["effects"])} records between a header '
                          f'claiming {block["declared"]} and a footer claiming {block["ended"]}. '
                          'Let OpenMW exit normally so the log is flushed, then rerun.')
    by_index, unmapped = {}, []
    for effect in block['effects']:
        index = effect.get('index')
        if index is None:
            # Added by a Lua mod rather than a plugin, so no engine id exists for it.
            unmapped.append(effect.get('name') or effect.get('id') or '?')
            continue
        if not isinstance(index, int):
            raise ExportError('A dump record has a non-integer index')
        if index in by_index:
            raise ExportError(f'Effect index {index} appears twice in the dump')
        missing = [f for f in REQUIRED if not isinstance(effect.get(f), bool)]
        if missing:
            raise ExportError(f'Effect {index} is missing {", ".join(missing)}; the dump came '
                              'from an OpenMW too old for this tool')
        by_index[index] = effect
    return by_index, unmapped


def build(log, output):
    blocks, errors = parse(Path(log).read_text(encoding='utf-8', errors='replace'))
    if not blocks:
        detail = ('\n  The mod reported: ' + '; '.join(errors)) if errors else (
            '\n  Enable silt_effect_dump.omwscripts in the launcher, run OpenMW, and quit.')
        raise ExportError(f'No complete effect dump in {log}.{detail}')
    block = blocks[-1]
    effects, unmapped = validate(block)
    payload = {'schemaVersion': VERSION, 'effects': len(effects),
               'luaAdded': sorted(unmapped),
               'source': {'tool': 'openmw_effect_dump', 'dumpVersion': block['dumpVersion'],
                          'context': block['context'], 'log': str(Path(log).resolve()),
                          'blocksFound': len(blocks), 'capturedAtUnix': time.time()},
               'coverage': 'Read from the running engine through its Lua API, so these are '
                           'facts rather than inferences. Display units are not among them: '
                           'OpenMW decides those in its interface, not in the effect record. '
                           'luaAdded lists effects a Lua mod registered at runtime; they have '
                           'no engine id and appear in no plugin file, so nothing can join '
                           'them to a catalog.',
               'records': [effects[i] for i in sorted(effects)]}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    destination = output/'effect-flags.json'
    handle, staging = tempfile.mkstemp(prefix='.flags-', dir=output)
    os.close(handle)
    Path(staging).write_text(json.dumps(payload, ensure_ascii=False, indent=1)+'\n',
                             encoding='utf-8')
    os.replace(staging, destination)
    return destination, payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, help='openmw.log; found automatically when omitted')
    parser.add_argument('--output', type=Path, help='Defaults to the configured output root')
    args = parser.parse_args(argv)
    try:
        root = load_config(ROOT/'foundation_config.json')[2]
        log = find_log(args.log)
        destination, payload = build(log, args.output or root)
        harmful = sum(1 for r in payload['records'] if r['harmful'])
        if payload['luaAdded']:
            print(f'{len(payload["luaAdded"])} effects were added by Lua mods and carry no '
                  f'engine id, so they are recorded but not joinable:\n  '
                  + ', '.join(payload['luaAdded'][:8])
                  + (' ...' if len(payload['luaAdded']) > 8 else ''), flush=True)
        print(f'Read {payload["effects"]} effects from {log}\n'
              f'  context: {payload["source"]["context"]}, '
              f'{payload["source"]["blocksFound"]} dump block(s) in the log\n'
              f'  {harmful} harmful, '
              f'{sum(1 for r in payload["records"] if not r["hasMagnitude"])} without magnitude, '
              f'{sum(1 for r in payload["records"] if not r["hasDuration"])} without duration\n'
              f'Written: {destination}', flush=True)
        return 0
    except (ValueError, KeyError, OSError) as exc:
        print(f'Effect flag import failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
