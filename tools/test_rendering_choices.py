"""Tests for deriving the list size and per-section form.

Both were authoring decisions: 3 list sizes x 13 form values across 7
sections, set by hand, where a wrong value is a silent formatting bug rather
than an error. Both rules were already deterministic and written down, and
both are functions of a count the run already has — so nobody should be
typing them.
"""
import os
import sys
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
