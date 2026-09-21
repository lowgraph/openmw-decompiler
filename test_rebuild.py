from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest

from export_items import ExportError
from rebuild import ROOT, run, select, steps

SITE = 'A:/Claude/morrowind-tools'


def step(name, code):
    """A fake step: a Python one-liner run as a real process."""
    return (name, name, [sys.executable, '-c', code], Path(tempfile.gettempdir()))


def quietly(plan, log=None):
    log = log or Path(tempfile.mkdtemp())/'rebuild.log'
    out = io.StringIO()
    with redirect_stdout(out):
        code = run(plan, log, dict(os.environ))
    return code, out.getvalue(), log


class PlanTests(unittest.TestCase):
    def test_rebuild_md_lists_exactly_what_the_runner_runs(self):
        # Two copies of one list drift; this is the thing that stops them.
        text = (ROOT/'REBUILD.md').read_text(encoding='utf-8')
        block = next(chunk for chunk in text.split('```powershell\n')[1:]
                     if chunk.startswith('python extract_foundation.py'))
        documented = block.split('```')[0].strip().splitlines()
        names = [s[0] for s in steps(SITE)]
        shown = [s[1] for s in steps(SITE)][names.index('extract'):names.index('stage') + 1]
        self.assertEqual(documented, shown)

    def test_tests_come_first_and_verification_last(self):
        names = [s[0] for s in steps(SITE)]
        self.assertEqual(names[0], 'tests')
        self.assertEqual(names[-3:], ['stage', 'check', 'site-tests'])

    def test_from_and_to_select_a_slice(self):
        plan = steps(SITE)
        self.assertEqual([s[0] for s in select(plan, 'rules', 'travel')],
                         ['rules', 'gear-rows', 'travel'])
        self.assertEqual(select(plan, 'site-tests')[0][0], 'site-tests')

    def test_an_unknown_step_is_refused_with_the_real_names(self):
        with self.assertRaises(ExportError) as caught:
            select(steps(SITE), 'gear')
        self.assertIn('gear-rows', str(caught.exception))

    def test_from_after_to_is_refused(self):
        with self.assertRaises(ExportError):
            select(steps(SITE), 'bundle', 'rules')


class RunTests(unittest.TestCase):
    def test_the_first_refusal_stops_the_run_and_names_the_resume(self):
        marker = Path(tempfile.mkdtemp())/'ran'
        plan = [step('first', 'print("one")'),
                step('second', 'import sys; print("refused"); sys.exit(3)'),
                step('third', f'open(r"{marker}", "w").close()')]
        code, said, log = quietly(plan)
        self.assertEqual(code, 3)
        self.assertFalse(marker.exists(), 'a step after the refusal ran')
        self.assertIn('Stopped at second', said)
        self.assertIn('python rebuild.py --from second', said)
        self.assertIn('refused', log.read_text(encoding='utf-8'))

    def test_a_clean_run_reports_every_step(self):
        code, said, log = quietly([step('a', 'print(1)'), step('b', 'print(2)')])
        self.assertEqual(code, 0)
        self.assertIn('Rebuild complete', said)
        self.assertRegex(log.read_text(encoding='utf-8'), r'a\s+0m \d\ds\n\s+b\s+0m')

    def test_a_program_that_cannot_start_stops_the_run(self):
        plan = [('ghost', 'ghost', [str(Path(tempfile.mkdtemp())/'nothing.exe')],
                 Path(tempfile.gettempdir())), step('after', 'print("should not run")')]
        code, said, _ = quietly(plan)
        self.assertEqual(code, 1)
        self.assertIn('Could not start ghost', said)
        self.assertNotIn('should not run', said)

    def test_output_that_is_not_utf8_is_kept_rather_than_crashing(self):
        plan = [step('bytes', 'import sys; sys.stdout.buffer.write(b"caf\\xe9\\n")')]
        code, _, log = quietly(plan)
        self.assertEqual(code, 0)
        self.assertIn('caf\ufffd', log.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
