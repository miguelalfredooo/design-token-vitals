"""Tests for trend.

A trend report is a claim about progress. The cases that matter are the
ones where it would claim progress that never happened.
"""
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trend  # noqa: E402
from findings import finding_id, priority  # noqa: E402

RED = finding_id("redundant", "color", "#b3402f", "--danger")
BLUE = finding_id("redundant", "color", "#2563eb", "--brand")


def doc(findings=None, **over):
    d = {
        "discovery": {
            "environment": "nextjs",
            "owned_paths": ["apps/v4"],
            "token_sources": [{"path": "app/globals.css", "classification": "canonical"}],
        },
        "stack": {"adapters": ["tailwind", "css-vars"]},
        "run": {"scope": ["apps/v4/**"]},
        "fix_queue": findings if findings is not None else [],
    }
    for path, value in over.items():
        section, field = path.split("__")
        d.setdefault(section, {})[field] = value
    return d


def entry(fid, literal, occurrences, files=1):
    return {"id": fid, "literal": literal, "tier": "redundant",
            "occurrences": occurrences, "files": files,
            "priority": priority(occurrences, files, 1, "exact static match")}


def run(base, cur, force=False):
    with tempfile.TemporaryDirectory() as d:
        pb, pc = os.path.join(d, "b.json"), os.path.join(d, "c.json")
        for path, data in ((pb, base), (pc, cur)):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
        held, sys.stdout = sys.stdout, io.StringIO()
        try:
            code = trend.main([pb, pc] + (["--force"] if force else []))
            return code, sys.stdout.getvalue()
        finally:
            sys.stdout = held


class TestCompatibilityGate(unittest.TestCase):
    def test_different_scope_refuses(self):
        code, out = run(doc(), doc(run__scope=["apps/www/**"]))
        self.assertEqual(code, 2)
        self.assertIn("different questions", out)

    def test_different_framework_refuses(self):
        code, _ = run(doc(), doc(discovery__environment="discourse"))
        self.assertEqual(code, 2)

    def test_different_adapters_refuse(self):
        code, _ = run(doc(), doc(stack__adapters=["scss"]))
        self.assertEqual(code, 2)

    def test_different_token_sources_refuse(self):
        other = doc()
        other["discovery"]["token_sources"] = [{"path": "app/other.css", "classification": "canonical"}]
        code, out = run(doc(), other)
        self.assertEqual(code, 2)
        self.assertIn("token sources", out)

    def test_force_diffs_anyway_and_says_so(self):
        code, out = run(doc(), doc(run__scope=["apps/www/**"]), force=True)
        self.assertIn("WARNING", out)
        self.assertNotEqual(code, 2)

    def test_compatible_runs_pass_the_gate(self):
        code, out = run(doc(), doc())
        self.assertEqual(code, 0)
        self.assertNotIn("different questions", out)


class TestDiff(unittest.TestCase):
    def test_a_new_finding_is_reported_new(self):
        d = trend.diff(doc([]), doc([entry(RED, "#b3402f", 3)]))
        self.assertEqual([f["id"] for f in d["new"]], [RED])

    def test_a_gone_finding_is_reported_resolved(self):
        d = trend.diff(doc([entry(RED, "#b3402f", 3)]), doc([]))
        self.assertEqual([f["id"] for f in d["resolved"]], [RED])

    def test_a_grown_count_is_a_regression(self):
        d = trend.diff(doc([entry(RED, "#b3402f", 3)]), doc([entry(RED, "#b3402f", 9)]))
        self.assertEqual(d["grew"][0]["was"], 3)
        self.assertEqual(d["grew"][0]["now"], 9)
        self.assertEqual(len(d["regressions"]), 1)

    def test_a_shrinking_count_is_progress_rather_than_a_regression(self):
        d = trend.diff(doc([entry(RED, "#b3402f", 9)]), doc([entry(RED, "#b3402f", 2)]))
        self.assertEqual(d["regressions"], [])
        self.assertEqual(d["shrank"][0]["now"], 2)

    def test_a_previously_resolved_finding_coming_back_is_a_regression(self):
        base = doc([])
        base["trend"] = {"resolved": [RED]}
        d = trend.diff(base, doc([entry(RED, "#b3402f", 1)]))
        self.assertTrue(any(r["why"] == "resolved earlier, back now" for r in d["regressions"]))

    def test_unchanged_findings_report_no_movement(self):
        d = trend.diff(doc([entry(RED, "#b3402f", 3)]), doc([entry(RED, "#b3402f", 3)]))
        self.assertEqual((d["new"], d["resolved"], d["grew"], d["shrank"]), ([], [], [], []))

    def test_identity_survives_a_respelled_literal(self):
        """#FFF and #ffffff are one finding, so neither run invents churn."""
        a = finding_id("redundant", "color", "#FFF", "--surface")
        b = finding_id("redundant", "color", "#ffffff", "--surface")
        d = trend.diff(doc([entry(a, "#FFF", 2)]), doc([entry(b, "#ffffff", 2)]))
        self.assertEqual((d["new"], d["resolved"]), ([], []))

    def test_regression_exit_status_is_one(self):
        code, _ = run(doc([entry(RED, "#b3402f", 3)]), doc([entry(RED, "#b3402f", 9)]))
        self.assertEqual(code, 1)

    def test_clean_progress_exits_zero(self):
        code, _ = run(doc([entry(RED, "#b3402f", 9)]), doc([entry(RED, "#b3402f", 1)]))
        self.assertEqual(code, 0)

    def test_findings_are_found_wherever_they_are_nested(self):
        cur = doc([])
        cur["groups"] = {"components": [{"name": "Button", "findings": [entry(BLUE, "#2563eb", 4)]}]}
        d = trend.diff(doc([]), cur)
        self.assertEqual([f["id"] for f in d["new"]], [BLUE])


if __name__ == "__main__":
    unittest.main()
