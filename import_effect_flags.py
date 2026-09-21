"""Read the engine's magic effect flags out of openmw.log and publish them as facts.

`openmw_effect_dump` prints one JSON object per effect to the log, because OpenMW's
Lua sandbox has no io and its vfs is read-only. This reads the last complete block and
writes it where `build_rules_library.py` can pick it up.

What arrives here is ground truth from the engine, not inference: harmful, targeting,
and whether an effect uses magnitude or duration at all.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

from export_items import ExportError
from extract_foundation import (ROOT, extracted_snapshot, extraction_versions, label_carries,
                                load_config, openmw_version)

VERSION = '1.0.0'
# Every version published id and name; only the numeric index was ever wrong, and
# nothing reads it now, so an older log is still usable.
SUPPORTED_DUMPS = (1, 2, 3)
MARKER = 'SILTDUMP'
BEGIN = re.compile(re.escape(MARKER)+r' BEGIN (\d+) (\w+) (\d+)(?:\s+\S+)*\s*$')
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
                       'declared': int(start.group(3)), 'effects': []}
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
    if block['dumpVersion'] not in SUPPORTED_DUMPS:
        raise ExportError(
            f'Unsupported dump version {block["dumpVersion"]}; this tool reads '
            f'{", ".join(str(v) for v in SUPPORTED_DUMPS)}. Reinstall the mod from '
            'openmw_effect_dump and run OpenMW again.')
    if not (len(block['effects']) == block['declared'] == block['ended']):
        raise ExportError(f'Truncated dump: {len(block["effects"])} records between a header '
                          f'claiming {block["declared"]} and a footer claiming {block["ended"]}. '
                          'Let OpenMW exit normally so the log is flushed, then rerun.')
    by_id, names = {}, Counter()
    for effect in block['effects']:
        ident = effect.get('id')
        if not isinstance(ident, str) or not ident:
            raise ExportError('A dump record has no id')
        if ident in by_id:
            raise ExportError(f'Effect id {ident!r} appears twice in the dump')
        missing = [f for f in REQUIRED if not isinstance(effect.get(f), bool)]
        if missing:
            raise ExportError(f'Effect {ident!r} is missing {", ".join(missing)}; the dump came '
                              'from an OpenMW too old for this tool')
        by_id[ident] = effect
        names[effect.get('name')] += 1
    # Effects join on name, so a repeated one cannot be resolved and must be visible.
    return by_id, sorted(n for n, count in names.items() if count > 1)


def dump_provenance(root, config, source, openmw):
    """What a dump about to be taken belongs to: the current extraction, and the engine that
    will run. The rules step compares the first with its catalogs, so a dump left over from
    an older extraction is refused there instead of quietly merged."""
    snapshot = extracted_snapshot(root, config, source)
    running = openmw_version(openmw)
    labelled = extraction_versions(root).get('vanilla', '')
    if not label_carries(labelled, running):
        raise ExportError(f'OpenMW reports {running}, but the extraction is labelled '
                          f'{labelled!r}.\n  Update versions.vanilla in export_config.json '
                          'and run extract_foundation.py first.')
    return {'snapshotId': snapshot, 'openmwVersion': running}


def build(log, output, profile=None, provenance=None):
    blocks, errors = parse(Path(log).read_text(encoding='utf-8', errors='replace'))
    if not blocks:
        detail = ('\n  The mod reported: ' + '; '.join(errors)) if errors else (
            '\n  Enable silt_effect_dump.omwscripts in the launcher, run OpenMW, and quit.')
        raise ExportError(f'No complete effect dump in {log}.{detail}')
    block = blocks[-1]
    effects, ambiguous = validate(block)
    payload = {'schemaVersion': VERSION, 'profile': profile, 'effects': len(effects),
               'ambiguousNames': ambiguous,
               'source': {'tool': 'openmw_effect_dump', 'dumpVersion': block['dumpVersion'],
                          'context': block['context'], 'log': str(Path(log).resolve()),
                          'blocksFound': len(blocks), 'capturedAtUnix': time.time(),
                          **(provenance or {})},
               'coverage': 'Read from the running engine through its Lua API, so these are '
                           'facts rather than inferences. Display units are not among them: '
                           'OpenMW decides those in its interface, not in the effect record. '
                           'Effects join to a catalog on name; ambiguousNames lists any the '
                           'dump repeats, which cannot be resolved. The dump reflects the '
                           'load order it ran under, so it can contain effects a Lua mod '
                           'registered that no plugin file defines.',
               'records': [effects[i] for i in sorted(effects)]}
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    # One file per profile when we know which; the engine's list depends on the load order.
    destination = output/(f'{profile}.json' if profile else 'effect-flags.json')
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
    parser.add_argument('--profile', choices=['vanilla', 'tr', 'tr_arce'],
                        help='Write <root>/effect-flags/<profile>.json for this profile')
    args = parser.parse_args(argv)
    try:
        config, source, root = load_config(ROOT/'foundation_config.json')
        log = find_log(args.log)
        output = args.output or (root/'effect-flags' if args.profile else root)
        # The log came from whichever OpenMW you ran; the configured one is assumed.
        provenance = dump_provenance(root, config, source, source['openmwExecutable'])
        destination, payload = build(log, output, args.profile, provenance)
        harmful = sum(1 for r in payload['records'] if r['harmful'])
        if payload['ambiguousNames']:
            print(f'{len(payload["ambiguousNames"])} effect names are used more than once and '
                  f'cannot be joined by name: ' + ', '.join(payload['ambiguousNames'][:8]),
                  flush=True)
        print(f'Read {payload["effects"]} effects from {log}\n'
              f'  context: {payload["source"]["context"]}, '
              f'{payload["source"]["blocksFound"]} dump block(s) in the log\n'
              f'  {harmful} harmful, '
              f'{sum(1 for r in payload["records"] if not r["hasMagnitude"])} without magnitude, '
              f'{sum(1 for r in payload["records"] if not r["hasDuration"])} without duration\n'
              f'Written: {destination}', flush=True)
        return 0
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f'Effect flag import failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
