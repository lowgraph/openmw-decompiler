import contextlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import dump_profiles

from dump_profiles import AUTO_CONTENT, content_for, find_openmw, run_profile
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
                          AUTO_CONTENT])

    def test_a_profile_with_no_lua_content_still_gets_the_dump(self):
        self.assertEqual(content_for({'id': 'vanilla', 'plugins': ['Morrowind.esm']}),
                         ['Morrowind.esm', AUTO_CONTENT])

    def test_the_load_order_is_not_reordered(self):
        # OpenMW applies content in the order given; sorting it would change the game.
        ordered = {'id': 'x', 'plugins': ['Z.esm', 'A.esp', 'M.esp']}
        self.assertEqual(content_for(ordered)[:3], ['Z.esm', 'A.esp', 'M.esp'])


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


class RunTests(unittest.TestCase):
    """The driver decides a run failed from the log, not from the exit code.

    OpenMW returns 0 when it closes for reasons of its own, so a log that did not
    move is the only reliable sign that the dump never printed.
    """
    def setUp(self):
        self.log = Path(tempfile.mkdtemp())/'openmw.log'

    @contextlib.contextmanager
    def launching(self, behaviour):
        real = dump_profiles.subprocess.run
        dump_profiles.subprocess.run = behaviour
        try:
            yield
        finally:
            dump_profiles.subprocess.run = real

    @staticmethod
    def quietly(*_, **__):
        return subprocess.CompletedProcess([], 0, stdout='', stderr='')

    def test_a_log_that_did_not_move_is_an_error(self):
        self.log.write_text('from an older run', encoding='utf-8')
        with self.launching(self.quietly), self.assertRaises(ExportError) as caught:
            run_profile(Path('openmw.exe'), PROFILE, self.log, 60)
        self.assertIn('no new log', str(caught.exception))
        self.assertIn('tr', str(caught.exception))

    def test_a_missing_log_is_an_error_rather_than_an_empty_dump(self):
        with self.launching(self.quietly), self.assertRaises(ExportError):
            run_profile(Path('openmw.exe'), PROFILE, self.log, 60)

    def test_what_openmw_complained_about_is_repeated_back(self):
        def failing(*_, **__):
            return subprocess.CompletedProcess([], 1, stdout='',
                                               stderr='could not find Tamriel_Data.esm')
        with self.launching(failing), self.assertRaises(ExportError) as caught:
            run_profile(Path('openmw.exe'), PROFILE, self.log, 60)
        self.assertIn('Tamriel_Data.esm', str(caught.exception))

    def test_a_fresh_log_is_accepted(self):
        self.log.write_text('old', encoding='utf-8')
        os.utime(self.log, (0, 0))

        def writing(*_, **__):
            self.log.write_text('SILTDUMP BEGIN', encoding='utf-8')
            return subprocess.CompletedProcess([], 0, stdout='', stderr='')
        with self.launching(writing):
            self.assertGreaterEqual(run_profile(Path('openmw.exe'), PROFILE, self.log, 60), 0)

    def test_a_timeout_says_what_to_check(self):
        def slow(*_, **__):
            raise subprocess.TimeoutExpired('openmw', 1)
        with self.launching(slow), self.assertRaises(ExportError) as caught:
            run_profile(Path('openmw.exe'), PROFILE, self.log, 1)
        self.assertIn(AUTO_CONTENT, str(caught.exception))


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
