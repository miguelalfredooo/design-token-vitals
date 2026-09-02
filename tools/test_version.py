"""Tests for reproducible skill provenance."""
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import version  # noqa: E402


class TestVersion(unittest.TestCase):
    def test_local_version_changes_with_skill_contents(self):
        root = tempfile.mkdtemp()
        path = os.path.join(root, "SKILL.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("one")
        with mock.patch.object(version, "ROOT", root):
            first = version.local_version()
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("two")
            second = version.local_version()
        self.assertTrue(first.startswith("local-"))
        self.assertNotEqual(first, second)

    def test_describe_uses_local_hash_outside_git(self):
        root = tempfile.mkdtemp()
        with open(os.path.join(root, "SKILL.md"), "w", encoding="utf-8") as handle:
            handle.write("skill")
        with mock.patch.object(version, "ROOT", root), mock.patch.object(version, "git", return_value=None):
            self.assertTrue(version.describe()["version"].startswith("local-"))

    def test_dirty_git_version_changes_with_skill_contents(self):
        root = tempfile.mkdtemp()
        path = os.path.join(root, "SKILL.md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("one")

        def fake_git(*args):
            if args[:2] == ("rev-parse", "--short"):
                return "abc1234"
            if args[:2] == ("describe", "--tags"):
                return "v1.0.0"
            if args[:2] == ("status", "--porcelain"):
                return " M SKILL.md"
            return None

        with mock.patch.object(version, "ROOT", root), mock.patch.object(
                version, "git", side_effect=fake_git):
            first = version.describe()["version"]
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("two")
            second = version.describe()["version"]
        self.assertRegex(first, r"^1\.0\.0\+abc1234\.dirty\.[0-9a-f]{12}$")
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
