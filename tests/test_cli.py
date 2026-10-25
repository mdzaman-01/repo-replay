import json
import os
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO

from repo_replay.cli import main, name_from_url, resolve_source
from tests.helpers import make_repo


def read_payload(path):
    with open(path, encoding="utf-8") as fh:
        html = fh.read()
    m = re.search(r'<script type="application/json" id="replay-data">(.*?)</script>', html, re.S)
    assert m, "data block not found"
    return html, json.loads(m.group(1))


class CliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = make_repo()
        cls.out_dir = tempfile.mkdtemp(prefix="replay-out-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo, ignore_errors=True)
        shutil.rmtree(cls.out_dir, ignore_errors=True)

    def run_cli(self, *args):
        err = StringIO()
        with redirect_stderr(err):
            code = main(list(args))
        return code, err.getvalue()

    def test_end_to_end_writes_a_self_contained_page(self):
        out = os.path.join(self.out_dir, "a.html")
        code, _ = self.run_cli(self.repo, "-o", out, "-q")
        self.assertEqual(code, 0)
        html, payload = read_payload(out)
        self.assertEqual(len(payload["commits"]), 4)
        self.assertTrue(payload["hasLines"])
        # self-contained: no external requests of any kind
        self.assertNotIn("src=\"http", html)
        self.assertNotIn("href=\"http://", html)
        self.assertNotRegex(html, r"<link[^>]+stylesheet")

    def test_lockfiles_excluded_by_default_and_includable(self):
        out = os.path.join(self.out_dir, "b.html")
        self.run_cli(self.repo, "-o", out, "-q")
        self.assertNotIn("package-lock.json", read_payload(out)[1]["files"])
        self.run_cli(self.repo, "-o", out, "-q", "--no-default-excludes")
        self.assertIn("package-lock.json", read_payload(out)[1]["files"])

    def test_script_tag_in_commit_message_cannot_break_the_page(self):
        out = os.path.join(self.out_dir, "c.html")
        self.run_cli(self.repo, "-o", out, "-q")
        html, payload = read_payload(out)
        self.assertIn("Fix </script><b>bold</b> edge case", [r[2] for r in payload["commits"]])
        self.assertEqual(html.count("</script>"), 3)  # config, data, player: nothing injected

    def test_title_is_escaped(self):
        out = os.path.join(self.out_dir, "d.html")
        self.run_cli(self.repo, "-o", out, "-q", "--title", "<b>x</b> & __DATA__")
        with open(out, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("<title>&lt;b&gt;x&lt;/b&gt; &amp; __DATA__</title>", html)

    def test_anonymize_and_no_lines(self):
        out = os.path.join(self.out_dir, "e.html")
        self.run_cli(self.repo, "-o", out, "-q", "--anonymize", "--no-lines")
        _, payload = read_payload(out)
        self.assertEqual(payload["authors"], ["Contributor 1", "Contributor 2", "Contributor 3"][: len(payload["authors"])])
        self.assertFalse(payload["hasLines"])

    def test_max_commits_merges_steps(self):
        out = os.path.join(self.out_dir, "f.html")
        self.run_cli(self.repo, "-o", out, "-q", "--max-commits", "2")
        _, payload = read_payload(out)
        self.assertLessEqual(len(payload["commits"]), 2)
        self.assertEqual(payload["totalCommits"], 4)

    def test_not_a_repo(self):
        code, err = self.run_cli(self.out_dir, "-o", os.path.join(self.out_dir, "x.html"))
        self.assertEqual(code, 2)
        self.assertIn("not a git repository", err)

    def test_unusable_source(self):
        code, err = self.run_cli("not a real thing!!")
        self.assertEqual(code, 2)

    def test_empty_range_is_a_clear_error(self):
        code, err = self.run_cli(self.repo, "--since", "2100-01-01", "-o", os.path.join(self.out_dir, "g.html"))
        self.assertEqual(code, 1)
        self.assertIn("no commits", err)

    def test_clone_from_url(self):
        out = os.path.join(self.out_dir, "h.html")
        code, _ = self.run_cli("file://" + self.repo, "-o", out, "-q")
        self.assertEqual(code, 0)
        _, payload = read_payload(out)
        self.assertEqual(len(payload["commits"]), 4)
        self.assertFalse(payload["hasLines"])  # URLs skip line counts for speed


class SourceTests(unittest.TestCase):
    def test_resolve(self):
        self.assertEqual(resolve_source("owner/name"), ("https://github.com/owner/name.git", True))
        self.assertEqual(resolve_source("https://example.com/a/b.git"), ("https://example.com/a/b.git", True))
        self.assertEqual(resolve_source(tempfile.gettempdir()), (tempfile.gettempdir(), False))
        with self.assertRaises(ValueError):
            resolve_source("nope nope")

    def test_name_from_url(self):
        self.assertEqual(name_from_url("https://github.com/torvalds/linux.git"), "linux")
        self.assertEqual(name_from_url("git@github.com:me/thing.git"), "thing")


if __name__ == "__main__":
    unittest.main()
