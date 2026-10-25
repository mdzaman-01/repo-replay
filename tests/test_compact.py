import unittest

from repo_replay.compact import batch_commits, build_payload, filter_commits, is_excluded, merge_commits
from repo_replay.gitlog import Commit, FileChange


def c(author, ts, *changes, msg="m"):
    return Commit("sha", author, ts, msg, 1, [FileChange(*ch) for ch in changes])


class ExcludeTests(unittest.TestCase):
    def test_matches_basename_and_path(self):
        pats = ["package-lock.json", "vendor/*", "*.min.js"]
        self.assertTrue(is_excluded("web/package-lock.json", pats))
        self.assertTrue(is_excluded("vendor/lib/x.py", pats))
        self.assertTrue(is_excluded("static/app.min.js", pats))
        self.assertFalse(is_excluded("src/app.py", pats))

    def test_filter_drops_commits_left_empty(self):
        commits = [c("a", 1, ("package-lock.json", "M")), c("a", 2, ("package-lock.json", "M"), ("x.py", "A"))]
        out = filter_commits(commits, ["package-lock.json"])
        self.assertEqual(len(out), 1)
        self.assertEqual([ch.path for ch in out[0].changes], ["x.py"])


class MergeTests(unittest.TestCase):
    def ops(self, *per_commit):
        group = [c("a", i, ("f.py", op, 1, 0)) for i, op in enumerate(per_commit)]
        merged = merge_commits(group)
        return {ch.path: ch.op for ch in merged.changes}

    def test_created_then_deleted_is_invisible(self):
        self.assertEqual(self.ops("A", "M", "D"), {})

    def test_created_then_edited_is_created(self):
        self.assertEqual(self.ops("A", "M"), {"f.py": "A"})

    def test_edited_then_deleted_is_deleted(self):
        self.assertEqual(self.ops("M", "D"), {"f.py": "D"})

    def test_deleted_then_recreated_is_modified(self):
        self.assertEqual(self.ops("D", "A"), {"f.py": "M"})

    def test_lines_are_summed_and_top_author_wins(self):
        group = [c("a", 1, ("f", "A", 5, 1)), c("b", 2, ("f", "M", 3, 2)), c("b", 3, ("g", "A", 1, 0))]
        merged = merge_commits(group)
        by = {ch.path: ch for ch in merged.changes}
        self.assertEqual((by["f"].added, by["f"].deleted), (8, 3))
        self.assertEqual((merged.author, merged.ts, merged.weight), ("b", 3, 3))


class BatchTests(unittest.TestCase):
    def test_small_history_untouched(self):
        commits = [c("a", i, ("f%d" % i, "A")) for i in range(5)]
        self.assertEqual(len(batch_commits(commits, 10)), 5)
        self.assertEqual(len(batch_commits(commits, 0)), 5)

    def test_limit_is_respected_and_weights_add_up(self):
        commits = [c("a", i, ("f%d" % i, "A")) for i in range(100)]
        out = batch_commits(commits, 20)
        self.assertLessEqual(len(out), 20)
        self.assertEqual(sum(x.weight for x in out), 100)
        self.assertEqual(sum(len(x.changes) for x in out), 100)


class PayloadTests(unittest.TestCase):
    def test_structure_and_indices(self):
        commits = [c("Ada", 10, ("a.py", "A", 3, 0), ("b.py", "A", 1, 0), msg="one"),
                   c("Bob", 20, ("a.py", "M", 2, 1), ("b.py", "D", 0, 1), msg="two")]
        p = build_payload(commits, "demo", 2)
        self.assertEqual(p["files"], ["a.py", "b.py"])
        self.assertEqual(p["authors"], ["Ada", "Bob"])
        self.assertEqual(p["commits"][0], [10, 0, "one", [[0, 0, 3, 0], [1, 0, 1, 0]]])
        self.assertEqual(p["commits"][1][3], [[0, 1, 2, 1], [1, 2, 0, 1]])
        self.assertEqual(p["totalCommits"], 2)

    def test_anonymize_hides_names(self):
        p = build_payload([c("Ada", 1, ("a", "A")), c("Bob", 2, ("a", "M"))], "r", 2, anonymize=True)
        self.assertEqual(p["authors"], ["Contributor 1", "Contributor 2"])

    def test_long_subject_is_truncated(self):
        p = build_payload([c("a", 1, ("x", "A"), msg="y" * 500)], "r", 1)
        self.assertLessEqual(len(p["commits"][0][2]), 120)

    def test_weight_only_stored_when_merged(self):
        merged = merge_commits([c("a", 1, ("x", "A")), c("a", 2, ("y", "A"))])
        p = build_payload([merged, c("a", 3, ("z", "A"))], "r", 3)
        self.assertEqual(p["commits"][0][4], 2)
        self.assertEqual(len(p["commits"][1]), 4)


if __name__ == "__main__":
    unittest.main()
