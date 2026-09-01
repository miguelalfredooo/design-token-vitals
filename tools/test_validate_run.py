"""Tests for validate_run.

Each rule describes a report that looks finished and is not. A test that
only proves the happy path would let every one of them through.
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_run  # noqa: E402

FAMILIES = validate_run.FAMILIES


def good_doc():
    return {
        "discovery": {
            "detected_by": "apps/v4/app/globals.css: @theme inline block",
            "token_sources": [
                {"path": "app/globals.css", "classification": "canonical",
                 "reachable_from": ["app/globals.css"]},
                {"path": "app/legacy.css", "classification": "alias",
                 "reachable_from": ["app/globals.css"]},
                {"path": "app/stray.css", "classification": "unverified"},
            ],
            "import_graph": {"roots": [{"path": "app/globals.css", "detected_by": "next app router"}]},
            "resolved_modes": ["light", "dark"],
        },
        "declared": {"modes": ["light", "dark"]},
        "vitals": {"mode-completeness": {"grade": "pass"}},
        "inventory": {"families": {
            f: {"state": "measured", "count": 3, "note": None} for f in FAMILIES
        }},
        "rendering": {"truncated": []},
    }


def rules_failed(doc, html=None):
    return {f.rule for f in validate_run.validate(doc, html)}


class TestHappyPath(unittest.TestCase):
    def test_a_complete_report_passes_every_rule(self):
        self.assertEqual(validate_run.validate(good_doc()), [])


class TestRule1DiscoveryEvidence(unittest.TestCase):
    def test_single_source_with_no_graph_roots_fails(self):
        d = good_doc()
        d["discovery"]["token_sources"] = [{"path": "tokens.css", "classification": "canonical",
                                            "reachable_from": ["tokens.css"]}]
        d["discovery"]["import_graph"] = {"roots": []}
        self.assertIn("1-discovery-evidence", rules_failed(d))

    def test_no_sources_at_all_fails(self):
        d = good_doc()
        d["discovery"]["token_sources"] = []
        d["stack"] = {"token_sources": []}
        self.assertIn("1-discovery-evidence", rules_failed(d))

    def test_single_source_backed_by_graph_roots_passes(self):
        d = good_doc()
        d["discovery"]["token_sources"] = [{"path": "tokens.css", "classification": "canonical",
                                            "reachable_from": ["app/globals.css"]}]
        self.assertNotIn("1-discovery-evidence", rules_failed(d))


class TestRule2Reachability(unittest.TestCase):
    def test_canonical_source_without_reachability_fails(self):
        d = good_doc()
        d["discovery"]["token_sources"][0].pop("reachable_from")
        self.assertIn("2-reachability", rules_failed(d))

    def test_unverified_source_needs_no_reachability(self):
        d = good_doc()
        self.assertNotIn("2-reachability", rules_failed(d))

    def test_unknown_classification_fails(self):
        d = good_doc()
        d["discovery"]["token_sources"][0]["classification"] = "probably-fine"
        self.assertIn("2-reachability", rules_failed(d))

    def test_source_without_classification_fails(self):
        d = good_doc()
        d["discovery"]["token_sources"].append("app/bare-string.css")
        self.assertIn("2-reachability", rules_failed(d))


class TestRule3ModeResolution(unittest.TestCase):
    def test_grading_modes_without_resolved_output_fails(self):
        d = good_doc()
        d["discovery"].pop("resolved_modes")
        self.assertIn("3-mode-resolution", rules_failed(d))

    def test_grading_modes_with_a_scheme_unresolved_fails(self):
        d = good_doc()
        d["declared"]["modes"] = ["light", "dark", "high-contrast"]
        self.assertIn("3-mode-resolution", rules_failed(d))

    def test_blocked_needs_no_resolved_output(self):
        d = good_doc()
        d["discovery"].pop("resolved_modes")
        d["vitals"]["mode-completeness"]["grade"] = "blocked"
        self.assertNotIn("3-mode-resolution", rules_failed(d))


class TestRule4UnmeasuredAsZero(unittest.TestCase):
    def test_unmeasured_family_reported_as_zero_fails(self):
        d = good_doc()
        d["inventory"]["families"]["motion"] = {"state": "unmeasured", "count": 0, "note": "no build"}
        self.assertIn("4-unmeasured-as-zero", rules_failed(d))

    def test_unmeasured_family_without_a_note_fails(self):
        d = good_doc()
        d["inventory"]["families"]["motion"] = {"state": "unmeasured", "count": None}
        self.assertIn("4-unmeasured-as-zero", rules_failed(d))

    def test_absent_family_may_report_zero(self):
        d = good_doc()
        d["inventory"]["families"]["motion"] = {"state": "absent", "count": 0}
        self.assertNotIn("4-unmeasured-as-zero", rules_failed(d))

    def test_unknown_state_fails(self):
        d = good_doc()
        d["inventory"]["families"]["motion"] = {"state": "probably", "count": 1}
        self.assertIn("4-unmeasured-as-zero", rules_failed(d))


class TestRule5FamilyCoverage(unittest.TestCase):
    def test_missing_typography_fails_by_name(self):
        d = good_doc()
        del d["inventory"]["families"]["typography"]
        failures = validate_run.validate(d)
        self.assertTrue(any("typography is missing" in f.message for f in failures))

    def test_missing_grid_fails(self):
        d = good_doc()
        del d["inventory"]["families"]["grid"]
        self.assertIn("5-family-coverage", rules_failed(d))

    def test_no_families_block_fails(self):
        d = good_doc()
        d["inventory"].pop("families")
        self.assertIn("5-family-coverage", rules_failed(d))

    def test_taxonomy_covers_the_documented_foundations(self):
        for name in ("color", "typography", "spacing", "radius", "grid", "focus", "motion"):
            self.assertIn(name, FAMILIES)


class TestRule6HtmlJsonParity(unittest.TestCase):
    def test_html_truncation_not_declared_in_json_fails(self):
        html = '<div class="trunc">Showing the 12 largest groups.</div>'
        self.assertIn("6-html-json-parity", rules_failed(good_doc(), html))

    def test_declared_truncation_without_a_summary_fails(self):
        d = good_doc()
        d["rendering"]["truncated"] = [{"section": "leaks", "shown": 12, "withheld": 40}]
        html = '<div class="trunc">Showing the 12 largest groups.</div>'
        self.assertIn("6-html-json-parity", rules_failed(d, html))

    def test_declared_truncation_with_a_summary_passes(self):
        d = good_doc()
        d["rendering"]["truncated"] = [
            {"section": "leaks", "shown": 12, "withheld": 40,
             "summary": "single-file occurrences of 40 further values"}
        ]
        html = '<div class="trunc">Showing the 12 largest groups.</div>'
        self.assertNotIn("6-html-json-parity", rules_failed(d, html))

    def test_html_omitted_skips_the_rule(self):
        self.assertNotIn("6-html-json-parity", rules_failed(good_doc(), None))


class TestRule7FixQueue(unittest.TestCase):
    def queue_doc(self, **over):
        d = good_doc()
        item = {"id": "a" * 12, "tier": "redundant", "literal": "#b3402f",
                "replacement": "--danger", "locations": ["app/a.css:4"],
                "confidence": "exact static match", "safe_to_automate": True}
        item.update(over)
        d["fix_queue"] = [item]
        return d

    def test_a_complete_entry_passes(self):
        self.assertNotIn("7-fix-queue", rules_failed(self.queue_doc()))

    def test_missing_replacement_fails(self):
        self.assertIn("7-fix-queue", rules_failed(self.queue_doc(replacement=None)))

    def test_missing_locations_fails(self):
        self.assertIn("7-fix-queue", rules_failed(self.queue_doc(locations=[])))

    def test_unknown_confidence_level_fails(self):
        self.assertIn("7-fix-queue", rules_failed(self.queue_doc(confidence="pretty sure")))

    def test_omitting_the_automation_flag_fails(self):
        d = self.queue_doc()
        del d["fix_queue"][0]["safe_to_automate"]
        self.assertIn("7-fix-queue", rules_failed(d))

    def test_near_miss_marked_automatable_fails(self):
        """Drift needs a person to decide what was intended."""
        self.assertIn("7-fix-queue", rules_failed(self.queue_doc(tier="near-miss")))

    def test_manual_review_marked_automatable_fails(self):
        self.assertIn("7-fix-queue", rules_failed(
            self.queue_doc(confidence="manual review")))

    def test_near_miss_not_marked_automatable_passes(self):
        self.assertNotIn("7-fix-queue", rules_failed(
            self.queue_doc(tier="near-miss", safe_to_automate=False)))

    def test_absent_queue_skips_the_rule(self):
        self.assertNotIn("7-fix-queue", rules_failed(good_doc()))


class TestRule8HtmlCompleteness(unittest.TestCase):
    def test_a_finding_missing_from_the_html_fails(self):
        d = good_doc()
        d["fix_queue"] = [{"id": "b" * 12, "tier": "redundant", "literal": "#fff",
                           "replacement": "--surface", "locations": ["a.css:1"],
                           "confidence": "exact static match", "safe_to_automate": True}]
        self.assertIn("8-html-completeness", rules_failed(d, "<html>nothing here</html>"))

    def test_a_finding_present_in_the_html_passes(self):
        d = good_doc()
        fid = "b" * 12
        d["fix_queue"] = [{"id": fid, "tier": "redundant", "literal": "#fff",
                           "replacement": "--surface", "locations": ["a.css:1"],
                           "confidence": "exact static match", "safe_to_automate": True}]
        html = '<tr data-finding="%s"><td>#fff</td></tr>' % fid
        self.assertNotIn("8-html-completeness", rules_failed(d, html))

    def test_collapsed_behind_details_still_counts_as_present(self):
        d = good_doc()
        fid = "c" * 12
        d["fix_queue"] = [{"id": fid, "tier": "redundant", "literal": "#fff",
                           "replacement": "--surface", "locations": ["a.css:1"],
                           "confidence": "exact static match", "safe_to_automate": True}]
        html = '<details><summary>more</summary><span id="%s"></span></details>' % fid
        self.assertNotIn("8-html-completeness", rules_failed(d, html))

    def test_no_html_skips_the_rule(self):
        self.assertNotIn("8-html-completeness", rules_failed(good_doc(), None))


class TestRule9UnescapedMarkup(unittest.TestCase):
    def test_a_script_tag_in_the_html_fails(self):
        html = '<td><span class="lit">"<script>alert(1)</script>"</span></td>'
        self.assertIn("9-unescaped-markup", rules_failed(good_doc(), html))

    def test_an_event_handler_attribute_fails(self):
        html = '<td><span class="lit"><b onmouseover=alert(1)>x</b></span></td>'
        self.assertIn("9-unescaped-markup", rules_failed(good_doc(), html))

    def test_a_javascript_url_fails(self):
        html = '<a href="javascript:alert(1)">x</a>'
        self.assertIn("9-unescaped-markup", rules_failed(good_doc(), html))

    def test_escaped_markup_passes(self):
        """The same content, escaped on fill, is inert and must pass."""
        html = '<td><span class="lit">"&lt;script&gt;alert(1)&lt;/script&gt;"</span></td>'
        self.assertNotIn("9-unescaped-markup", rules_failed(good_doc(), html))

    def test_the_word_onload_inside_prose_does_not_trip_it(self):
        html = '<p>The onload story here is a real one, and so is the script.</p>'
        self.assertNotIn("9-unescaped-markup", rules_failed(good_doc(), html))

    def test_the_template_itself_passes(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "assets", "report-template.html"), encoding="utf-8") as fh:
            self.assertNotIn("9-unescaped-markup", rules_failed(good_doc(), fh.read()))


class TestIndependence(unittest.TestCase):
    def test_each_rule_fails_on_its_own(self):
        """A broken doc reports every rule it breaks, rather than the first."""
        d = good_doc()
        d["discovery"].pop("resolved_modes")
        del d["inventory"]["families"]["grid"]
        self.assertEqual(rules_failed(d), {"3-mode-resolution", "5-family-coverage"})

    def test_good_doc_is_not_accidentally_passing(self):
        """Guard against a typo making every rule vacuous."""
        d = copy.deepcopy(good_doc())
        d["discovery"]["token_sources"][0]["classification"] = "nonsense"
        self.assertTrue(validate_run.validate(d))


if __name__ == "__main__":
    unittest.main()
