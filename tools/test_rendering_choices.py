"""Tests for deriving the list size and per-section form.

Both were authoring decisions: 3 list sizes x 13 form values across 7
sections, set by hand, where a wrong value is a silent formatting bug rather
than an error. Both rules were already deterministic and written down, and
both are functions of a count the run already has — so nobody should be
typing them.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rendering_choices  # noqa: E402


class TestListSize(unittest.TestCase):
    def test_the_documented_thresholds_are_the_ones_applied(self):
        for count, expected in ((0, "full"), (149, "full"), (150, "short"),
                                (600, "short"), (601, "summary")):
            with self.subTest(count=count):
                self.assertEqual(rendering_choices.list_size(count), expected)

    def test_the_boundaries_are_inclusive_where_the_rule_says_so(self):
        """150 is short and 600 is short — both were stated and both bite."""
        self.assertEqual(rendering_choices.list_size(150), "short")
        self.assertEqual(rendering_choices.list_size(600), "short")


class TestForms(unittest.TestCase):
    def test_every_section_gets_a_form(self):
        forms = rendering_choices.forms({})
        self.assertEqual(set(forms), set(rendering_choices.SECTIONS))

    def test_a_section_form_comes_from_that_sections_own_count(self):
        """Not from the token total — a small repo can still leak a lot."""
        few = rendering_choices.forms({"leaks": 3})
        many = rendering_choices.forms({"leaks": 400})
        self.assertNotEqual(few["leaks"], many["leaks"])

    def test_every_chosen_form_is_one_the_template_carries(self):
        forms = rendering_choices.forms({name: 500
                                         for name in rendering_choices.SECTIONS})
        for section, form in forms.items():
            self.assertIn(form, rendering_choices.FORMS[section], section)

    def test_the_choice_is_stable_across_two_identical_runs(self):
        counts = {"color": 40, "leaks": 12, "orphans": 0}
        self.assertEqual(rendering_choices.forms(counts),
                         rendering_choices.forms(counts))


class TestApply(unittest.TestCase):
    def test_it_writes_both_axes_into_the_rendering_block(self):
        report = {"rendering": {"view": "snapshot"}}
        rendering_choices.apply(report, token_count=800,
                                section_counts={"leaks": 2})
        self.assertEqual(report["rendering"]["tier"], "summary")
        self.assertEqual(set(report["rendering"]["forms"]),
                         set(rendering_choices.SECTIONS))

    def test_the_view_is_left_alone_because_it_encodes_intent(self):
        report = {"rendering": {"view": "evidence"}}
        rendering_choices.apply(report, 10, {})
        self.assertEqual(report["rendering"]["view"], "evidence")


if __name__ == "__main__":
    unittest.main()


class TestTheCliProducesTheWholeBlock(unittest.TestCase):
    """A CLI that only takes a token count leaves the real work by hand.

    The per-section forms are functions of each section's OWN count, and the
    run has already measured every one of them — but the command accepted a
    bare integer, so an operator had to read the thresholds out of the
    reference and apply them themselves. That is the authoring decision this
    module exists to remove.
    """

    def artifacts(self):
        directory = tempfile.mkdtemp()
        tokens = {
            "concept_count": 1104,
            "family_states": {
                "color": {"state": "counted", "count": 491},
                "typography": {"state": "counted", "count": 162},
                "spacing": {"state": "counted", "count": 62},
                "motion": {"state": "not-visible"},
            },
        }
        leakage = {"exact_value_candidates": [], "uncovered_candidates": [{"x": 1}]}
        discovery = {"orphans": {"owned": ["a.css"], "outside_owned_scope": []}}
        for name, doc in (("tokens", tokens), ("leakage", leakage),
                          ("discovery", discovery)):
            with open(os.path.join(directory, name + ".json"), "w",
                      encoding="utf-8") as handle:
                json.dump(doc, handle)
        return directory

    def run_cli(self, directory):
        out = os.path.join(directory, "rendering.json")
        code = rendering_choices.main([
            "--tokens", os.path.join(directory, "tokens.json"),
            "--leakage", os.path.join(directory, "leakage.json"),
            "--discovery", os.path.join(directory, "discovery.json"),
            "--json", out])
        self.assertEqual(code, 0)
        with open(out, encoding="utf-8") as handle:
            return json.load(handle)

    def test_it_emits_the_list_size_from_the_real_token_count(self):
        self.assertEqual(self.run_cli(self.artifacts())["tier"], "summary")

    def test_it_emits_a_form_for_every_section(self):
        forms = self.run_cli(self.artifacts())["forms"]
        self.assertEqual(set(forms), set(rendering_choices.SECTIONS))

    def test_a_section_form_reflects_that_sections_own_measured_count(self):
        forms = self.run_cli(self.artifacts())["forms"]
        # 491 colors sits between the swatch-grid threshold (~300) and the
        # ramp threshold (~1000) in references/report.md's own table.
        self.assertEqual(forms["color"], "swatches")
        self.assertEqual(forms["leaks"], "rows")

    def test_a_family_the_run_could_not_see_counts_as_nothing_not_as_zero(self):
        """`not-visible` carries no number, so it contributes none."""
        counts = rendering_choices.section_counts(
            {"family_states": {"motion": {"state": "not-visible"}}}, {}, {})
        self.assertEqual(counts["spacing"], 0)
