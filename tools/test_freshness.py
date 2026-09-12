"""Tests for evidence freshness against the commit a run measured.

A report with no date on its evidence is trusted for as long as somebody
leaves the tab open. Naming the commit the run measured, and how far the
working tree has moved since, is what makes a reader re-run instead of
believing a month-old number.
"""
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freshness  # noqa: E402


def git(root, *args):
    subprocess.run(["git", "-C", root] + list(args),
                   check=True, capture_output=True, text=True)


def repo_with_commits(n):
    root = tempfile.mkdtemp()
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t.test")
    git(root, "config", "user.name", "t")
    refs = []
    for index in range(n):
        with open(os.path.join(root, "f.txt"), "w", encoding="utf-8") as handle:
            handle.write(str(index))
        git(root, "add", "f.txt")
        git(root, "commit", "-q", "-m", "c%d" % index)
        refs.append(subprocess.run(
            ["git", "-C", root, "rev-parse", "--short=12", "HEAD"],
            capture_output=True, text=True, check=True).stdout.strip())
    return root, refs


class TestFreshness(unittest.TestCase):
    def test_evidence_taken_at_head_is_fresh(self):
        root, refs = repo_with_commits(1)
        state = freshness.measure(root, refs[-1])
        self.assertEqual(state["state"], "fresh")
        self.assertEqual(state["commits_since"], 0)
        self.assertIn(refs[-1], state["note"])

    def test_evidence_behind_head_counts_the_commits_since(self):
        root, refs = repo_with_commits(4)
        state = freshness.measure(root, refs[0])
        self.assertEqual(state["state"], "stale")
        self.assertEqual(state["commits_since"], 3)
        self.assertIn("3 commit", state["note"])

    def test_a_dirty_tree_is_never_reported_as_fresh(self):
        root, refs = repo_with_commits(1)
        with open(os.path.join(root, "f.txt"), "a", encoding="utf-8") as handle:
            handle.write("edit")
        state = freshness.measure(root, refs[-1])
        self.assertTrue(state["dirty"])
        self.assertEqual(state["state"], "stale")
        self.assertIn("uncommitted", state["note"])

    def test_a_ref_this_repository_does_not_have_is_unknown_not_stale(self):
        root, _ = repo_with_commits(1)
        state = freshness.measure(root, "0" * 12)
        self.assertEqual(state["state"], "unknown")
        self.assertIsNone(state["commits_since"])

    def test_outside_a_checkout_nothing_is_claimed(self):
        state = freshness.measure(tempfile.mkdtemp(), None)
        self.assertEqual(state["state"], "unknown")
        self.assertIn("not a git", state["note"].lower())


if __name__ == "__main__":
    unittest.main()
