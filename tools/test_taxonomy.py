"""Tests for taxonomy.

The list is defined once in code. What needs guarding is that the
reader's Markdown and the fixture's expected output both still match it,
so an edit to either fails here rather than passing quietly.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import taxonomy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestSingleSource(unittest.TestCase):
    def test_nineteen_families(self):
        self.assertEqual(len(taxonomy.FAMILIES), 19)
        self.assertEqual(len(set(taxonomy.FAMILIES)), 19, "a family is listed twice")

    def test_markdown_matches_code_exactly_and_in_order(self):
        only_code, only_prose, order = taxonomy.drift()
        self.assertEqual((only_code, only_prose, order), ([], [], False))

    def test_fixture_expected_output_matches_code(self):
        path = os.path.join(ROOT, "fixtures", "expected.json")
        with open(path, encoding="utf-8") as fh:
            fams = json.load(fh)["inventory_families"]
        listed = fams["measured"] + fams["absent"] + fams["unmeasured"]
        self.assertEqual(sorted(listed), sorted(taxonomy.FAMILIES))

    def test_validate_run_uses_this_list(self):
        import validate_run
        self.assertIs(validate_run.FAMILIES, taxonomy.FAMILIES)

    def test_drift_is_detected(self):
        """A Markdown file missing a family must be reported."""
        import tempfile
        with open(taxonomy.MARKDOWN, encoding="utf-8") as fh:
            text = fh.read().replace("| `density` |", "| `densty` |", 1)
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write(text)
        only_code, only_prose, _ = taxonomy.drift(tmp.name)
        os.unlink(tmp.name)
        self.assertEqual(only_code, ["density"])
        self.assertEqual(only_prose, ["densty"])


if __name__ == "__main__":
    unittest.main()
