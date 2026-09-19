"""Run OpenMW once per profile and capture each one's magic effect table.

The engine's effect list depends on what is loaded, and Tamriel Rebuilt registers
extra effects through Lua rather than through a plugin record. A single dump therefore
describes one load order, not the project. This launches OpenMW for each profile with
that profile's own content, using `--replace=content` so nothing from openmw.cfg leaks
in, and the auto variant of the mod quits as soon as it has printed.

The game window opens and closes on its own. Nothing is written to the game's
configuration, and no save is touched.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from export_items import ExportError
from extract_foundation import ROOT, load_config
from import_effect_flags import build as import_flags

AUTO_CONTENT = 'silt_effect_dump_auto.omwscripts'
LIKELY_OPENMW = (Path('A:/OpenMW 0.51.0/openmw.exe'),
                 Path('C:/Program Files/OpenMW/openmw.exe'))


def find_openmw(explicit, source):
    for candidate in (explicit, source.get('openmwExecutable'), *LIKELY_OPENMW):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    found = shutil.which('openmw')
    if found:
        return Path(found)
    raise ExportError('Could not find openmw.exe; pass --openmw with its path, or set '
                      'openmwExecutable in export_config.json')


def content_for(profile):
    """Plugins, the Lua content that belongs with them, and the dump itself."""
    return list(profile['plugins']) + list(profile.get('runtimeContent') or []) + [AUTO_CONTENT]


def run_profile(openmw, profile, log, timeout):
    command = [str(openmw), '--replace=content']
    command += [f'--content={name}' for name in content_for(profile)]
    command += ['--no-sound']
    before = log.stat().st_mtime if log.is_file() else 0
    started = time.time()
    try:
        finished = subprocess.run(command, timeout=timeout, capture_output=True, text=True)
    except subprocess.TimeoutExpired as exc:
        raise ExportError(
            f'OpenMW did not exit within {timeout}s for profile {profile["id"]}. It quits '
            f'itself once the dump is printed, so it probably never got there. Check that '
            f'{AUTO_CONTENT} is installed in the data directory, and that every content '
            'file for this profile is present.') from exc
    if not log.is_file() or log.stat().st_mtime <= before:
        raise ExportError(f'OpenMW wrote no new log for profile {profile["id"]}.'
                          + (f'\n  It said: {finished.stderr.strip()[:300]}' if finished.stderr else ''))
    return time.time() - started


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--openmw', type=Path)
    parser.add_argument('--log', type=Path, help='openmw.log; taken from openmw.cfg when omitted')
    parser.add_argument('--output', type=Path, help='Defaults to <root>/effect-flags')
    parser.add_argument('--timeout', type=int, default=600, help='Seconds to allow one run')
    parser.add_argument('--dry-run', action='store_true', help='Print the commands only')
    args = parser.parse_args(argv)
    try:
        config, source, root = load_config(ROOT/'foundation_config.json')
        chosen = [p for p in config['profiles']
                  if not args.profile or p['id'] in args.profile]
        openmw = find_openmw(args.openmw, source)
        log = args.log or Path(source['openmwConfig']).parent/'openmw.log'
        output = args.output or root/'effect-flags'
        if args.dry_run:
            for profile in chosen:
                print(profile['id'] + ':\n  ' + ' '.join(
                    [f'"{openmw}"', '--replace=content']
                    + [f'--content="{n}"' for n in content_for(profile)] + ['--no-sound']))
            return 0
        print(f'Using {openmw}\nReading {log}\n', flush=True)
        for profile in chosen:
            print(f'{profile["id"]}: launching OpenMW with '
                  f'{len(content_for(profile))} content files...', flush=True)
            elapsed = run_profile(openmw, profile, log, args.timeout)
            destination, payload = import_flags(log, output, profile['id'])
            print(f'  {payload["effects"]} effects in {elapsed:.0f}s -> {destination.name}',
                  flush=True)
            if payload['ambiguousNames']:
                print('  names used more than once: ' + ', '.join(payload['ambiguousNames']),
                      flush=True)
        print('\nNow rebuild the rules so they pick these up:\n  python build_rules_library.py')
        return 0
    except KeyboardInterrupt:
        print('\nCancelled.')
        return 130
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(f'Profile dump failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
