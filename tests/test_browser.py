"""Optional smoke test: loads a generated page in headless Chromium.

Skipped automatically unless Playwright and a browser are installed:
    pip install playwright && playwright install chromium
"""
import os
import shutil
import tempfile
import unittest

from repo_replay.cli import main
from tests.helpers import make_repo

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "playwright is not installed")
class BrowserSmokeTest(unittest.TestCase):
    def test_page_loads_plays_and_seeks_without_errors(self):
        repo = make_repo()
        out_dir = tempfile.mkdtemp()
        out = os.path.join(out_dir, "page.html")
        try:
            self.assertEqual(main([repo, "-o", out, "-q"]), 0)
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch()
                except Exception as exc:  # browser binary missing
                    self.skipTest(f"chromium unavailable: {exc}")
                page = browser.new_page()
                errors = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto("file://" + out + "#t=1")
                page.wait_for_function("window.__replay && __replay.idx === __replay.N")
                alive = page.evaluate("__replay.files.filter(f => f.alive).length")
                self.assertEqual(alive, 3)  # app.py, util.py, logo.png (README deleted, lockfile excluded)
                page.evaluate("__replay.seek(0)")
                page.wait_for_function("__replay.idx === 0")
                self.assertEqual(page.evaluate("__replay.files.filter(f => f.alive).length"), 0)
                self.assertEqual(errors, [])
                browser.close()
        finally:
            shutil.rmtree(repo, ignore_errors=True)
            shutil.rmtree(out_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
