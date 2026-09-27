"""Scratch folders for the tests, removed when the test run ends.

The suite runs with TEMP pointing at A:\\Cache, and `tempfile.mkdtemp()` never cleans
up after itself: every run used to leave about 174 folders behind, 21,000 by the time
anyone looked. Tests take their scratch folders from here instead.
"""
import atexit
import shutil
import tempfile


def scratch_dir():
    """A fresh temporary folder, deleted with everything in it when the run ends."""
    path = tempfile.mkdtemp()
    atexit.register(shutil.rmtree, path, True)
    return path
