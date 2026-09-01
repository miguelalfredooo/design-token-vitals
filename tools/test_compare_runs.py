"""Tests for compare_runs.

The comparison decides whether a reproducibility claim holds, so it has to
be right about what counts as a disagreement and what does not.
"""
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_runs  # noqa: E402

VITALS = compare_runs.VITALS


def run_doc(grades=None, evidence=None, **over):
    grades = grades or {v: "pass" for v in VITALS}
    evidence = evidence or {}
    doc = {
        "discovery": {"environment": "monorepo", "owned_paths": ["apps/v4"], "excluded_paths": []},
        "run": {"token_count": 53, "family_count": 5, "files_scanned": 1230,
                "scope": ["apps/v4"], "framework_versions": {"tailwindcss": "4.3.3"}},
        "stack": {"adapters": ["tailwind", "css-vars"]},
        "vitals": {v: {"grade": grades[v], "evidence": evidence.get(v, []), "note": None} for v in VITALS},
        "rendering": {"tier": "full", "forms": {"color": "swatches", "leaks": "rows"}},
    }
    for path, value in over.items():
        section, field = path.split("__")
        doc[section][field] = value
    return doc


def compare(a, b):
    """Run the comparison on two docs, with its report captured rather than printed."""
    with tempfile.TemporaryDirectory() as d:
        pa, pb = os.path.join(d, "a.json"), os.path.join(d, "b.json")
        for path, doc in ((pa, a), (pb, b)):
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(doc, handle)
        held, sys.stdout = sys.stdout, io.StringIO()
        try:
            return compare_runs.main([pa, pb])
        finally:
            sys.stdout = held


class TestCompare(unittest.TestCase):
    def test_identical_runs_pass(self):
        self.assertEqual(compare(run_doc(), run_doc()), 0)

    def test_one_differing_grade_fails(self):
        g = {v: "pass" for v in VITALS}
        g["leakage"] = "attention"
        self.assertEqual(compare(run_doc(), run_doc(grades=g)), 1)

    def test_differing_token_count_alone_passes(self):
        """A count divergence is reported, and it does not change a grade."""
        self.assertEqual(compare(run_doc(), run_doc(run__token_count=114)), 0)

    def test_differing_evidence_under_same_grade_passes(self):
        a = run_doc(evidence={"leakage": ["a.css:1"]})
        b = run_doc(evidence={"leakage": ["b.css:2"]})
        self.assertEqual(compare(a, b), 0)

    def test_reordered_list_reads_as_agreement(self):
        a = run_doc(stack__adapters=["tailwind", "css-vars"])
        b = run_doc(stack__adapters=["css-vars", "tailwind"])
        self.assertEqual(compare(a, b), 0)

    def test_differing_owned_paths_is_reported(self):
        a, b = run_doc(), run_doc(discovery__owned_paths=["apps/www"])
        self.assertEqual(compare(a, b), 0)  # scope drift alone does not fail

    def test_missing_forms_block_is_tolerated(self):
        a = run_doc()
        b = run_doc()
        del b["rendering"]["forms"]
        self.assertEqual(compare(a, b), 0)

    def test_wrong_argument_count_returns_2(self):
        held, sys.stdout = sys.stdout, io.StringIO()
        try:
            self.assertEqual(compare_runs.main([]), 2)
        finally:
            sys.stdout = held


if __name__ == "__main__":
    unittest.main()
