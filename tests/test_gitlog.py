import shutil
import unittest

from repo_replay.gitlog import COMMIT_MARK, FIELD_SEP, GitError, parse_log, read_history, repo_name
from tests.helpers import make_repo


def header(sha, author, ts, parents, subject):
    return COMMIT_MARK + FIELD_SEP.join([sha, author, str(ts), parents, subject])


class ParseLogTests(unittest.TestCase):
    def test_raw_and_numstat_are_merged_per_file(self):
        lines = [
            header("aaa", "Ada", 100, "", "first"),
            "",
            ":000000 100644 0000000 1111111 A\tsrc/a.py",
            ":100644 000000 1111111 0000000 D\told.txt",
            "",
            "5\t0\tsrc/a.py",
            "0\t7\told.txt",
            "-\t-\tlogo.png",
        ]
        (c,) = list(parse_log(lines))
        self.assertEqual((c.author, c.ts, c.message, c.parents), ("Ada", 100, "first", 0))
        by_path = {ch.path: ch for ch in c.changes}
        self.assertEqual((by_path["src/a.py"].op, by_path["src/a.py"].added), ("A", 5))
        self.assertEqual((by_path["old.txt"].op, by_path["old.txt"].deleted), ("D", 7))
        # numstat-only entries (binary files) default to a modification with zero lines
        self.assertEqual((by_path["logo.png"].op, by_path["logo.png"].added), ("M", 0))

    def test_name_status_mode(self):
        lines = [header("bbb", "Grace", 200, "aaa", "second"), "", "A\tx.py", "M\ty.py", "D\tz.py", "T\tt.py"]
        (c,) = list(parse_log(lines))
        self.assertEqual([ch.op for ch in c.changes], ["A", "M", "D", "M"])

    def test_merge_commit_has_no_changes_and_two_parents(self):
        (c,) = list(parse_log([header("ccc", "Ada", 5, "aaa bbb", "Merge branch")]))
        self.assertEqual(c.parents, 2)
        self.assertEqual(c.changes, [])

    def test_ignores_noise_before_first_commit(self):
        self.assertEqual(list(parse_log(["garbage", "", ":100644 100644 a b M\tf"])), [])


class ReadHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = make_repo()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_oldest_first_with_authors(self):
        commits = read_history(self.repo)
        self.assertEqual([c.message for c in commits][:2], ["Initial commit", "Add util, grow app"])
        self.assertEqual(commits[0].author, "Ada Lovelace")
        self.assertEqual(len(commits), 4)
        self.assertEqual(commits[0].ts, 1704103200)

    def test_operations_and_line_counts(self):
        commits = read_history(self.repo)
        first = {ch.path: ch for ch in commits[0].changes}
        self.assertEqual({p: c.op for p, c in first.items()},
                         {"src/app.py": "A", "README.md": "A", "logo.png": "A"})
        self.assertEqual(first["src/app.py"].added, 3)
        self.assertEqual(first["logo.png"].added, 0)  # binary
        second = {ch.path: ch for ch in commits[1].changes}
        self.assertEqual((second["src/app.py"].op, second["src/app.py"].added), ("M", 2))
        third = {ch.path: ch.op for ch in commits[2].changes}
        self.assertEqual(third["README.md"], "D")

    def test_without_lines_still_reports_operations(self):
        commits = read_history(self.repo, with_lines=False)
        self.assertEqual(len(commits), 4)
        self.assertTrue(all(ch.added == 0 for c in commits for ch in c.changes))
        self.assertEqual({ch.path: ch.op for ch in commits[2].changes}["README.md"], "D")

    def test_unicode_author_survives(self):
        self.assertEqual(read_history(self.repo)[-1].author, "Grace H\u00f6pper")

    def test_since_filters_history(self):
        self.assertEqual(len(read_history(self.repo, since="2024-01-03T00:00:00")), 2)

    def test_repo_name(self):
        self.assertTrue(repo_name(self.repo).startswith("replay-test-"))

    def test_not_a_repo_raises(self):
        with self.assertRaises(GitError):
            read_history("/definitely/not/a/repo")


if __name__ == "__main__":
    unittest.main()
