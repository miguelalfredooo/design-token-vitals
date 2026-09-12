"""Tests for conservative literal-color classification."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_literal_colors  # noqa: E402


class TestLiteralColors(unittest.TestCase):
    def test_equal_value_is_a_manual_candidate_not_an_automatic_fix(self):
        root = tempfile.mkdtemp()
        path = os.path.join(root, "app/card.scss")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(".card { color: #fff; } // #000 is a comment")
        discovery = {"owned_import_graph": {"reachable": {"app/card.scss": {}}}}
        tokens = {"sources": [], "concepts": [{"id": "surface", "family": "color",
                  "representations": ["css-custom-property"], "values": ["#ffffff"]}]}
        result = audit_literal_colors.audit(root, discovery, tokens)
        finding = result["exact_value_candidates"][0]
        self.assertEqual(finding["token_candidates"], ["--surface"])
        self.assertFalse(finding["safe_to_automate"])
        self.assertEqual(finding["confidence"], "manual review")
        self.assertEqual(len(result["uncovered_candidates"]), 0)


if __name__ == "__main__":
    unittest.main()


class TestNothingToMeasure(unittest.TestCase):
    """A clean repository has to be able to say so.

    Both checks returned the string "not-visible" unconditionally, so a
    codebase whose every color already came from a token could not grade
    leakage at all: validate_run rejects a leakage grade while semantic
    equivalence is unmeasured, and there was no input that would ever
    change the answer. A run with nothing left to compare has finished the
    comparison.
    """

    def repo(self, content):
        root = tempfile.mkdtemp()
        path = os.path.join(root, "app/card.scss")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return audit_literal_colors.audit(
            root,
            {"owned_import_graph": {"reachable": {"app/card.scss": {}}}},
            {"sources": [], "concepts": [{
                "id": "surface", "family": "color",
                "representations": ["css-custom-property"],
                "values": ["#ffffff"]}]})

    def test_no_literal_at_all_measures_both_checks_as_none_found(self):
        result = self.repo(".card { color: var(--surface); }")
        for check in ("near_miss", "semantic_equivalence"):
            with self.subTest(check=check):
                self.assertEqual(result[check]["state"], "counted", check)
                self.assertEqual(result[check]["findings"], 0, check)
                self.assertTrue(result[check]["note"])

    def test_a_literal_leaves_near_miss_honestly_unmeasured(self):
        result = self.repo(".card { color: #123456; }")
        self.assertEqual(result["near_miss"]["state"], "not-visible")
        self.assertIsNone(result["near_miss"]["findings"])

    def test_an_exact_candidate_leaves_semantic_equivalence_unmeasured(self):
        result = self.repo(".card { color: #fff; }")
        self.assertEqual(result["exact_value_candidates"][0]["literal"], "#ffffff")
        self.assertEqual(result["semantic_equivalence"]["state"], "not-visible")

    def test_an_uncovered_literal_does_not_claim_semantic_review_is_pending(self):
        """Nothing to replace it with, so no role to prove."""
        result = self.repo(".card { color: #123456; }")
        self.assertEqual(len(result["uncovered_candidates"]), 1)
        self.assertEqual(result["semantic_equivalence"]["state"], "counted")
