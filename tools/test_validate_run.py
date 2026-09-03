"""Tests for validate_run.

Each rule describes a report that looks finished and is not. A test that
only proves the happy path would let every one of them through.
"""
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validate_run  # noqa: E402
import discover_tokens  # noqa: E402
import render_component_usage  # noqa: E402
import render_discovery  # noqa: E402
import discover_environment  # noqa: E402

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

    def test_leakage_cannot_be_graded_when_semantic_equivalence_is_unmeasured(self):
        d = good_doc()
        d["vitals"]["leakage"] = {
            "grade": "attention",
            "tiers": {"redundant": None, "exact-value candidate": 24},
        }
        self.assertIn("4-unmeasured-as-zero", rules_failed(d))

    def test_blocked_leakage_may_report_exact_value_candidates(self):
        d = good_doc()
        d["vitals"]["leakage"] = {
            "grade": "blocked",
            "tiers": {"redundant": None, "exact-value candidate": 24},
        }
        self.assertNotIn("4-unmeasured-as-zero", rules_failed(d))


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
    def inventory_tabs_shell(self):
        tabs = []
        panels = []
        for index, family in enumerate(("color", "typography", "foundation")):
            tabs.append(
                '<button role="tab" id="inventory-tab-%s" aria-controls="inventory-panel-%s" '
                'aria-selected="%s"></button>' % (
                    family, family, "true" if index == 0 else "false"))
            panels.append(
                '<div role="tabpanel" id="inventory-panel-%s" '
                'aria-labelledby="inventory-tab-%s"></div>' % (family, family))
        return (
            '<body data-report-view="snapshot">'
            '<style>.token-tabs__list { display: none; gap: 4px; }'
            '.token-tabs--ready .token-tabs__list { display: flex; }'
            '.report-view-switcher { display: none; }'
            '.report-views--ready .report-view-switcher { display: block; }'
            '@media print { .token-tabs__list { display: none !important; }'
            '.token-tabs__panel { display: block !important; padding-top: 12px; } }</style>'
            '<div data-token-inventory-tabs><div role="tablist">%s</div>%s</div>'
            '<!-- SLOT:report-view-switcher --><!-- /SLOT:report-view-switcher -->'
            '<!-- SLOT:inventory-tabs-script --><!-- /SLOT:inventory-tabs-script -->' % (
                "".join(tabs), "".join(panels))
        )

    def universal_doc(self):
        d = good_doc()
        d["discovery"]["engine"] = {"name": "universal-profile-engine"}
        d["rendering"].update({
            "view": "snapshot",
            "available_views": list(render_discovery.REPORT_VIEWS),
        })
        d.update({
            "stage": {"current": "declared", "next": "adopted"},
            "executive_summary": {}, "decisions": [], "fix_queue": [],
            "groups": {"by_value": [], "by_component": []},
            "lineage": [],
            "coverage_matrix": {
                "bundles": [], "modes": [], "families": [], "cells": [],
            },
        })
        return d

    def test_universal_report_requires_stakeholder_regions(self):
        failure = validate_run.rule_6_html_matches_json(
            self.universal_doc(), "<html></html>")
        self.assertIsNotNone(failure)
        self.assertIn("required HTML region is absent", " ".join(failure.detail))

    def test_finished_legacy_report_cannot_skip_the_three_view_contract(self):
        failure = validate_run.rule_6_html_matches_json(
            good_doc(), "<!doctype html><html><body></body></html>"
        )

        self.assertIsNotNone(failure)
        self.assertIn("rendering.view is missing or invalid", failure.detail)
        self.assertIn("HTML has no report-view switcher", failure.detail)

    def test_universal_report_regions_preserve_json_records(self):
        d = self.universal_doc()
        slots = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        html = self.inventory_tabs_shell() + "".join(
            "<!-- SLOT:%s --><!-- /SLOT:%s -->" % (name, name)
            for name in slots
        )
        rendered = render_discovery.render_report_slots(
            html, d, None,
            {"repository": {"root": "/tmp/repo", "ref": "abc123"}},
        )
        self.assertIsNone(validate_run.rule_6_html_matches_json(d, rendered))

    def test_dashboard_component_values_must_match_json(self):
        d = self.universal_doc()
        row = {
            "id": "c" * 12, "rank": 1, "name": "app / button",
            "key": "app::button", "kind": "component",
            "paths": ["app/button.scss"], "references": 80,
            "distinct_tokens": 26,
        }
        roadmap_row = {
            "id": row["id"], "rank": row["rank"],
            "references": row["references"],
        }
        roadmap = validate_run.build_roadmap([roadmap_row])
        for field in (
                "roadmap_band", "share_of_ranked_references",
                "cumulative_share_of_ranked_references"):
            row[field] = roadmap_row[field]
        d["component_usage"] = {
            "state": "measured", "shown": 1, "fallback_surfaces": 0,
            "roadmap": roadmap, "top_20": [row],
        }
        slots = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        html = self.inventory_tabs_shell() + "".join(
            "<!-- SLOT:%s --><!-- /SLOT:%s -->" % (name, name)
            for name in slots
        )
        rendered = render_discovery.render_report_slots(
            html, d, None,
            {"repository": {"root": "/tmp/repo", "ref": "abc123"}},
        )

        tampered = rendered.replace(
            'data-component-references="80"',
            'data-component-references="999"',
            1,
        )

        failure = validate_run.rule_6_html_matches_json(d, tampered)
        self.assertIsNotNone(failure)
        self.assertIn(
            "dashboard data-component-references disagrees with JSON",
            " ".join(failure.detail),
        )
        visible_tamper = rendered.replace(
            '<td class="num">80</td>', '<td class="num">999</td>', 1
        )
        visible_failure = validate_run.rule_6_html_matches_json(
            d, visible_tamper
        )
        self.assertIsNotNone(visible_failure)
        self.assertIn(
            "dashboard visible counts disagree with JSON",
            " ".join(visible_failure.detail),
        )

    def test_each_supplementary_region_is_required(self):
        d = self.universal_doc()
        slots = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        html = self.inventory_tabs_shell() + "".join(
            "<!-- SLOT:%s --><!-- /SLOT:%s -->" % (name, name)
            for name in slots
        )
        rendered = render_discovery.render_report_slots(
            html, d, None,
            {"repository": {"root": "/tmp/repo", "ref": "abc123"}},
        )
        for name in (
                "next-steps", "modes-coverage", "modes-gaps",
                "orphans", "enforcement"):
            with self.subTest(region=name):
                missing = re.sub(
                    r'<!-- SLOT:%s -->.*?<!-- /SLOT:%s -->' % (
                        re.escape(name), re.escape(name)),
                    "", rendered, flags=re.S,
                )
                failure = validate_run.rule_6_html_matches_json(d, missing)
                self.assertIsNotNone(failure)
                self.assertIn(
                    "required HTML region is absent: %s" % name,
                    failure.detail,
                )

    def test_inventory_tab_controller_is_required(self):
        d = self.universal_doc()
        slots = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        html = self.inventory_tabs_shell() + "".join(
            "<!-- SLOT:%s --><!-- /SLOT:%s -->" % (name, name)
            for name in slots
        )
        rendered = render_discovery.render_report_slots(
            html, d, None,
            {"repository": {"root": "/tmp/repo", "ref": "abc123"}},
        ).replace(render_discovery.INVENTORY_TABS_SCRIPT, "")
        failure = validate_run.rule_6_html_matches_json(d, rendered)
        self.assertIsNotNone(failure)
        self.assertIn(
            "inventory tabs lack exactly one verified controller",
            failure.detail,
        )

    def test_report_view_selection_must_match_json(self):
        d = self.universal_doc()
        slots = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        html = self.inventory_tabs_shell() + "".join(
            "<!-- SLOT:%s --><!-- /SLOT:%s -->" % (name, name)
            for name in slots
        )
        rendered = render_discovery.render_report_slots(
            html, d, None,
            {"repository": {"root": "/tmp/repo", "ref": "abc123"}},
        )
        tampered = rendered.replace(
            '<body data-report-view="snapshot">',
            '<body data-report-view="evidence">',
        )
        failure = validate_run.rule_6_html_matches_json(d, tampered)
        self.assertIsNotNone(failure)
        self.assertIn("HTML initial report view disagrees with JSON", failure.detail)

    def test_report_sections_must_keep_their_view_contract(self):
        d = self.universal_doc()
        slots = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        html = self.inventory_tabs_shell() + "".join(
            "<!-- SLOT:%s --><!-- /SLOT:%s -->" % (name, name)
            for name in slots
        )
        rendered = render_discovery.render_report_slots(
            html, d, None,
            {"repository": {"root": "/tmp/repo", "ref": "abc123"}},
        )
        rendered += '<section id="inventory" data-report-views="action evidence"></section>'
        failure = validate_run.rule_6_html_matches_json(d, rendered)
        self.assertIsNotNone(failure)
        self.assertIn(
            "inventory section has the wrong report-view visibility",
            failure.detail,
        )

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
                "confidence": "exact static match", "semantic_role_verified": True,
                "safe_to_automate": True}
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

    def test_exact_value_without_semantic_proof_marked_automatable_fails(self):
        self.assertIn("7-fix-queue", rules_failed(
            self.queue_doc(semantic_role_verified=False)))

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

    def test_leakage_finding_missing_one_location_fails(self):
        d = good_doc()
        fid = "d" * 12
        d["leakage_analysis"] = {
            "exact_value_candidates": [{
                "id": fid, "locations": ["a.css:1", "b.css:2"],
                "token_candidates": ["--surface"], "properties": ["color"],
            }],
            "uncovered_candidates": [],
        }
        html = (
            '<tr data-finding="%s" '
            'data-finding-locations-json="[&quot;a.css:1&quot;,&quot;b.css:2&quot;]" '
            'data-finding-token-candidates-json="[&quot;--surface&quot;]" '
            'data-finding-properties-json="[&quot;color&quot;]">'
            '<td><span data-finding-location="a.css:1">a.css:1</span></td></tr>'
        ) % fid
        self.assertIn("8-html-completeness", rules_failed(d, html))


class TestRule9UnescapedMarkup(unittest.TestCase):
    def test_the_fixed_inventory_controller_passes(self):
        html = render_discovery.INVENTORY_TABS_SCRIPT
        self.assertNotIn("9-unescaped-markup", rules_failed(good_doc(), html))

    def test_a_modified_inventory_controller_fails(self):
        html = render_discovery.INVENTORY_TABS_SCRIPT.replace(
            "inventory-tabs", "inventory-tabs-modified", 1)
        self.assertIn("9-unescaped-markup", rules_failed(good_doc(), html))

    def test_a_repeated_inventory_controller_fails(self):
        html = render_discovery.INVENTORY_TABS_SCRIPT * 2
        self.assertIn("9-unescaped-markup", rules_failed(good_doc(), html))

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


class TestUniversalDiscoveryRules(unittest.TestCase):
    def universal_doc(self):
        d = good_doc()
        d["discovery"]["environment"] = ["nextjs"]
        d["discovery"]["capabilities"] = {
            "detection": "verified", "production_roots": "verified",
            "import_resolution": "verified", "token_source_discovery": "verified",
            "ownership": "verified", "mode_resolution": "verified",
            "runtime_verification": "unmeasured",
        }
        d["discovery"]["import_graph"] = {
            "roots": [{"path": "app/globals.css", "root_type": "common",
                       "evidence": "app/layout.tsx:1", "confidence": "framework-registered",
                       "ownership": "owned"}],
            "unresolved": [],
        }
        d["discovery"]["mode_resolution"] = {
            "audited_pairs": [{"bundle": "common", "mode": "light"},
                              {"bundle": "common", "mode": "dark"}],
            "resolved_pairs": [{"bundle": "common", "mode": "light", "artifact": "build/light.css"},
                               {"bundle": "common", "mode": "dark", "artifact": "build/dark.css"}],
        }
        return d

    def test_universal_contract_passes(self):
        self.assertEqual(validate_run.validate(self.universal_doc()), [])

    def test_root_without_evidence_fails(self):
        d = self.universal_doc()
        del d["discovery"]["import_graph"]["roots"][0]["ownership"]
        self.assertIn("10-root-evidence", rules_failed(d))

    def test_bundle_mode_pair_without_artifact_fails(self):
        d = self.universal_doc()
        d["discovery"]["mode_resolution"]["resolved_pairs"].pop()
        self.assertIn("3-mode-resolution", rules_failed(d))

    def test_generic_unresolved_reason_fails(self):
        d = self.universal_doc()
        d["discovery"]["import_graph"]["unresolved"] = [
            {"from": "a.scss", "spec": "sass:math", "reason": "no file matches"}
        ]
        self.assertIn("12-unresolved-classification", rules_failed(d))


class TestRule13ComponentUsage(unittest.TestCase):
    def usage_doc(self):
        d = good_doc()
        component_id = "c" * 12
        roadmap_row = {"id": component_id, "rank": 1, "references": 2}
        roadmap = validate_run.build_roadmap([roadmap_row])
        d["component_usage"] = {
            "state": "measured",
            "shown": 1,
            "roadmap": roadmap,
            "top_20": [{
                "id": component_id,
                "rank": 1,
                "key": "app::button",
                "name": "app / button",
                "kind": "component",
                "confidence": "co-named-source",
                "paths": ["app/button.scss"],
                "references": 2,
                "distinct_tokens": 1,
                "families": {"color": 2},
                "share_of_ranked_references": roadmap_row[
                    "share_of_ranked_references"],
                "cumulative_share_of_ranked_references": roadmap_row[
                    "cumulative_share_of_ranked_references"],
                "roadmap_band": roadmap_row["roadmap_band"],
                "tokens": [{
                    "id": "brand",
                    "family": "color",
                    "references": 2,
                    "syntaxes": ["css-custom-property"],
                    "locations": ["app/button.scss:4"],
                }],
            }],
        }
        return d

    def test_complete_component_usage_passes(self):
        self.assertNotIn("13-component-usage", rules_failed(self.usage_doc()))

    def test_rendered_component_usage_passes_html_parity(self):
        d = self.usage_doc()
        html = render_component_usage.render_section(d["component_usage"])
        self.assertNotIn("13-component-usage", rules_failed(d, html))

    def test_collapsed_locations_pass_html_parity(self):
        d = self.usage_doc()
        token = d["component_usage"]["top_20"][0]["tokens"][0]
        token["locations"] = [
            "app/button.scss:4",
            "app/button.scss:8",
            "app/button.scss:12",
            "app/button.scss:20",
        ]
        html = render_component_usage.render_section(d["component_usage"])

        self.assertIn('data-location-hidden="2"', html)
        self.assertNotIn("13-component-usage", rules_failed(d, html))

    def test_visible_location_tail_fails_html_parity(self):
        d = self.usage_doc()
        token = d["component_usage"]["top_20"][0]["tokens"][0]
        token["locations"] = [
            "app/button.scss:4",
            "app/button.scss:8",
            "app/button.scss:12",
            "app/button.scss:20",
        ]
        html = render_component_usage.render_section(d["component_usage"])
        html = re.sub(
            r'<details class="location-disclosure"[^>]*><summary>.*?</summary>'
            r'<div class="details-body location-lines">(.*?)</div></details>',
            r"\1",
            html,
            count=1,
            flags=re.S,
        )

        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_wrong_location_disclosure_count_fails_html_parity(self):
        d = self.usage_doc()
        token = d["component_usage"]["top_20"][0]["tokens"][0]
        token["locations"] = [
            "app/button.scss:4",
            "app/button.scss:8",
            "app/button.scss:12",
            "app/button.scss:20",
        ]
        html = render_component_usage.render_section(d["component_usage"])
        html = html.replace('data-location-hidden="2"', 'data-location-hidden="1"')

        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_open_location_tail_fails_html_parity(self):
        d = self.usage_doc()
        token = d["component_usage"]["top_20"][0]["tokens"][0]
        token["locations"] = [
            "app/button.scss:4",
            "app/button.scss:8",
            "app/button.scss:12",
        ]
        html = render_component_usage.render_section(d["component_usage"])
        html = html.replace(
            '<details class="location-disclosure"',
            '<details open class="location-disclosure"',
        )

        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_missing_token_detail_block_fails_html_parity(self):
        d = self.usage_doc()
        html = render_component_usage.render_section(d["component_usage"])
        html = html.replace(
            '<details id="component-detail-%s" data-component-detail="%s">' % (
                "c" * 12, "c" * 12
            ),
            '<details id="component-detail-removed" data-component-detail="removed">',
        )
        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_token_evidence_cannot_be_borrowed_from_another_row(self):
        d = self.usage_doc()
        html = render_component_usage.render_section(d["component_usage"])
        html = html.replace(
            '<span class="path" data-token-location="app/button.scss:4">app/button.scss:4</span>',
            '<span class="path">removed</span>',
        )
        html += '<span data-token-location="app/button.scss:4">app/button.scss:4</span>'
        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_more_than_twenty_rows_fails(self):
        d = self.usage_doc()
        d["component_usage"]["top_20"] *= 21
        d["component_usage"]["shown"] = 21
        self.assertIn("13-component-usage", rules_failed(d))

    def test_reference_total_must_match_token_rows(self):
        d = self.usage_doc()
        d["component_usage"]["top_20"][0]["references"] = 3
        self.assertIn("13-component-usage", rules_failed(d))

    def test_component_roadmap_is_required_for_measured_usage(self):
        d = self.usage_doc()
        del d["component_usage"]["roadmap"]
        self.assertIn("13-component-usage", rules_failed(d))

    def test_component_roadmap_share_must_match_ranked_references(self):
        d = self.usage_doc()
        d["component_usage"]["top_20"][0][
            "share_of_ranked_references"] = 99.0
        self.assertIn("13-component-usage", rules_failed(d))

    def test_component_roadmap_html_must_match_json(self):
        d = self.usage_doc()
        html = render_component_usage.render_section(d["component_usage"])
        html = html.replace(
            'data-component-roadmap-json="',
            'data-component-roadmap-json="stale',
            1,
        )
        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_visible_component_roadmap_values_must_match_json(self):
        d = self.usage_doc()
        html = render_component_usage.render_section(d["component_usage"])
        html = html.replace(
            '<td class="num">2</td>', '<td class="num">999</td>', 1
        )

        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_component_roadmap_detail_link_is_required(self):
        d = self.usage_doc()
        html = render_component_usage.render_section(d["component_usage"])
        html = html.replace(
            'href="#component-detail-%s"' % ("c" * 12),
            'href="#component-detail-removed"',
            1,
        )

        self.assertIn("13-component-usage", rules_failed(d, html))

    def test_token_locations_are_required(self):
        d = self.usage_doc()
        d["component_usage"]["top_20"][0]["tokens"][0]["locations"] = []
        self.assertIn("13-component-usage", rules_failed(d))

    def test_unmeasured_usage_requires_a_note(self):
        d = good_doc()
        d["component_usage"] = {"state": "unmeasured", "top_20": []}
        self.assertIn("13-component-usage", rules_failed(d))


class TestRule14ProfileEngine(unittest.TestCase):
    def profile_doc(self):
        root = tempfile.mkdtemp()
        files = {
            "next.config.mjs": "export default {};",
            "app/layout.tsx": 'import "./globals.css";',
            "app/globals.css": ":root { --brand: red; }",
            "components/Button.tsx": 'import "./Button.module.css";',
            "components/Button.module.css": ".button {}",
        }
        for rel, text in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        discovery = discover_environment.discover(
            root, ["app/**", "components/**"])
        return {"discovery": discovery}

    def profile_inventory_doc(self):
        d = self.profile_doc()
        tokens = {
            "concept_count": 1,
            "concepts": [{
                "id": "brand",
                "family": "color",
                "representations": ["css-custom-property"],
                "sites": ["app/globals.css:1"],
                "values": ["red"],
                "definitions": [],
            }],
            "sources": [
                {"role": "canonical"},
                {"role": "alias"},
                {"role": "candidate"},
                {"role": "consumer-override"},
            ],
            "candidate_or_local_override_sources": [{}, {}],
        }
        d["discovery"]["import_graph"]["unresolved"] = [
            {"reason": "external package"},
            {"reason": "missing local source"},
            {"reason": "unsupported resolver"},
        ]
        d["discovery"] = render_discovery.enrich(d["discovery"], tokens)
        d.update({
            "schema_version": "2",
            "run": {"token_count": 1},
            "inventory": {
                "concepts": render_discovery.normalized_concepts(tokens),
                "families": {},
                "candidate_or_local_override_sources": [{}, {}],
            },
            "rendering": {"view": "snapshot", "tier": "full"},
            "provenance": {
                "adapter_versions": {},
                "repo_ref": "test-ref",
                "skill_version": "local-test",
            },
        })
        html = "".join([
            render_discovery.render_section(d["discovery"]),
            render_discovery.concept_rows(d["inventory"]["concepts"]),
            render_discovery.render_measurement(
                d["discovery"], tokens, d, "local-test",
                "2026-09-03T00:00:00Z",
            ),
            render_discovery.render_runhead(
                d["discovery"], tokens, d, "local-test"
            ),
            render_discovery.render_footer(
                d["discovery"], tokens, "local-test"
            ),
        ])
        return d, html

    def test_complete_profile_engine_passes(self):
        self.assertIsNone(validate_run.rule_14_profile_engine(self.profile_doc()))

    def test_rendered_profile_engine_passes_html_parity(self):
        d = self.profile_doc()
        html = render_discovery.render_section(d["discovery"])
        self.assertIsNone(validate_run.rule_14_profile_engine(d, html))

    def test_measurement_metadata_drift_fails_html_parity(self):
        fields = {
            "token_sources": "2",
            "unresolved_actionable": "2",
            "unresolved_total": "3",
            "unresolved_by_reason": "{",
        }
        for field, value in fields.items():
            with self.subTest(field=field):
                d, html = self.profile_inventory_doc()
                marker = "&quot;%s&quot;:%s" % (field, value)
                stale = html.replace(marker, marker + "stale", 1)
                failure = validate_run.rule_14_profile_engine(d, stale)
                self.assertEqual(failure.rule, "14-profile-engine")
                self.assertIn(
                    "measurement summary is missing or stale in HTML",
                    failure.detail,
                )

    def test_runhead_confirmed_source_drift_fails_html_parity(self):
        d, html = self.profile_inventory_doc()
        runhead = re.search(
            r'<dl class="meta" data-runhead-summary-json="[^"]+">', html
        ).group(0)
        stale_runhead = runhead.replace(
            "&quot;token_sources&quot;:2", "&quot;token_sources&quot;:99"
        )
        failure = validate_run.rule_14_profile_engine(
            d, html.replace(runhead, stale_runhead, 1)
        )
        self.assertEqual(failure.rule, "14-profile-engine")
        self.assertIn("run header summary is missing or stale in HTML", failure.detail)

    def test_missing_product_root_fails_html_parity(self):
        d = self.profile_doc()
        html = render_discovery.render_section(d["discovery"])
        root = d["discovery"]["roots"][0]["path"]
        html = html.replace('data-discovery-root="%s"' % root,
                            'data-discovery-root="removed"')
        self.assertEqual(
            validate_run.rule_14_profile_engine(d, html).rule,
            "14-profile-engine",
        )

    def test_product_root_metadata_drift_fails_html_parity(self):
        d = self.profile_doc()
        html = render_discovery.render_section(d["discovery"])
        d["discovery"]["roots"][0]["ownership"] = "unknown"
        self.assertEqual(
            validate_run.rule_14_profile_engine(d, html).rule,
            "14-profile-engine",
        )

    def test_capability_next_step_drift_fails_html_parity(self):
        d = self.profile_doc()
        html = render_discovery.render_section(d["discovery"])
        d["discovery"]["capability_ladder"]["steps"][0]["next_step"] = (
            "Different next step"
        )
        self.assertEqual(
            validate_run.rule_14_profile_engine(d, html).rule,
            "14-profile-engine",
        )

    def test_root_candidate_must_render(self):
        d = self.profile_doc()
        candidate = {
            "path": "styles/disconnected.css", "root_type": "theme",
            "ownership": "unknown", "confidence": "static candidate",
            "profiles": ["convention"], "evidence": "conventional style",
        }
        d["discovery"]["root_candidates"] = [candidate]
        html = render_discovery.render_section(d["discovery"])
        html = html.replace('data-root-candidate="styles/disconnected.css"',
                            'data-root-candidate="removed"')
        self.assertEqual(
            validate_run.rule_14_profile_engine(d, html).rule,
            "14-profile-engine",
        )

    def test_component_candidate_must_render(self):
        d = self.profile_doc()
        candidate = {
            "path": "vendor/components", "scope": "component",
            "ownership": "unknown", "confidence": "static candidate",
            "profiles": ["nextjs"], "evidence": "component convention",
        }
        d["discovery"]["component_root_candidates"] = [candidate]
        html = render_discovery.render_section(d["discovery"])
        html = html.replace('data-component-root-candidate="vendor/components"',
                            'data-component-root-candidate="removed"')
        self.assertEqual(
            validate_run.rule_14_profile_engine(d, html).rule,
            "14-profile-engine",
        )

    def test_current_skill_rejects_stale_provenance(self):
        d = self.profile_doc()
        d["provenance"] = {"skill_version": "stale-version"}
        self.assertEqual(
            validate_run.rule_14_profile_engine(
                d, current_skill=True).rule,
            "14-profile-engine",
        )

    def test_repository_ref_is_not_a_framework_version(self):
        d = self.profile_doc()
        repository_ref = d["discovery"]["repository"]["ref"]
        d["run"] = {
            "repo_ref": repository_ref,
            "framework_versions": {
                "nextjs": "repository checkout %s" % repository_ref,
            },
        }
        self.assertEqual(
            validate_run.rule_14_profile_engine(d).rule,
            "14-profile-engine",
        )

    def test_profile_order_drift_fails(self):
        d = self.profile_doc()
        d["discovery"]["profile_composition"]["order"] = []
        self.assertEqual(
            validate_run.rule_14_profile_engine(d).rule,
            "14-profile-engine",
        )

    def test_partial_profile_candidate_must_render(self):
        d = self.profile_doc()
        d["discovery"]["profile_composition"]["candidates"] = [{
            "id": "vite", "kind": "build-tool", "score": 0.5,
            "evidence": [{"path": "src/main.ts"}], "missing_signals": [],
        }]
        html = render_discovery.render_section(d["discovery"])
        html = html.replace('data-profile-candidate="vite"',
                            'data-profile-candidate="removed"')
        self.assertEqual(
            validate_run.rule_14_profile_engine(d, html).rule,
            "14-profile-engine",
        )

    def test_ladder_state_must_match_capability(self):
        d = self.profile_doc()
        d["discovery"]["capability_ladder"]["steps"][0]["state"] = "blocked"
        self.assertEqual(
            validate_run.rule_14_profile_engine(d).rule,
            "14-profile-engine",
        )

    def test_supplemental_root_cannot_enter_product_graph(self):
        d = self.profile_doc()
        surface = {
            "path": "demo/story.ts", "scope": "demo", "profiles": ["storybook"],
        }
        d["discovery"]["surface_roots"] = [surface]
        d["discovery"]["import_graph"]["reachable"][surface["path"]] = {
            "depth": 0, "via": [],
        }
        self.assertEqual(
            validate_run.rule_14_profile_engine(d).rule,
            "14-profile-engine",
        )


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


class TestRule15SourceArtifactParity(unittest.TestCase):
    def test_interaction_evidence_is_bound_to_report_and_screenshots(self):
        d = good_doc()
        d["provenance"] = {
            "skill_version": "local-test", "generated_at": "2026-09-01T00:00:00Z",
        }
        with tempfile.TemporaryDirectory() as root:
            screenshot = os.path.join(root, "inventory.png")
            with open(screenshot, "wb") as handle:
                handle.write(b"png evidence")
            print_pdf = os.path.join(root, "print.pdf")
            with open(print_pdf, "wb") as handle:
                handle.write(b"pdf evidence")
            d["discovery"]["repository"] = {"root": root}
            interaction = {
                "skill_version": "local-test",
                "generated_at": "2026-09-01T00:00:00Z",
                "report_json_sha256": "a" * 64,
                "report_html_sha256": "b" * 64,
                "controller_sha256": hashlib.sha256(
                    render_discovery.INVENTORY_TABS_SCRIPT.encode("utf-8")
                ).hexdigest(),
                "browser": {"name": "Chromium", "version": "test"},
                "screenshots": [{
                    "path": "inventory.png",
                    "sha256": validate_run.file_sha256(screenshot),
                }],
                "print_pdf": {
                    "path": "print.pdf",
                    "sha256": validate_run.file_sha256(print_pdf),
                    "verified_text": ["row-21-token"],
                },
            }
            artifacts = {
                "interaction": interaction,
                "_report_json_sha256": "a" * 64,
                "_report_html_sha256": "b" * 64,
            }
            self.assertIsNone(
                validate_run.rule_15_source_artifact_parity(d, artifacts))

            interaction["report_html_sha256"] = "stale"
            failure = validate_run.rule_15_source_artifact_parity(d, artifacts)
            self.assertEqual(failure.rule, "15-source-artifact-parity")
            self.assertIn(
                "interaction evidence report HTML hash is stale",
                failure.detail,
            )

    def test_stale_token_artifact_fails_a_consistent_report(self):
        d = good_doc()
        tokens = {
            "concept_count": 1,
            "concepts": [{
                "id": "font-family", "family": "typography",
                "representations": ["css-custom-property"],
                "sites": ["tokens.css:1"],
                "values": ["DM Sans"], "alias_of": None,
            }],
            "candidate_or_local_override_sources": [],
        }
        failure = validate_run.rule_15_source_artifact_parity(
            d, {"tokens": tokens})
        self.assertEqual(failure.rule, "15-source-artifact-parity")

    def test_exact_component_and_leakage_artifacts_pass(self):
        d = good_doc()
        d["component_usage"] = {"state": "unmeasured"}
        d["leakage_analysis"] = {"consumer_files_scanned": 2}
        d["run"] = {"files_scanned": 2}
        self.assertIsNone(validate_run.rule_15_source_artifact_parity(d, {
            "components": d["component_usage"],
            "leakage": d["leakage_analysis"],
        }))


class TestRule16IdentityIntegrity(unittest.TestCase):
    def identity_doc_and_html(self):
        root = tempfile.mkdtemp()
        type_text = ":root { --font-family: DM Sans, sans-serif; }\n"
        color_text = "\n:root { --brand-primary: #5b4bd6; }\n"
        os.makedirs(os.path.join(root, "styles"), exist_ok=True)
        with open(os.path.join(root, "styles/type.css"), "w", encoding="utf-8") as handle:
            handle.write(type_text)
        with open(os.path.join(root, "styles/colors.css"), "w", encoding="utf-8") as handle:
            handle.write(color_text)
        concepts = [{
            "name": "font-family", "family": "typography",
            "values": ["DM Sans, sans-serif"],
            "sites": ["styles/type.css:1"],
            "representations": ["css-custom-property"],
            "definitions": [{
                "value": "DM Sans, sans-serif", "site": "styles/type.css:1",
                "representation": "css-custom-property",
                "offset": type_text.index("--font-family"),
                "identity_context": None,
            }],
        }, {
            "name": "brand-primary", "family": "color",
            "values": ["#5b4bd6"], "sites": ["styles/colors.css:2"],
            "representations": ["css-custom-property"],
            "definitions": [{
                "value": "#5b4bd6", "site": "styles/colors.css:2",
                "representation": "css-custom-property",
                "offset": color_text.index("--brand-primary"),
                "identity_context": None,
            }],
        }]
        canonical = [dict(item, id=item["name"]) for item in concepts]
        discovery = {
            "engine": {"name": "universal-profile-engine"},
            "repository": {"root": root},
            "owned_import_graph": {"reachable": {
                "styles/type.css": {"depth": 0, "via": []},
                "styles/colors.css": {"depth": 0, "via": []},
            }},
        }
        subjects = validate_run.subject_namespace_evidence(root, discovery)
        identity = validate_run.identity_summary(
            canonical, subject_namespaces=subjects)
        typography = identity["typography"]
        brand = identity["brand_colors"]
        doc = {
            "discovery": discovery,
            "inventory": {"concepts": concepts, "identity": {
                "typography": typography, "brand_colors": brand,
            }},
        }
        type_html = render_discovery.typography_block([], typography)
        color_html = render_discovery.color_block([], brand)
        html = (
            "<!-- SLOT:inventory-color -->%s<!-- /SLOT:inventory-color -->"
            "<!-- SLOT:inventory-type -->%s<!-- /SLOT:inventory-type -->"
        ) % (color_html, type_html)
        return doc, html

    def test_verified_identity_and_visible_evidence_pass(self):
        doc, html = self.identity_doc_and_html()
        self.assertIsNone(validate_run.rule_16_identity_integrity(doc, html))

    def test_missing_brand_swatch_fails(self):
        doc, html = self.identity_doc_and_html()
        html = html.replace('data-brand-color="brand-primary"',
                            'data-brand-color="removed"')
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_template_sample_content_fails(self):
        doc, html = self.identity_doc_and_html()
        html += "color.semantic.brand.base"
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_identity_cannot_verify_when_definitions_are_omitted(self):
        doc, html = self.identity_doc_and_html()
        for concept in doc["inventory"]["concepts"]:
            concept.pop("definitions")
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_definition_projections_must_match_visible_aggregates(self):
        doc, html = self.identity_doc_and_html()
        definition = doc["inventory"]["concepts"][1]["definitions"][0]
        definition.update({
            "value": "#ffffff", "site": "other.css:9",
            "representation": "scss-variable",
        })
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_identity_definitions_must_match_source_declarations(self):
        for index, value in ((0, "Arial, sans-serif"), (1, "#123456")):
            with self.subTest(index=index):
                doc, _ = self.identity_doc_and_html()
                concept = doc["inventory"]["concepts"][index]
                concept["values"] = [value]
                concept["definitions"][0]["value"] = value
                canonical = [
                    dict(item, id=item["name"])
                    for item in doc["inventory"]["concepts"]
                ]
                subjects = validate_run.subject_namespace_evidence(
                    doc["discovery"]["repository"]["root"], doc["discovery"])
                identity = validate_run.identity_summary(
                    canonical, subject_namespaces=subjects)
                doc["inventory"]["identity"] = identity
                html = (
                    "<!-- SLOT:inventory-color -->%s<!-- /SLOT:inventory-color -->"
                    "<!-- SLOT:inventory-type -->%s<!-- /SLOT:inventory-type -->"
                ) % (
                    render_discovery.color_block([], identity["brand_colors"]),
                    render_discovery.typography_block([], identity["typography"]),
                )
                failure = validate_run.rule_16_identity_integrity(doc, html)
                self.assertEqual(failure.rule, "16-identity-integrity")
                self.assertTrue(any(
                    "not reproducible from source" in detail
                    for detail in failure.detail
                ))

    def test_verified_identity_requires_repository_source_binding(self):
        doc, html = self.identity_doc_and_html()
        doc["discovery"].pop("repository")
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_brand_heading_context_must_be_reproducible_and_reachable(self):
        doc, _ = self.identity_doc_and_html()
        root = tempfile.mkdtemp()
        path = os.path.join(root, "styles/colors.css")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(":root { --primary: #5b4bd6; }\n")
        context = {
            "kind": "brand", "label": "Visual Identity",
            "path": "styles/colors.css", "line": 1,
        }
        color = {
            "name": "primary", "family": "color", "values": ["#5b4bd6"],
            "sites": ["styles/colors.css:1"],
            "representations": ["css-custom-property"],
            "identity_contexts": [context],
            "definitions": [{
                "value": "#5b4bd6", "site": "styles/colors.css:1",
                "representation": "css-custom-property", "offset": 0,
                "identity_context": context,
            }],
        }
        doc["inventory"]["concepts"][1] = color
        doc["discovery"].update({
            "repository": {"root": root},
            "owned_import_graph": {
                "reachable": {"styles/colors.css": {"depth": 0, "via": []}},
            },
        })
        subjects = validate_run.subject_namespace_evidence(root, doc["discovery"])
        canonical = [
            dict(item, id=item["name"])
            for item in doc["inventory"]["concepts"]
        ]
        identity = validate_run.identity_summary(
            canonical, subject_namespaces=subjects)
        doc["inventory"]["identity"] = identity
        html = (
            "<!-- SLOT:inventory-color -->%s<!-- /SLOT:inventory-color -->"
            "<!-- SLOT:inventory-type -->%s<!-- /SLOT:inventory-type -->"
        ) % (
            render_discovery.color_block([], identity["brand_colors"]),
            render_discovery.typography_block([], identity["typography"]),
        )
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_generic_font_and_invented_confidence_fail(self):
        doc, html = self.identity_doc_and_html()
        typography = doc["inventory"]["identity"]["typography"]
        typography["family"] = "sans-serif"
        typography["confidence"] = "agent-says-so"
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_unresolved_brand_color_fails(self):
        for value in ("rgb(var(--brand-rgb))", "#12345", "rgb(foo)"):
            with self.subTest(value=value):
                doc, html = self.identity_doc_and_html()
                doc["inventory"]["identity"]["brand_colors"]["colors"][0][
                    "value"] = value
                self.assertEqual(
                    validate_run.rule_16_identity_integrity(doc, html).rule,
                    "16-identity-integrity",
                )

    def test_blocked_brand_cannot_render_a_swatch(self):
        doc, html = self.identity_doc_and_html()
        brand = doc["inventory"]["identity"]["brand_colors"]
        brand.update({"state": "blocked", "confidence": "unresolved", "colors": []})
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_blocked_brand_cannot_render_markerless_generic_swatches(self):
        doc, html = self.identity_doc_and_html()
        brand = doc["inventory"]["identity"]["brand_colors"]
        brand.update({"state": "blocked", "confidence": "unresolved", "colors": []})
        html = render_discovery.color_block([], brand)
        html = html.replace(
            "<h3>Brand identity colors</h3>",
            '<h3>Brand identity colors</h3><div data-brand-swatches '
            'class="swatches"><div class="sw"><i style="background:#123456">'
            '</i></div></div>',
        )
        html = (
            "<!-- SLOT:inventory-color -->%s<!-- /SLOT:inventory-color -->"
            "<!-- SLOT:inventory-type -->%s<!-- /SLOT:inventory-type -->"
        ) % (html, render_discovery.typography_block(
            doc["inventory"]["concepts"],
            doc["inventory"]["identity"]["typography"]))
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )

    def test_verified_embedded_repository_font_passes(self):
        doc, _ = self.identity_doc_and_html()
        root = tempfile.mkdtemp()
        relative = "public/fonts/dm-sans.woff2"
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = b"wOF2repository-font"
        with open(path, "wb") as handle:
            handle.write(payload)
        style_path = os.path.join(root, "styles/type.css")
        os.makedirs(os.path.dirname(style_path), exist_ok=True)
        type_text = (
            '@font-face { font-family: "DM Sans"; '
            'src: url("/fonts/dm-sans.woff2") format("woff2"); }\n'
            ':root { --font-family: DM Sans, sans-serif; }\n'
        )
        with open(style_path, "w", encoding="utf-8") as handle:
            handle.write(type_text)
        color_path = os.path.join(root, "styles/colors.css")
        color_text = "\n:root { --brand-primary: #5b4bd6; }\n"
        with open(color_path, "w", encoding="utf-8") as handle:
            handle.write(color_text)
        type_concept, color_concept = doc["inventory"]["concepts"]
        type_concept["sites"] = ["styles/type.css:2"]
        type_concept["definitions"][0].update({
            "site": "styles/type.css:2", "offset": type_text.index("--font-family"),
        })
        color_concept["definitions"][0]["offset"] = color_text.index(
            "--brand-primary")
        doc["discovery"]["repository"] = {"root": root}
        doc["discovery"]["owned_import_graph"] = {
            "reachable": {
                "styles/type.css": {"depth": 0, "via": []},
                "styles/colors.css": {"depth": 0, "via": []},
            },
        }
        subjects = validate_run.subject_namespace_evidence(root, doc["discovery"])
        canonical = [dict(item, id=item["name"])
                     for item in doc["inventory"]["concepts"]]
        faces = discover_tokens.font_face_evidence(
            root, "styles/type.css", type_text)
        identity = validate_run.identity_summary(canonical, faces, subjects)
        doc["inventory"]["identity"] = identity
        typography = identity["typography"]
        type_html = render_discovery.typography_block(
            doc["inventory"]["concepts"], typography, root)
        brand = identity["brand_colors"]
        html = (
            "<!-- SLOT:inventory-color -->%s<!-- /SLOT:inventory-color -->"
            "<!-- SLOT:inventory-type -->%s<!-- /SLOT:inventory-type -->"
        ) % (render_discovery.color_block([], brand), type_html)
        self.assertIsNone(validate_run.rule_16_identity_integrity(doc, html))

    def test_commented_font_face_cannot_verify_a_specimen(self):
        doc, _ = self.identity_doc_and_html()
        root = tempfile.mkdtemp()
        relative = "public/fonts/dm-sans.woff2"
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = b"wOF2inactive-font"
        with open(path, "wb") as handle:
            handle.write(payload)
        style_path = os.path.join(root, "styles/type.css")
        os.makedirs(os.path.dirname(style_path), exist_ok=True)
        type_text = (
            '/* @font-face { font-family: "DM Sans"; '
            'src: url("/fonts/dm-sans.woff2") format("woff2"); } */\n'
            ':root { --font-family: DM Sans, sans-serif; }\n'
        )
        with open(style_path, "w", encoding="utf-8") as handle:
            handle.write(type_text)
        color_path = os.path.join(root, "styles/colors.css")
        color_text = "\n:root { --brand-primary: #5b4bd6; }\n"
        with open(color_path, "w", encoding="utf-8") as handle:
            handle.write(color_text)
        type_concept, color_concept = doc["inventory"]["concepts"]
        type_concept["sites"] = ["styles/type.css:2"]
        type_concept["definitions"][0].update({
            "site": "styles/type.css:2", "offset": type_text.index("--font-family"),
        })
        color_concept["definitions"][0]["offset"] = color_text.index(
            "--brand-primary")
        subjects = validate_run.subject_namespace_evidence(root, doc["discovery"])
        canonical = [dict(item, id=item["name"])
                     for item in doc["inventory"]["concepts"]]
        identity = validate_run.identity_summary(canonical, subject_namespaces=subjects)
        doc["inventory"]["identity"] = identity
        typography = identity["typography"]
        typography["specimen"] = {
            "state": "verified", "note": "Claimed asset.",
            "asset": {
                "state": "verified", "family": "DM Sans",
                "declaration": "styles/type.css:1",
                "url": "/fonts/dm-sans.woff2", "path": relative,
                "format": "woff2",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            },
        }
        doc["discovery"].update({
            "repository": {"root": root},
            "owned_import_graph": {
                "reachable": {
                    "styles/type.css": {"depth": 0, "via": []},
                    "styles/colors.css": {"depth": 0, "via": []},
                },
            },
        })
        brand = identity["brand_colors"]
        html = (
            "<!-- SLOT:inventory-color -->%s<!-- /SLOT:inventory-color -->"
            "<!-- SLOT:inventory-type -->%s<!-- /SLOT:inventory-type -->"
        ) % (
            render_discovery.color_block([], brand),
            render_discovery.typography_block(
                doc["inventory"]["concepts"], typography, root),
        )
        self.assertEqual(
            validate_run.rule_16_identity_integrity(doc, html).rule,
            "16-identity-integrity",
        )


class TestRule17AdoptionStrategy(unittest.TestCase):
    def test_strategy_section_accepts_report_view_metadata(self):
        doc = good_doc()
        strategy = validate_run.derive_adoption_strategy(doc)
        doc["adoption_strategy"] = strategy
        html = (
            '<section id="strategy" data-report-views="action evidence">%s</section>'
            '<footer></footer>' % render_discovery.render_adoption_strategy(strategy)
        )

        self.assertIsNone(validate_run.rule_17_adoption_strategy(doc, html))


class TestStampOnlyMarksAPassingRun(unittest.TestCase):
    # Borrow the shell builder rather than subclassing the parity case —
    # inheriting a TestCase re-runs every one of its tests under this name.
    inventory_tabs_shell = TestRule6HtmlJsonParity.inventory_tabs_shell

    """provenance.validation_gate is the one field a report must not set
    itself — only a passing tools/validate_run.py --stamp run may write it.
    A report that skips the gate must keep showing the un-gated banner."""

    def write_report(self, root, doc):
        path = os.path.join(root, "report.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
        return path

    def gated_pair(self):
        """A doc and the HTML a real render would produce for it, banner and all.

        The stamp has to survive the same HTML the gate accepts, so this
        builds through render_report_slots rather than hand-writing a shell:
        a minimal fixture would fail rule 6's report-view contract and prove
        nothing about the banner.
        """
        doc = good_doc()
        doc.setdefault("rendering", {}).update({
            "view": "snapshot",
            "available_views": list(render_discovery.REPORT_VIEWS),
        })
        slots = (
            "at-a-glance", "exec-summary", "decisions", "fix-queue",
            "groups", "lineage", "coverage-matrix", "next-steps",
            "modes-coverage", "modes-gaps", "orphans", "enforcement",
        )
        shell = self.inventory_tabs_shell() + "".join(
            "<!-- SLOT:%s --><!-- /SLOT:%s -->" % (name, name) for name in slots
        )
        banner = (
            '<!-- SLOT:validation-banner -->'
            '<div class="validation-banner" role="alert">'
            '<strong>\u26a0 Not validated.</strong> placeholder</div>'
            '<!-- /SLOT:validation-banner -->'
        )
        rendered = render_discovery.render_report_slots(
            shell, doc, None,
            {"repository": {"root": "/tmp/repo", "ref": "abc123"}},
        )
        return doc, banner + rendered

    def test_stamp_writes_passed_true_into_the_json(self):
        with tempfile.TemporaryDirectory() as root:
            doc, _ = self.gated_pair()
            path = self.write_report(root, doc)
            rc = validate_run.main([path, "--stamp"])
            self.assertEqual(rc, validate_run.EXIT_OK)
            with open(path, encoding="utf-8") as fh:
                stamped = json.load(fh)
            gate = stamped["provenance"]["validation_gate"]
            self.assertTrue(gate["passed"])
            self.assertEqual(gate["exit_code"], 0)
            self.assertTrue(gate["checked_at"])

    def test_stamp_clears_the_html_banner_on_pass(self):
        with tempfile.TemporaryDirectory() as root:
            doc, html = self.gated_pair()
            report_path = self.write_report(root, doc)
            html_path = os.path.join(root, "report.html")
            with open(html_path, "w", encoding="utf-8") as fh:
                fh.write(html)
            rc = validate_run.main([report_path, "--html", html_path, "--stamp"])
            self.assertEqual(rc, validate_run.EXIT_OK)
            with open(html_path, encoding="utf-8") as fh:
                stamped_html = fh.read()
            self.assertNotIn("Not validated", stamped_html)
            self.assertIn("validation-ok", stamped_html)
            self.assertIn("Validated", stamped_html)

    def test_a_failing_run_is_never_stamped(self):
        with tempfile.TemporaryDirectory() as root:
            d, _ = self.gated_pair()
            d["discovery"]["token_sources"] = []
            d["stack"] = {"token_sources": []}
            path = self.write_report(root, d)
            rc = validate_run.main([path, "--stamp"])
            self.assertEqual(rc, validate_run.EXIT_FINDING)
            with open(path, encoding="utf-8") as fh:
                unstamped = json.load(fh)
            self.assertNotIn("validation_gate", unstamped.get("provenance", {}))

    def test_without_the_stamp_flag_a_passing_run_leaves_the_file_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            doc, _ = self.gated_pair()
            path = self.write_report(root, doc)
            with open(path, encoding="utf-8") as fh:
                before = fh.read()
            rc = validate_run.main([path])
            self.assertEqual(rc, validate_run.EXIT_OK)
            with open(path, encoding="utf-8") as fh:
                after = fh.read()
            self.assertEqual(before, after)
            doc = json.loads(after)
            self.assertNotIn("validation_gate", doc.get("provenance", {}))

    def test_stamp_with_no_html_file_only_touches_the_json(self):
        with tempfile.TemporaryDirectory() as root:
            doc, _ = self.gated_pair()
            path = self.write_report(root, doc)
            rc = validate_run.main([path, "--stamp"])
            self.assertEqual(rc, validate_run.EXIT_OK)
            self.assertFalse(os.path.exists(os.path.join(root, "report.html")))


if __name__ == "__main__":
    unittest.main()
