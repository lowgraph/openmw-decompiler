"""Rebuild everything in REBUILD.md's order, stopping at the first step that refuses.

Running it unattended is safe because every step already refuses the mistakes that would
make its output wrong: a stale version label, a plugin no profile lists, an effect dump
from another extraction, formulas copied from another engine release. The first refusal
stops the run and says why; nothing after it runs. Fix what it named, then resume from
that step with --from.

    python rebuild.py                  everything, about an hour and a half
    python rebuild.py --from rules     resume at a step
    python rebuild.py --to bundle      stop after a step
    python rebuild.py --list           the steps, in order

The whole run is also written to <root>/rebuild-logs, so a refusal an hour in is still
there to read.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from export_items import ExportError
from extract_foundation import ROOT, load_config

# REBUILD.md prints these same commands, in this order; a test keeps the two identical.
PIPELINE = [
    ('extract', 'extract_foundation.py'),
    ('catalogs', 'build_catalogs.py'),
    ('world', 'build_world_catalog.py'),
    ('journal', 'build_journal_catalog.py'),
    ('acquisition', 'build_acquisition_index.py'),
    ('script-evidence', 'build_script_evidence.py'),
    ('services', 'build_services_catalog.py'),
    ('dump', 'dump_profiles.py'),
    ('rules', 'build_rules_library.py'),
    ('gear-rows', 'build_gear_rows.py'),
    ('travel', 'build_travel_catalog.py'),
    ('quests', 'build_quest_catalog.py'),
    ('merchants', 'build_merchant_catalog.py'),
    ('places', 'build_places_catalog.py'),
    ('factions', 'build_faction_catalog.py'),
    ('best-in-slot', 'build_best_in_slot_catalog.py'),
    ('bundle', 'build_app_bundle.py'),
]


def steps(site):
    """Every step as (name, shown, argv, cwd).

    The code's own tests come first, because a rebuild with broken code publishes broken
    data; the best-in-slot check and the site's tests come last, as REBUILD.md's
    verification does.
    """
    python = sys.executable
    stage = Path(site)/'scripts/stage-game-data.mjs'
    found = [('tests', 'python -B -m unittest discover -s . -p "test_*.py"',
              [python, '-B', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py'], ROOT)]
    found += [(name, f'python {script}', [python, script], ROOT) for name, script in PIPELINE]
    found.append(('stage', f'node {stage}', [shutil.which('node') or 'node', str(stage)], ROOT))
    found.append(('check', 'python build_best_in_slot_catalog.py --check',
                  [python, 'build_best_in_slot_catalog.py', '--check'], ROOT))
    # npm is a .cmd on Windows, which only cmd.exe can run.
    npm = ['cmd', '/d', '/c', 'npm', 'test'] if os.name == 'nt' else ['npm', 'test']
    found.append(('site-tests', 'npm test (in the site)', npm, Path(site)))
    return found


def select(plan, start=None, stop=None):
    """The steps from `start` through `stop`, both by name."""
    names = [step[0] for step in plan]
    for wanted in (start, stop):
        if wanted is not None and wanted not in names:
            raise ExportError(f'No step called {wanted!r}. The steps: ' + ', '.join(names))
    first = names.index(start) if start else 0
    last = names.index(stop) if stop else len(names) - 1
    if first > last:
        raise ExportError(f'--from {start} comes after --to {stop}')
    return plan[first:last + 1]


def duration(seconds):
    return f'{int(seconds // 60)}m {int(seconds % 60):02d}s'


def stream(argv, cwd, env, log):
    """Run one step, echoing its output as it arrives and keeping a copy in the log."""
    with subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT) as child:
        for raw in child.stdout:
            line = raw.decode('utf-8', errors='replace').rstrip('\r\n')
            print(line, flush=True)
            log.write(line + '\n')
        return child.wait()


def run(plan, log_path, env):
    """Run the plan in order and return the first failing exit code, or 0."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timings = []
    with open(log_path, 'w', encoding='utf-8') as log:
        def say(text):
            print(text, flush=True)
            log.write(text + '\n')
            log.flush()

        say(f'Rebuild of {len(plan)} step(s), started {time.strftime("%Y-%m-%d %H:%M")}.'
            f' Log: {log_path}')
        started_all = time.time()
        for index, (name, shown, argv, cwd) in enumerate(plan, 1):
            say(f'\n[{index}/{len(plan)}] {name}: {shown}')
            started = time.time()
            try:
                code = stream(argv, cwd, env, log)
            except KeyboardInterrupt:
                say(f'\nCancelled during {name}. Resume with: python rebuild.py --from {name}')
                return 130
            except OSError as exc:
                say(f'\nCould not start {name}: {exc}')
                code = 1
            timings.append((name, time.time() - started))
            if code:
                say(f'\nStopped at {name} after {duration(timings[-1][1])} (exit {code}). '
                    'The steps before it finished; nothing after it ran.\n'
                    f'Fix what it said above, then resume: python rebuild.py --from {name}')
                return code
        say(f'\nRebuild complete in {duration(time.time() - started_all)}:')
        for name, seconds in timings:
            say(f'  {name:16} {duration(seconds)}')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--from', dest='start', metavar='STEP', help='Resume at this step')
    parser.add_argument('--to', dest='stop', metavar='STEP', help='Stop after this step')
    parser.add_argument('--list', action='store_true', help='Print the steps and exit')
    parser.add_argument('--log', type=Path, help='Defaults to <root>/rebuild-logs/<time>.log')
    args = parser.parse_args(argv)
    # Child output can hold characters the console code page cannot print.
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(errors='replace')
    try:
        _, source, root = load_config(ROOT/'foundation_config.json')
        site = source.get('siteRepository') or 'A:/Claude/morrowind-tools'
        plan = select(steps(site), args.start, args.stop)
        if args.list:
            for name, shown, _, _ in plan:
                print(f'  {name:16} {shown}')
            return 0
        missing = [tool for tool in ('node', 'npm') if shutil.which(tool) is None]
        if missing:
            raise ExportError(f'{" and ".join(missing)} not found; the site steps need them')
        cache = source.get('locationCacheDirectory', 'A:/Cache')
        # Unbuffered and UTF-8, so output arrives line by line and in one encoding; temp
        # files in A:\Cache, as the repository's rules require.
        env = os.environ | {'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8',
                            'TEMP': cache, 'TMP': cache}
        log = args.log or root/'rebuild-logs'/time.strftime('%Y%m%d-%H%M%S.log')
        return run(plan, log, env)
    except (ValueError, KeyError, OSError) as exc:
        print(f'Rebuild could not start: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
