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
