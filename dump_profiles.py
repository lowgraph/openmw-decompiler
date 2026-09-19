"""Run OpenMW once per profile and capture each one's magic effect table.

The engine's effect list depends on what is loaded, and Tamriel Rebuilt registers
extra effects through Lua rather than through a plugin record. A single dump therefore
describes one load order, not the project. This launches OpenMW for each profile with
that profile's own content, using `--replace=content` so nothing from openmw.cfg leaks
in, and `--data` pointing at openmw_effect_dump so nothing has to be installed.

The game window opens, prints, and is closed from here as soon as the dump reaches the
log. Nothing is written to the game's configuration, and no save is touched.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from export_items import ExportError
from extract_foundation import ROOT, load_config
from import_effect_flags import MARKER, build as import_flags

MOD = ROOT/'openmw_effect_dump'
CONTENT = 'silt_effect_dump.omwscripts'
# The line the mod prints last. Seeing it means the whole table is in the log.
COMPLETE = MARKER + ' END '
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
    return list(profile['plugins']) + list(profile.get('runtimeContent') or []) + [CONTENT]


def command_for(openmw, profile, mod=MOD):
    """The dump mod comes in on --data, so nothing has to be installed anywhere."""
    return ([str(openmw), '--replace=content', f'--data={mod}']
            + [f'--content={name}' for name in content_for(profile)]
            + ['--no-sound'])


def said(noise):
    """The last thing OpenMW printed, for an error that would otherwise say nothing."""
    try:
        tail = Path(noise).read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        return ''
    return f'\n  It last said: {tail[-400:]}' if tail else ''


def dumped(log, since):
    """True once this run's log holds a complete block.

    OpenMW truncates the log when it starts, so a file written since launch belongs to
    this run, and an END line in it is this run's.
    """
    if not log.is_file() or log.stat().st_mtime <= since:
        return False
    try:
        return COMPLETE in log.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return False


def run_profile(openmw, profile, log, timeout, mod=MOD, poll=1.0):
    """Launch, wait for the dump, then close the game. Returns seconds elapsed.

    The game's own output goes to a file rather than a pipe. OpenMW writes a great deal
    of it while starting, and a pipe nobody drains fills in about a second; the engine
    then blocks on that write, which also stops openmw.log growing, so the run looks
    dead in exactly the place we are watching.
    """
    identifier = profile['id']
    before = log.stat().st_mtime if log.is_file() else 0
    started = time.time()
    handle, noise = tempfile.mkstemp(prefix=f'openmw-{identifier}-', suffix='.txt')
    game = None
    try:
        game = subprocess.Popen(command_for(openmw, profile, mod),
                                stdout=handle, stderr=subprocess.STDOUT)
        while time.time() - started < timeout:
            if dumped(log, before):
                return time.time() - started
            if game.poll() is not None:
                # It exited on its own, so whatever it wrote is all there is.
                if dumped(log, before):
                    return time.time() - started
                raise ExportError(
                    f'OpenMW closed without printing a dump for profile {identifier}.'
                    + said(noise)
                    + '\n  Check that every content file for this profile is present, '
                    + f'and that {mod} holds {CONTENT} and its scripts folder.')
            time.sleep(poll)
        raise ExportError(
            f'No dump appeared within {timeout}s for profile {identifier}. The mod '
            'prints at the main menu, so it should take no longer than the game takes '
            'to start.' + said(noise)
            + f'\n  Check that {mod} holds {CONTENT} and its scripts folder.')
    finally:
        if game is not None and game.poll() is None:
            game.terminate()
            try:
                game.wait(timeout=30)
            except subprocess.TimeoutExpired:
                game.kill()
        os.close(handle)
        # OpenMW starts a crash handler that inherits this file, and Windows keeps the
        # lock a little past the game's own exit. A leftover temp file is not worth
        # losing a good dump over.
        try:
            Path(noise).unlink(missing_ok=True)
        except OSError:
            pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', action='append', choices=['vanilla', 'tr', 'tr_arce'])
    parser.add_argument('--openmw', type=Path)
    parser.add_argument('--mod', type=Path, default=MOD, help='The dump mod to load')
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
        if not (args.mod/CONTENT).is_file():
            raise ExportError(f'{args.mod/CONTENT} is missing; pass --mod with the path to '
                              'the openmw_effect_dump folder')
        if args.dry_run:
            for profile in chosen:
                printable = ' '.join(f'"{part}"' if ' ' in part else part
                                     for part in command_for(openmw, profile, args.mod))
                print(f'{profile["id"]}:\n  {printable}')
            return 0
        print(f'Using {openmw}\nReading {log}\n', flush=True)
        for profile in chosen:
            print(f'{profile["id"]}: launching OpenMW with '
                  f'{len(content_for(profile))} content files...', flush=True)
            elapsed = run_profile(openmw, profile, log, args.timeout, args.mod)
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
