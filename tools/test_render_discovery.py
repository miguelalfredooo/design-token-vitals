"""Tests for universal discovery report rendering."""
import json
import hashlib
from html.parser import HTMLParser
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover_environment  # noqa: E402
import analyze_component_usage  # noqa: E402
import render_discovery  # noqa: E402


class InventoryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.details_depth = 0
        self.details_open = []
        self.visible_rows = []
        self.tail_rows = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "details":
            self.details_depth += 1
            if "data-token-inventory-more" in attributes:
                self.details_open.append("open" in attributes)
        if tag == "tr" and "data-token-concept" in attributes:
            target = self.tail_rows if self.details_depth else self.visible_rows
            target.append(attributes)

    def handle_endtag(self, tag):
        if tag == "details":
            self.details_depth -= 1


def fixture():
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
    return root, discover_environment.discover(
        root, ["app/**", "components/**"])


class TestRendering(unittest.TestCase):
    def test_inventory_tab_controller_is_fixed_and_keyboard_complete(self):
        rendered = render_discovery.render_report_slots(
            "<!-- SLOT:inventory-tabs-script --><!-- /SLOT:inventory-tabs-script -->",
            {}, None, {"repository": {}},
        )
        self.assertEqual(rendered.count(render_discovery.INVENTORY_TABS_SCRIPT), 1)
        for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
            self.assertIn(key, rendered)
        self.assertIn('window.addEventListener("hashchange"', rendered)
        self.assertIn('window.addEventListener("beforeprint"', rendered)
        self.assertIn('window.addEventListener("afterprint"', rendered)
        self.assertIn("disclosure.open = wasOpen", rendered)
        self.assertIn("const setReportView", rendered)
        self.assertIn("revealHashTarget", rendered)
        self.assertIn("target.scrollIntoView", rendered)
        self.assertIn('document.documentElement.classList.add("report-views--ready")', rendered)
        self.assertIn(
            'disclosure.open = disclosure.dataset.reportDefaultOpen === "true"',
            rendered,
        )

    def test_progressive_disclosures_are_open_without_script_and_restore_defaults(self):
        document = (
            '<details><summary>Closed by default</summary><p>A</p></details>'
            '<details open class="kept"><summary>Open by default</summary><p>B</p></details>'
        )

        rendered = render_discovery.prepare_progressive_disclosures(document)

        self.assertIn(
            '<details open data-report-default-open="false">', rendered
        )
        self.assertIn(
            '<details open data-report-default-open="true" class="kept">',
            rendered,
        )
        self.assertEqual(
            render_discovery.prepare_progressive_disclosures(rendered), rendered
        )

    def test_report_view_switcher_has_three_plain_language_choices(self):
        rendered = render_discovery.render_report_view_switcher("action")
        self.assertIn('data-report-view-default="action"', rendered)
        self.assertIn('data-report-views-json="[&quot;snapshot&quot;,&quot;action&quot;,&quot;evidence&quot;]"', rendered)
        self.assertEqual(rendered.count('data-report-view-button="'), 3)
        self.assertIn(
            'data-report-view-button="action" aria-pressed="true"', rendered
        )
        for label, helper in (
                ("Snapshot", "What matters now"),
                ("Action Plan", "What to do next"),
                ("Evidence", "How we know")):
            self.assertIn("<strong>%s</strong>" % label, rendered)
            self.assertIn("<span>%s</span>" % helper, rendered)

    def test_report_view_resolution_defaults_and_rejects_unknown_values(self):
        self.assertEqual(render_discovery.resolve_report_view(), "snapshot")
        self.assertEqual(
            render_discovery.resolve_report_view("evidence"), "evidence"
        )
        with self.assertRaisesRegex(ValueError, "report view must be one of"):
            render_discovery.resolve_report_view("brief")

    def test_measurement_names_initial_view_and_density(self):
        _root, discovery = fixture()
        rendered = render_discovery.render_measurement(
            discovery,
            {"concept_count": 1, "sources": []},
            {
                "schema_version": "1",
                "rendering": {"view": "action", "tier": "collapsed"},
                "provenance": {"adapter_versions": {}},
            },
            "local-test",
            "2026-09-03T00:00:00Z",
        )
        self.assertIn("action view · collapsed density", rendered)

    def test_provenance_separates_confirmed_sources_and_actionable_imports(self):
        _root, discovery = fixture()
        discovery["import_graph"]["unresolved"] = [
            {"reason": "external package"},
            {"reason": "missing local source"},
            {"reason": "unsupported resolver"},
        ]
        tokens = {
            "concept_count": 4,
            "sources": [
                {"role": "canonical"},
                {"role": "alias"},
                {"role": "candidate"},
                {"role": "consumer-override"},
            ],
            "candidate_or_local_override_sources": [{}, {}],
        }
        report = {
            "schema_version": "1",
            "rendering": {"view": "snapshot", "tier": "full"},
            "provenance": {"adapter_versions": {}},
        }

        measurement = render_discovery.render_measurement(
            discovery, tokens, report, "local-test", "2026-09-03T00:00:00Z"
        )
        runhead = render_discovery.render_runhead(
            discovery, tokens, report, "local-test"
        )

        self.assertIn("2 confirmed definition sources", measurement)
        self.assertIn("2 confirmed definition sources", runhead)
        self.assertIn("2 actionable imports remain unresolved", measurement)
        self.assertIn("All 3 classified import misses", measurement)
        self.assertIn("1 external package; 1 missing local source", measurement)
        self.assertIn("1 unsupported resolver", measurement)

    def test_template_sections_follow_the_fixed_view_contract(self):
        with open(render_discovery.TEMPLATE_PATH, encoding="utf-8") as handle:
            template = handle.read()
        for section_id, views in render_discovery.REPORT_VIEW_SECTIONS.items():
            if section_id == "discovery-engine":
                continue
            tag = re.search(
                r'<section\b[^>]*\bid="%s"[^>]*>' % re.escape(section_id),
                template,
            )
            self.assertIsNotNone(tag, section_id)
            self.assertIn(
                'data-report-views="%s"' % " ".join(views), tag.group(0)
            )
        self.assertNotIn('section data-report-views="', template)
        self.assertNotIn('section hidden', template)
        self.assertIn(
            'section[data-report-views] { display: block !important; }', template
        )

    def test_template_has_accessible_inventory_family_relationships(self):
        with open(render_discovery.TEMPLATE_PATH, encoding="utf-8") as handle:
            template = handle.read()
        self.assertIn('role="tablist"', template)
        self.assertEqual(template.count('role="tab"'), 3)
        self.assertEqual(template.count('role="tabpanel"'), 3)
        for family in ("color", "typography", "foundation"):
            self.assertIn(
                'aria-controls="inventory-panel-%s"' % family, template)
            self.assertIn(
                'id="inventory-panel-%s" aria-labelledby="inventory-tab-%s"' % (
                    family, family), template)
        self.assertNotIn('role="tabpanel" hidden', template)
        self.assertIn('display: none; gap: 4px;', template)
        self.assertIn(
            '.token-tabs--ready .token-tabs__list { display: flex; }',
            template,
        )
        self.assertIn('<!-- SLOT:inventory-tabs-script -->', template)

    def test_dashboard_links_have_visible_keyboard_focus(self):
        with open(render_discovery.TEMPLATE_PATH, encoding="utf-8") as handle:
            template = handle.read()
        self.assertIn(".dashboard-action:focus-visible", template)
        self.assertIn(".dashboard-readiness:focus-visible", template)
        self.assertIn(".dashboard-vital:focus-visible", template)
        self.assertIn(".dashboard-link:focus-visible", template)

    def test_dashboard_keeps_evidence_and_plain_language_with_an_empty_fix_queue(self):
        rendered = render_discovery.render_at_a_glance({
            "stage": {
                "current": "declared", "next": "adopted",
                "threshold": "Resolve semantic equivalence.",
            },
            "vitals": {
                "coverage": {"grade": "attention"},
                "enforcement": {"grade": "blocked"},
            },
            "executive_summary": {"confidence_split": {
                "confirmed": 2, "blocked": 1, "unmeasured": 1,
            }},
            "leakage_analysis": {
                "consumer_files_scanned": 4,
                "exact_value_candidates": [{"id": "one"}],
                "uncovered_candidates": [{"id": "two"}],
            },
            "fix_queue": [],
            "run": {"token_count": 20, "files_scanned": 4},
            "rendering": {"tier": "full"},
            "inventory": {
                "families": {},
                "identity": {
                    "typography": {"state": "verified", "family": "DM Sans"},
                    "brand_colors": {"state": "verified", "colors": [{
                        "token": "brand-primary", "value": "#5b4bd6",
                    }]},
                },
            },
            "component_usage": {"top_20": [{
                "name": "layout / qotd", "distinct_tokens": 12,
                "references": 30,
            }]},
            "discovery": {"roots": [{
                "path": "app.scss", "ownership": "unknown",
                "profiles": ["discourse"],
            }]},
        })
        self.assertIn('class="dashboard" data-report-region="at-a-glance"', rendered)
        self.assertIn("Your token foundation is in place", rendered)
        self.assertIn("You’re here", rendered)
        self.assertIn("How the system is doing", rendered)
        self.assertIn("What we could verify", rendered)
        self.assertIn("Needs evidence", rendered)
        self.assertIn("DM Sans", rendered)
        self.assertIn("brand-primary", rendered)
        self.assertIn("layout / qotd", rendered)
        self.assertIn("Discourse", rendered)
        self.assertIn('class="ladder" data-glance-mark="stage"', rendered)
        self.assertEqual(rendered.count('class="seg" data-glance-mark='), 3)
        self.assertIn('class="dashboard-progress" data-glance-mark="fix-queue"', rendered)
        self.assertEqual(rendered.count("data-glance-mark="), 6)
        self.assertIn('data-fix-total="0" data-fix-verified="0"', rendered)
        self.assertIn('style="width:0.000%"', rendered)
        self.assertIn("No automatic changes are queued yet", rendered)
        self.assertIn('class="dashboard-readiness" href="#fix-queue"', rendered)
        self.assertIn('href="#measurement"', rendered)
        self.assertIn("Review ownership", rendered)
        self.assertNotIn("<svg", rendered)

    def test_dashboard_component_roadmap_shows_five_evidenced_rows(self):
        components = [{
            "id": "component-%d" % index,
            "rank": index,
            "name": "app / component-%d" % index,
            "kind": "component",
            "references": 7 - index,
            "distinct_tokens": index,
        } for index in range(1, 7)]
        roadmap = analyze_component_usage.build_roadmap(components)

        rendered = render_discovery.render_dashboard_component_roadmap({
            "component_usage": {
                "state": "measured",
                "roadmap": roadmap,
                "top_20": components,
            },
        })

        self.assertIn(
            "Where component token work has the widest footprint", rendered
        )
        self.assertIn('data-dashboard-component-roadmap-json=', rendered)
        self.assertEqual(rendered.count('data-dashboard-component="'), 5)
        self.assertIn('role="region" tabindex="0"', rendered)
        self.assertIn('aria-labelledby="dashboard-component-roadmap-title"', rendered)
        self.assertIn('href="#component-detail-component-1"', rendered)
        self.assertIn('data-component-paths="0"', rendered)
        self.assertIn("app / component-5", rendered)
        self.assertNotIn("app / component-6", rendered)
        self.assertIn("Assess first", rendered)
        self.assertIn("Plan next", rendered)
        self.assertIn("Focused follow-up", rendered)
        self.assertIn("95.2%", rendered)

    def test_dashboard_calls_mixed_component_and_surface_rows_entries(self):
        components = [
            {
                "id": "component", "rank": 1, "name": "app / component",
                "kind": "component", "references": 2,
                "distinct_tokens": 1, "paths": ["app/component.scss"],
            },
            {
                "id": "surface", "rank": 2, "name": "app / route",
                "kind": "surface", "references": 1,
                "distinct_tokens": 1, "paths": ["app/routes/home.ts"],
            },
        ]
        roadmap = analyze_component_usage.build_roadmap(components)

        rendered = render_discovery.render_dashboard_component_roadmap({
            "component_usage": {
                "state": "measured", "fallback_surfaces": 1,
                "roadmap": roadmap, "top_20": components,
            },
        })

        self.assertIn("These 2 entries", rendered)
        self.assertIn("Explore all 2 entries", rendered)
        self.assertIn("component and surface token work", rendered)

    def test_dashboard_side_copy_names_fallback_surfaces(self):
        rendered = render_discovery.render_at_a_glance({
            "stage": {"current": "unresolved"},
            "vitals": {}, "executive_summary": {"confidence_split": {}},
            "leakage_analysis": {}, "fix_queue": [],
            "run": {"token_count": 0, "files_scanned": 1},
            "inventory": {"families": {}, "identity": {}},
            "component_usage": {
                "fallback_surfaces": 1,
                "top_20": [{
                    "name": "app / route", "kind": "surface",
                    "references": 3, "distinct_tokens": 1,
                }],
            },
            "discovery": {"roots": []},
        })

        self.assertIn("Most connected component or surface", rendered)
        self.assertIn("See the top 1 entry", rendered)

    def test_single_fallback_roadmap_uses_singular_copy(self):
        components = [{
            "id": "surface", "rank": 1, "name": "app / route",
            "kind": "surface", "references": 3, "distinct_tokens": 1,
            "paths": ["app/routes/home.ts"],
        }]
        roadmap = analyze_component_usage.build_roadmap(components)

        rendered = render_discovery.render_dashboard_component_roadmap({
            "component_usage": {
                "state": "measured", "fallback_surfaces": 1,
                "roadmap": roadmap, "top_20": components,
            },
        })

        self.assertIn("This component or surface accounts for", rendered)
        self.assertIn("Explore all 1 entry", rendered)

    def test_dashboard_does_not_promote_blocked_identity_candidates(self):
        rendered = render_discovery.render_at_a_glance({
            "stage": {"current": "unresolved"},
            "vitals": {},
            "executive_summary": {"confidence_split": {}},
            "leakage_analysis": {},
            "fix_queue": [],
            "run": {"token_count": 3, "files_scanned": 1},
            "inventory": {
                "families": {
                    "color": {"state": "measured"},
                    "typography": {"state": "unmeasured"},
                },
                "identity": {
                    "typography": {
                        "state": "blocked", "family": "DM Sans",
                        "candidates": [{"family": "DM Sans"}],
                    },
                    "brand_colors": {
                        "state": "blocked",
                        "colors": [{"token": "brand-primary", "value": "#5b4bd6"}],
                    },
                },
            },
            "discovery": {
                "environment": ["discourse", "rails-sprockets", "monorepo"],
                "roots": [],
            },
        })
        self.assertIn("across 1 measured family", rendered)
        self.assertIn("1 measured family · 1 family needs evidence", rendered)
        self.assertIn("Candidates: DM Sans", rendered)
        self.assertIn('data-font-verified="false"', rendered)
        self.assertNotIn("brand-primary", rendered)
        self.assertIn("Brand colors need stronger source evidence", rendered)
        self.assertIn("Discourse + Rails Sprockets + Monorepo", rendered)

    def test_dashboard_distinguishes_absent_families_from_evidence_gaps(self):
        rendered = render_discovery.render_at_a_glance({
            "stage": {"current": "declared"},
            "vitals": {"coverage": {"grade": "blocked"}},
            "executive_summary": {"confidence_split": {}},
            "leakage_analysis": {},
            "fix_queue": [],
            "run": {"token_count": 4, "files_scanned": 2},
            "inventory": {"families": {
                "color": {"state": "measured"},
                "motion": {"state": "unmeasured"},
                "elevation": {"state": "absent"},
            }},
            "discovery": {"roots": []},
        })

        self.assertIn(
            "1 measured family · 1 family needs evidence · 1 absent family",
            rendered,
        )
        self.assertNotIn("2 families need evidence", rendered)
        self.assertIn("More evidence needed", rendered)

    def test_dashboard_does_not_overstate_an_ungraded_run(self):
        rendered = render_discovery.render_at_a_glance({
            "stage": {"current": "unresolved"},
            "vitals": {},
            "executive_summary": {"confidence_split": {}},
            "leakage_analysis": {},
            "fix_queue": [],
            "run": {"token_count": 0, "files_scanned": 0},
            "inventory": {"families": {}},
            "discovery": {"roots": []},
        })

        self.assertIn("Not yet graded", rendered)
        self.assertNotIn("Well supported", rendered)

    def test_stage_summary_handles_a_punctuated_threshold(self):
        rendered = render_discovery.stage_summary({"stage": {
            "current": "declared", "next": "adopted",
            "threshold": "Resolve semantic equivalence.",
        }})
        self.assertNotIn("equivalence..", rendered)
        self.assertNotIn("equivalence.,", rendered)
        self.assertIn("equivalence. <b>Then:</b>", rendered)

    def test_large_token_inventory_uses_see_more_without_dropping_rows(self):
        for count in (19, 20, 21, 25):
            concepts = [{
                "name": "space-%02d" % index, "family": "spacing",
                "values": ["%dpx" % index],
                "representations": ["css-custom-property"],
                "sites": ["tokens.css:%d" % index],
                "definitions": [{"value": "%dpx" % index}],
            } for index in range(count)]
            rendered = render_discovery.concept_inventory_table(concepts)
            parsed = InventoryParser()
            parsed.feed(rendered)

            self.assertEqual(len(parsed.visible_rows), min(count, 20))
            self.assertEqual(len(parsed.tail_rows), max(count - 20, 0))
            self.assertFalse(any(parsed.details_open))
            for index, attributes in enumerate(
                    parsed.visible_rows + parsed.tail_rows):
                self.assertEqual(attributes["data-token-concept"], "space-%02d" % index)
                for name in (
                        "data-token-family", "data-token-representations-json",
                        "data-token-sites-json", "data-token-values-json",
                        "data-token-definitions-json"):
                    self.assertIn(name, attributes)
            if count > 20:
                self.assertIn(
                    'data-token-inventory-more="%d"' % (count - 20), rendered)
                self.assertIn("See %d more tokens" % (count - 20), rendered)
            else:
                self.assertNotIn("data-token-inventory-more", rendered)

    def test_typography_uses_discovered_quoted_or_unquoted_family(self):
        quoted = render_discovery.typography_block([{
            "name": "font-family", "family": "typography",
            "values": ['"DM Sans", sans-serif'], "representations": [],
            "sites": ["styles/type.css:1"],
        }], {
            "state": "verified", "family": "DM Sans", "token": "font-family",
            "confidence": "explicit-family-token",
            "evidence": ["styles/type.css:1"],
        })
        unquoted = render_discovery.typography_block([{
            "name": "font-family", "family": "typography",
            "values": ["Inter, system-ui, sans-serif"], "representations": [],
            "sites": ["styles/type.css:1"],
        }], {
            "state": "verified", "family": "Inter", "token": "font-family",
            "confidence": "explicit-family-token",
            "evidence": ["styles/type.css:1"],
        })
        self.assertIn("Verified family: DM Sans", quoted)
        self.assertIn("Verified family: Inter", unquoted)

    def test_blocked_typography_renders_no_generic_specimen(self):
        rendered = render_discovery.typography_block([{
            "name": "font-size-body", "family": "typography",
            "values": ["16px"], "representations": [],
            "sites": ["styles/type.css:1"],
        }], {
            "state": "blocked", "confidence": "unresolved",
            "family": None, "token": None, "evidence": [],
            "note": "No concrete family.",
        })
        self.assertNotIn('class="typescale"', rendered)
        self.assertNotIn("font-family:inherit", rendered)
        self.assertIn("Typography identity is blocked", rendered)

    def test_blocked_typography_surfaces_conflicting_candidates(self):
        rendered = render_discovery.typography_block([], {
            "state": "blocked", "confidence": "unresolved",
            "family": None, "token": None, "evidence": [],
            "specimen": {"state": "blocked", "asset": None},
            "candidates": [{
                "family": "DM Sans", "token": "font-family", "priority": 100,
                "evidence": ["a.css:1"],
            }, {
                "family": "Inter", "token": "font-family", "priority": 100,
                "evidence": ["b.css:1"],
            }],
        })
        self.assertIn('data-typography-candidates="2"', rendered)
        self.assertIn('data-typography-candidate-family="DM Sans"', rendered)
        self.assertIn('data-typography-candidate-priority="100"', rendered)
        self.assertIn('data-typography-candidate-evidence="b.css:1"', rendered)

    def test_typography_embeds_verified_repository_font(self):
        root = tempfile.mkdtemp()
        relative = "public/fonts/acme.woff2"
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        payload = b"wOF2self-contained-font"
        with open(path, "wb") as handle:
            handle.write(payload)
        style_path = os.path.join(root, "styles/type.css")
        os.makedirs(os.path.dirname(style_path), exist_ok=True)
        with open(style_path, "w", encoding="utf-8") as handle:
            handle.write(
                '@font-face { font-family: "Acme Sans"; '
                'src: url("/fonts/acme.woff2") format("woff2"); }\n')
        digest = hashlib.sha256(payload).hexdigest()
        rendered = render_discovery.typography_block([{
            "name": "font-size-body", "family": "typography",
            "values": ["16px"], "representations": [],
            "sites": ["styles/type.css:2"],
        }], {
            "state": "verified", "family": "Acme Sans",
            "token": "font-family", "confidence": "explicit-family-token",
            "evidence": ["styles/type.css:1"],
            "specimen": {
                "state": "verified", "note": "Verified asset.",
                "asset": {
                    "state": "verified", "family": "Acme Sans",
                    "declaration": "styles/type.css:1",
                    "url": "/fonts/acme.woff2", "path": relative,
                    "sha256": digest, "format": "woff2",
                    "size_bytes": len(payload),
                },
            },
        }, root)
        self.assertIn("data:font/woff2;base64,", rendered)
        self.assertIn('data-typography-specimen-state="verified"', rendered)
        self.assertIn('font-family:Token Vitals Identity', rendered)
        self.assertNotIn("sans-serif", rendered)

    def test_brand_colors_are_surfaced_as_verified_swatches(self):
        concepts = [{
            "name": "acme-brand", "family": "color", "values": ["#123456"],
            "representations": ["css-custom-property"],
            "sites": ["styles/colors.css:1"],
        }]
        rendered = render_discovery.color_block(concepts, {
            "state": "verified", "confidence": "explicit-brand-semantics",
            "note": "Only explicit brand semantics.",
            "colors": [{
                "token": "acme-brand", "value": "#123456",
                "confidence": "explicit-brand-token-name",
                "evidence": ["styles/colors.css:1"],
            }],
        })
        self.assertIn('data-brand-color="acme-brand"', rendered)
        self.assertIn('style="background:#123456"', rendered)
        self.assertIn("Full color inventory", rendered)

    def test_brand_conflicts_are_visible_and_not_swatched(self):
        rendered = render_discovery.color_block([], {
            "state": "blocked", "confidence": "unresolved", "colors": [],
            "conflicts": [{
                "token": "brand-primary", "values": ["#111111", "#abcdef"],
                "evidence": ["a.scss:1", "b.scss:1"],
                "reason": "multiple concrete values lack explicit mode provenance",
            }],
        })
        self.assertIn('data-brand-conflict="brand-primary"', rendered)
        self.assertIn('data-brand-conflicts-blocked="1"', rendered)
        self.assertNotIn('data-brand-color="brand-primary"', rendered)

    def test_leakage_sync_refreshes_denominators(self):
        report = {
            "run": {"files_scanned": 1},
            "executive_summary": {"affected": {"owned_files": 1}},
            "vitals": {"leakage": {}},
        }
        render_discovery.sync_leakage(report, {
            "consumer_files_scanned": 42,
            "exact_value_candidates": [{"id": "a"}],
            "uncovered_candidates": [{"id": "b"}, {"id": "c"}],
            "semantic_equivalence": "unmeasured",
            "near_miss": "unmeasured",
        })
        self.assertEqual(report["run"]["files_scanned"], 42)
        self.assertEqual(report["executive_summary"]["affected"]["owned_files"], 42)
        self.assertIn("across 42 owned", report["vitals"]["leakage"]["note"])

    def test_nothing_scanned_reports_no_tier_counts(self):
        """Zero scanned files cannot yield a count of zero findings.

        This is the skill's own rule 4, applied to itself: zero states the
        project has none, which a run that scanned nothing never
        established. The strategy section then printed "exact-value
        candidate 0" beside "redundant unmeasured" — one sentence answering
        the same question two ways.
        """
        report = {"run": {}, "executive_summary": {}, "vitals": {"leakage": {}}}
        render_discovery.sync_leakage(report, {
            "consumer_files_scanned": 0,
            "exact_value_candidates": [],
            "uncovered_candidates": [],
        })
        tiers = report["vitals"]["leakage"]["tiers"]
        self.assertEqual(report["vitals"]["leakage"]["grade"], "blocked")
        self.assertTrue(
            all(value is None for value in tiers.values()),
            "a run that scanned nothing reported a tier count: %r" % tiers)
        self.assertIn("no owned reachable consumer styles",
                      report["vitals"]["leakage"]["note"])

    def test_an_empty_trend_block_is_removed_like_a_missing_one(self):
        """No baseline means no trend section, however the block is spelled.

        The stripper tested `if not report.get("trend")`, so a schema-shaped
        block of nulls survived and shipped the template's own sample
        comparison — which the validation gate then caught as leftover
        sample content, once, on every fresh report.
        """
        document = (
            '<body data-report-view="snapshot">'
            '\n  <a href="#trend" data-tier="full">Trend</a>'
            '\n  <section id="trend" data-report-views="action evidence">'
            '\n    <b>Compared against <code>a91f4c07</code>.</b>'
            '\n  </section>\n'
            '</body>'
        )
        report = {"trend": {"baseline_ref": None, "compatible": None,
                            "new": [], "resolved": [], "grew": [],
                            "shrank": [], "regressions": []}}
        stripped = render_discovery.strip_trend_without_a_baseline(document, report)
        self.assertNotIn("a91f4c07", stripped)
        self.assertNotIn('id="trend"', stripped)
        self.assertNotIn('href="#trend"', stripped)

    def test_family_block_keeps_every_source_visible(self):
        sources = ["styles/source-%d.scss:%d" % (index, index)
                   for index in range(1, 7)]
        tokens = {
            "family_counts": {"typography": 1},
            "concepts": [{
                "id": "font-family", "family": "typography",
                "sites": sources, "representations": [], "values": [],
            }],
        }
        rendered = render_discovery.family_block(tokens, {"inventory": {}})
        for source in sources:
            path = source.rsplit(":", 1)[0]
            self.assertIn('data-family-source="%s"' % path, rendered)
        self.assertIn("Show 2 more sources", rendered)

    def test_leakage_block_keeps_every_location_visible(self):
        locations = ["styles/a.scss:1", "styles/b.scss:2", "styles/c.scss:3"]
        rendered = render_discovery.render_leakage({
            "consumer_files_scanned": 3,
            "exact_value_candidates": [{
                "id": "abc123", "tier": "exact-value candidate",
                "literal": "#fff", "token_candidates": ["--surface"],
                "occurrences": 3, "files": 3, "properties": ["color"],
                "locations": locations,
            }],
            "uncovered_candidates": [],
        })
        for location in locations:
            self.assertIn('data-finding-location="%s"' % location, rendered)
        self.assertIn("Show 2 more locations", rendered)

    def test_section_contains_profiles_ladder_and_all_roots(self):
        _, discovery = fixture()
        section = render_discovery.render_section(discovery)
        self.assertIn('data-profile="nextjs"', section)
        self.assertIn('data-capability="production_roots"', section)
        for root in discovery["roots"]:
            self.assertIn('data-discovery-root="%s"' % root["path"], section)

    def test_section_keeps_partial_profiles_and_application_candidates_visible(self):
        _, discovery = fixture()
        discovery["profile_composition"]["candidates"] = [{
            "id": "vite", "kind": "build-tool", "score": 0.5,
            "evidence": [{"path": "src/main.ts"}],
            "missing_signals": [{"type": "path_any", "patterns": ["vite.config.ts"]}],
        }]
        discovery["profile_composition"]["application_candidates"] = [{
            "path": "apps/site", "package": "site", "markers": ["next.config.mjs"],
        }]

        section = render_discovery.render_section(discovery)

        self.assertIn('data-profile-candidate="vite"', section)
        self.assertIn('data-application-candidate="apps/site"', section)

    def test_repository_content_is_escaped(self):
        _, discovery = fixture()
        discovery["roots"][0]["evidence"] = '<img src=x onerror="bad">'
        section = render_discovery.render_section(discovery)
        self.assertNotIn("<img", section)
        self.assertIn("&lt;img", section)

    def test_augment_merges_discovery_and_tokens(self):
        root, discovery = fixture()
        discovery_path = os.path.join(root, "discovery.json")
        tokens_path = os.path.join(root, "tokens.json")
        report_path = os.path.join(root, "report.json")
        html_path = os.path.join(root, "report.html")
        with open(discovery_path, "w", encoding="utf-8") as handle:
            json.dump(discovery, handle)
        with open(tokens_path, "w", encoding="utf-8") as handle:
            json.dump({"sources": [
                {
                    "path": "app/a-candidate.js", "role": "candidate",
                    "reachable_from": ["app/layout.tsx"],
                    "confidence": "import-graph verified", "declarations": 1,
                },
                {
                    "path": "app/globals.css", "role": "canonical",
                    "reachable_from": ["app/layout.tsx"],
                    "confidence": "import-graph verified", "declarations": 1,
                },
            ]}, handle)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump({"run": {"generated_at": "old"},
                       "provenance": {"generated_at": "old", "skill_version": "old"}}, handle)
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write('<html><section id="measurement"></section></html>')
        render_discovery.augment(
            discovery_path, report_path, html_path, tokens_path)
        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        self.assertEqual(report["rendering"]["view"], "snapshot")
        self.assertEqual(
            report["rendering"]["available_views"],
            list(render_discovery.REPORT_VIEWS),
        )
        self.assertEqual(
            report["discovery"]["capabilities"]["token_source_discovery"],
            "verified",
        )
        self.assertEqual(report["discovery"]["token_sources"][0]["classification"],
                         "consumer")
        token_step = next(
            item for item in report["discovery"]["capability_ladder"]["steps"]
            if item["capability"] == "token_source_discovery"
        )
        self.assertEqual(token_step["evidence"], ["app/globals.css"])
        self.assertNotIn("framework_versions", report["run"])
        with open(html_path, encoding="utf-8") as handle:
            self.assertIn('id="discovery-engine"', handle.read())

    def test_augment_supports_legacy_measurement_section(self):
        root, discovery = fixture()
        discovery_path = os.path.join(root, "discovery.json")
        report_path = os.path.join(root, "report.json")
        html_path = os.path.join(root, "report.html")
        with open(discovery_path, "w", encoding="utf-8") as handle:
            json.dump(discovery, handle)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump({"run": {}, "provenance": {}}, handle)
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(
                '<html><body><section>\n'
                '    <div class="eyebrow">Measurement</div>'
                '</section></body></html>'
            )

        render_discovery.augment(discovery_path, report_path, html_path)

        with open(html_path, encoding="utf-8") as handle:
            rendered = handle.read()
        self.assertIn('id="discovery-engine"', rendered)
        self.assertLess(
            rendered.index('id="discovery-engine"'),
            rendered.index('<div class="eyebrow">Measurement</div>'),
        )

    def test_augment_records_and_renders_requested_report_view(self):
        root, discovery = fixture()
        discovery_path = os.path.join(root, "discovery.json")
        report_path = os.path.join(root, "report.json")
        html_path = os.path.join(root, "report.html")
        with open(discovery_path, "w", encoding="utf-8") as handle:
            json.dump(discovery, handle)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump({"run": {}, "provenance": {}}, handle)
        with open(render_discovery.TEMPLATE_PATH, encoding="utf-8") as handle:
            template = handle.read()
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write(template)

        render_discovery.augment(
            discovery_path, report_path, html_path,
            refresh_template=True, report_view="evidence",
        )

        with open(report_path, encoding="utf-8") as handle:
            report = json.load(handle)
        with open(html_path, encoding="utf-8") as handle:
            rendered = handle.read()
        self.assertEqual(report["rendering"]["view"], "evidence")
        self.assertIn('<body data-report-view="evidence">', rendered)
        self.assertIn('data-report-view-default="evidence"', rendered)
        self.assertIn(
            'data-report-view-button="evidence" aria-pressed="true"', rendered
        )
        self.assertNotIn('<section id="trend"', rendered)
        self.assertNotIn("a91f4c07", rendered)
        disclosure_tags = re.findall(r'<details\b[^>]*>', rendered)
        self.assertTrue(disclosure_tags)
        self.assertTrue(all(" open " in tag for tag in disclosure_tags))
        self.assertTrue(all(
            'data-report-default-open="' in tag for tag in disclosure_tags
        ))

    def test_invalid_html_does_not_partially_update_report_json(self):
        root, discovery = fixture()
        discovery_path = os.path.join(root, "discovery.json")
        report_path = os.path.join(root, "report.json")
        html_path = os.path.join(root, "report.html")
        original = {"run": {"generated_at": "old"}, "provenance": {}}
        with open(discovery_path, "w", encoding="utf-8") as handle:
            json.dump(discovery, handle)
        with open(report_path, "w", encoding="utf-8") as handle:
            json.dump(original, handle)
        with open(html_path, "w", encoding="utf-8") as handle:
            handle.write("<html><body>No measurement section</body></html>")

        with self.assertRaisesRegex(ValueError, "no discovery-engine"):
            render_discovery.augment(discovery_path, report_path, html_path)

        with open(report_path, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), original)


if __name__ == "__main__":
    unittest.main()
