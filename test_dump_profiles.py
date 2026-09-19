import contextlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import dump_profiles
from dump_profiles import CONTENT, command_for, content_for, dumped, find_openmw, run_profile
from export_items import ExportError

PROFILE = {'id': 'tr', 'plugins': ['Morrowind.esm', 'TR_Mainland.esm'],
           'runtimeContent': ['tamrielrebuilt.omwscripts']}


def executable():
    path = Path(tempfile.mkdtemp())/'openmw.exe'
    path.write_bytes(b'')
    return path


class ContentTests(unittest.TestCase):
    def test_plugins_come_first_then_lua_content_then_the_dump(self):
        self.assertEqual(content_for(PROFILE),
                         ['Morrowind.esm', 'TR_Mainland.esm', 'tamrielrebuilt.omwscripts',
                          CONTENT])

    def test_a_profile_with_no_lua_content_still_gets_the_dump(self):
        self.assertEqual(content_for({'id': 'vanilla', 'plugins': ['Morrowind.esm']}),
                         ['Morrowind.esm', CONTENT])

    def test_the_load_order_is_not_reordered(self):
        # OpenMW applies content in the order given; sorting it would change the game.
        ordered = {'id': 'x', 'plugins': ['Z.esm', 'A.esp', 'M.esp']}
        self.assertEqual(content_for(ordered)[:3], ['Z.esm', 'A.esp', 'M.esp'])


class CommandTests(unittest.TestCase):
    def test_the_mod_arrives_on_the_command_line_so_nothing_is_installed(self):
        self.assertIn(f'--data={Path("A:/mod")}',
                      command_for('openmw.exe', PROFILE, Path('A:/mod')))

    def test_the_config_content_list_is_replaced_not_extended(self):
        # Without this the user's own load order leaks in and the dump describes that
        # rather than the profile.
        self.assertIn('--replace=content', command_for('openmw.exe', PROFILE))

    def test_every_content_file_is_passed_separately_and_in_order(self):
        command = command_for('openmw.exe', PROFILE)
        self.assertEqual([part[len('--content='):] for part in command
                          if part.startswith('--content=')], content_for(PROFILE))


class ExecutableTests(unittest.TestCase):
    def test_an_explicit_path_wins(self):
        path = executable()
        self.assertEqual(find_openmw(path, {'openmwExecutable': 'nowhere.exe'}), path)

    def test_the_configured_path_is_used_next(self):
        path = executable()
        self.assertEqual(find_openmw(None, {'openmwExecutable': str(path)}), path)

    def test_a_path_that_is_not_there_is_skipped_rather_than_returned(self):
        missing = Path(tempfile.mkdtemp())/'absent.exe'
        path = executable()
        self.assertEqual(find_openmw(missing, {'openmwExecutable': str(path)}), path)


class CompletionTests(unittest.TestCase):
    """The run ends when the dump lands in the log, not when the game exits."""
    def setUp(self):
        self.log = Path(tempfile.mkdtemp())/'openmw.log'

    def test_a_log_from_before_the_launch_does_not_count(self):
        self.log.write_text('SILTDUMP END 141', encoding='utf-8')
        self.assertFalse(dumped(self.log, self.log.stat().st_mtime))

    def test_a_log_this_run_wrote_counts(self):
        self.log.write_text('SILTDUMP END 141', encoding='utf-8')
        self.assertTrue(dumped(self.log, 0))

    def test_a_half_written_block_does_not_count(self):
        self.log.write_text('SILTDUMP BEGIN 3 menu 141\nSILTDUMP {"id":"one"}',
                            encoding='utf-8')
        self.assertFalse(dumped(self.log, 0))

    def test_a_log_that_is_not_there_does_not_count(self):
        self.assertFalse(dumped(self.log, 0))


class RunTests(unittest.TestCase):
    """Nothing in the mod quits the game, so the driver has to decide when to stop."""
    def setUp(self):
        self.log = Path(tempfile.mkdtemp())/'openmw.log'
        self.spawned = []

    @contextlib.contextmanager
    def launching(self, dumps_after=None, exits_after=None):
        log, spawned = self.log, self.spawned

        class Fake:
            def __init__(self, command, **kwargs):
                self.command, self.kwargs = command, kwargs
                self.polls, self.stopped = 0, None
                spawned.append(self)

            def poll(self):
                self.polls += 1
                if dumps_after is not None and self.polls >= dumps_after:
                    log.write_text('SILTDUMP END 141', encoding='utf-8')
                if self.stopped is not None:
                    return 0
                return 0 if exits_after is not None and self.polls >= exits_after else None

            def terminate(self):
                self.stopped = 'terminate'

            def kill(self):
                self.stopped = 'kill'

            def wait(self, timeout=None):
                return 0

        real = dump_profiles.subprocess.Popen
        dump_profiles.subprocess.Popen = Fake
        try:
            yield
        finally:
            dump_profiles.subprocess.Popen = real

    def run_one(self, timeout=60):
        return run_profile(Path('openmw.exe'), PROFILE, self.log, timeout, poll=0.01)

    def test_a_run_ends_as_soon_as_the_dump_lands(self):
        with self.launching(dumps_after=1):
            self.assertGreaterEqual(self.run_one(), 0)

    def test_the_game_is_closed_afterwards(self):
        with self.launching(dumps_after=1):
            self.run_one()
        self.assertEqual(self.spawned[0].stopped, 'terminate',
                         'the window must not be left open for the next profile')

    def test_the_game_writes_to_a_file_rather_than_a_pipe(self):
        # A pipe nobody drains fills during startup; OpenMW then blocks on the write,
        # which stops openmw.log growing too, and the run looks dead where we watch.
        with self.launching(dumps_after=1):
            self.run_one()
        self.assertIsInstance(self.spawned[0].kwargs['stdout'], int)
        self.assertEqual(self.spawned[0].kwargs['stderr'], subprocess.STDOUT)

    def test_a_game_that_exits_without_dumping_is_an_error(self):
        with self.launching(exits_after=1), self.assertRaises(ExportError) as caught:
            self.run_one()
        self.assertIn('without printing a dump', str(caught.exception))
        self.assertIn('tr', str(caught.exception))

    def test_a_game_that_dumps_and_then_exits_is_still_a_success(self):
        with self.launching(dumps_after=1, exits_after=1):
            self.assertGreaterEqual(self.run_one(), 0)

    def test_a_timeout_says_where_to_look(self):
        with self.launching(), self.assertRaises(ExportError) as caught:
            self.run_one(timeout=0.05)
        self.assertIn(CONTENT, str(caught.exception))


class ShippedModTests(unittest.TestCase):
    def test_the_mod_this_repository_ships_is_the_one_the_driver_loads(self):
        self.assertTrue((dump_profiles.MOD/CONTENT).is_file())
        for script in ('dump.lua', 'menu.lua', 'global.lua'):
            self.assertTrue((dump_profiles.MOD/'scripts'/'silt_effect_dump'/script).is_file(),
                            f'{script} is missing, so --data would load nothing')

    def test_nothing_in_the_mod_quits_the_game(self):
        # core.quit() during script load closed the window at startup, which reads as a
        # crash. The driver closes the game instead, and manual runs are unaffected.
        for script in (dump_profiles.MOD/'scripts'/'silt_effect_dump').glob('*.lua'):
            self.assertNotIn('quit', script.read_text(encoding='utf-8'), script.name)

    def test_every_content_file_the_mod_ships_names_a_script_that_exists(self):
        for content in dump_profiles.MOD.glob('*.omwscripts'):
            for line in content.read_text(encoding='utf-8').splitlines():
                if ':' not in line:
                    continue
                named = line.split(':', 1)[1].strip()
                self.assertTrue((dump_profiles.MOD/named).is_file(),
                                f'{content.name} points at {named}, which is not there')


class ConfigTests(unittest.TestCase):
    def test_every_profile_that_needs_lua_content_declares_it(self):
        # Tamriel Rebuilt registers its 45 extra effects from omwscripts, not from a
        # plugin record, so a profile that omits them dumps vanilla's list.
        config = json.loads((Path(__file__).parent/'foundation_config.json')
                            .read_text(encoding='utf-8'))
        runtime = {p['id']: p.get('runtimeContent') or [] for p in config['profiles']}
        self.assertEqual(runtime['vanilla'], [])
        for profile in ('tr', 'tr_arce'):
            self.assertIn('Tamriel_Data.omwscripts', runtime[profile],
                          f'{profile} would miss the Lua-registered effects')


if __name__ == '__main__':
    unittest.main()
