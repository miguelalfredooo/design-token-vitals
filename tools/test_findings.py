"""Tests for findings.

Identity is what makes a trend report mean anything, so the cases that
matter are the ones where identity should hold while everything around it
moves.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from findings import (  # noqa: E402
    collect_ids, effort, finding_id, is_automatable, normalize_literal, priority, rank,
)


class TestNormalizeLiteral(unittest.TestCase):
    def test_shorthand_hex_expands(self):
        self.assertEqual(normalize_literal("#FFF"), "#ffffff")

    def test_case_folds(self):
        self.assertEqual(normalize_literal("#B3402F"), normalize_literal("#b3402f"))

    def test_whitespace_inside_a_function_collapses(self):
        self.assertEqual(normalize_literal("rgb( 255 , 0 , 0 )"), "rgb(255,0,0)")

    def test_none_is_empty(self):
        self.assertEqual(normalize_literal(None), "")


class TestFindingId(unittest.TestCase):
    def test_id_is_stable_across_calls(self):
        a = finding_id("redundant", "color", "#B3402F", "--danger")
        b = finding_id("redundant", "color", "#b3402f", "--danger")
        self.assertEqual(a, b)

    def test_id_ignores_file_paths_entirely(self):
        """A rename must not resolve a finding and create a new one."""
        a = finding_id("redundant", "color", "#fff", "--surface")
        b = finding_id("redundant", "color", "#FFFFFF", "--surface")
        self.assertEqual(a, b)

    def test_different_token_is_a_different_finding(self):
        a = finding_id("redundant", "color", "#fff", "--surface")
        b = finding_id("redundant", "color", "#fff", "--card")
        self.assertNotEqual(a, b)

    def test_different_tier_is_a_different_finding(self):
        a = finding_id("redundant", "color", "#fff", "--surface")
        b = finding_id("near-miss", "color", "#fff", "--surface")
        self.assertNotEqual(a, b)

    def test_id_is_twelve_hex_characters(self):
        got = finding_id("redundant", "color", "#fff", "--surface")
        self.assertEqual(len(got), 12)
        int(got, 16)


class TestAutomatable(unittest.TestCase):
    def test_redundant_with_semantic_proof_is_automatable(self):
        self.assertTrue(
            is_automatable("redundant", "exact static match", True)
        )

    def test_exact_value_without_semantic_proof_is_not_automatable(self):
        self.assertFalse(is_automatable("redundant", "exact static match"))

    def test_redundant_needing_manual_review_is_not(self):
        self.assertFalse(is_automatable("redundant", "manual review"))

    def test_near_miss_is_never_automatable(self):
        self.assertFalse(is_automatable("near-miss", "exact static match"))

    def test_uncovered_is_never_automatable(self):
        self.assertFalse(is_automatable("uncovered", "compiled-runtime verified"))


class TestPriority(unittest.TestCase):
    def test_inputs_are_all_reported(self):
        p = priority(10, 4, 2, "exact static match")
        for key in ("occurrences", "files", "breadth", "confidence",
                    "confidence_weight", "formula", "score"):
            self.assertIn(key, p)

    def test_formula_matches_the_published_one(self):
        p = priority(10, 4, 2, "compiled-runtime verified")
        self.assertEqual(p["score"], round((10 + 2 * 4 + 3 * 2) * 1.0, 2))

    def test_files_outweigh_occurrences(self):
        spread = priority(10, 10, 0, "compiled-runtime verified")["score"]
        clustered = priority(10, 1, 0, "compiled-runtime verified")["score"]
        self.assertGreater(spread, clustered)

    def test_breadth_outweighs_files(self):
        broad = priority(10, 4, 4, "compiled-runtime verified")["score"]
        narrow = priority(10, 6, 0, "compiled-runtime verified")["score"]
        self.assertGreater(broad, narrow)

    def test_low_confidence_cannot_win_on_volume_alone(self):
        risky = priority(100, 40, 10, "manual review")["score"]
        certain = priority(100, 40, 10, "compiled-runtime verified")["score"]
        self.assertGreater(certain, risky)

    def test_unknown_confidence_is_treated_as_manual_review(self):
        self.assertEqual(priority(5, 1, 0, "whatever")["confidence_weight"], 0.4)


class TestRank(unittest.TestCase):
    def test_orders_by_score_descending(self):
        items = [
            {"id": "a" * 12, "priority": priority(1, 1, 0, "exact static match")},
            {"id": "b" * 12, "priority": priority(50, 20, 5, "exact static match")},
        ]
        self.assertEqual(rank(items)[0]["id"], "b" * 12)

    def test_ties_break_on_id_so_the_order_is_stable(self):
        p = priority(5, 2, 1, "exact static match")
        items = [{"id": "b" * 12, "priority": p}, {"id": "a" * 12, "priority": p}]
        self.assertEqual([i["id"] for i in rank(items)], ["a" * 12, "b" * 12])


class TestEffort(unittest.TestCase):
    def test_automatable_and_small_is_s(self):
        self.assertEqual(effort("redundant", "exact static match", 4, True), "S")

    def test_automatable_and_wide_is_m(self):
        self.assertEqual(effort("redundant", "exact static match", 84, True), "M")

    def test_a_single_file_judgment_call_is_m(self):
        self.assertEqual(effort("near-miss", "manual review", 1), "M")

    def test_drift_across_files_is_l(self):
        self.assertEqual(effort("near-miss", "manual review", 38), "L")

    def test_uncovered_is_never_below_m(self):
        self.assertIn(effort("uncovered", "exact static match", 2), ("M", "L"))


class TestCollectIds(unittest.TestCase):
    def test_finds_ids_at_any_depth(self):
        doc = {"fix_queue": [{"id": "a" * 12}],
               "groups": {"components": [{"findings": [{"id": "b" * 12}]}]}}
        self.assertEqual(collect_ids(doc), {"a" * 12, "b" * 12})

    def test_ignores_values_that_are_not_finding_ids(self):
        doc = {"run": {"repo_ref": "63c1308"}, "id": "short"}
        self.assertEqual(collect_ids(doc), set())

    def test_a_twelve_character_slug_is_not_a_finding_id(self):
        """Length alone is not identity.

        A finding id is sha1[:12], so it is always twelve hex characters.
        The adoption strategy's standards baseline happens to carry two ids
        that are twelve characters and not hex — `dtcg-2025.10` and
        `semver-2.0.0`. Collected as findings, validate_run rule 8 reports
        them as findings the HTML failed to render, which is both wrong and
        unreadable to anyone trying to act on it.
        """
        doc = {"adoption_strategy": {"standards": [
            {"id": "dtcg-2025.10"}, {"id": "semver-2.0.0"},
            {"id": "css-custom-properties-1"}, {"id": "wcag-2.2"},
        ]}, "fix_queue": [{"id": "0b79f18f2b07"}]}
        self.assertEqual(collect_ids(doc), {"0b79f18f2b07"})


if __name__ == "__main__":
    unittest.main()
