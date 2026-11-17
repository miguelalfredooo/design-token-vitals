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


def template_text():
    """Read the report template, closing the handle.

    A bare `open(...).read()` leaks the descriptor until the garbage
    collector runs, and the suite was emitting eleven ResourceWarnings for
    this one file. Noise in a test run is where a real warning goes to hide.
    """
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets", "report-template.html")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


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
        self.assertNotIn("setReportView", rendered)
        self.assertIn("revealHashTarget", rendered)
        self.assertIn("target.scrollIntoView", rendered)
        self.assertIn('document.documentElement.classList.add("report--ready")', rendered)
        self.assertIn("navigator.clipboard.writeText", rendered)
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

        summary = render_discovery.run_summary(discovery, tokens, report)
        runhead = render_discovery.render_runhead(
            discovery, tokens, report, "local-test"
        )

        self.assertEqual(summary["token_sources"], 2)
        self.assertEqual(summary["unresolved_actionable"], 2)
        self.assertEqual(summary["unresolved_total"], 3)
        self.assertEqual(summary["held_out_sources"], 2)
        self.assertIn("&quot;token_sources&quot;:2", runhead)

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
            "semantic_equivalence": "not-visible",
            "near_miss": "not-visible",
        })
        self.assertEqual(report["run"]["files_scanned"], 42)
        self.assertEqual(report["executive_summary"]["affected"]["owned_files"], 42)
        note = report["vitals"]["leakage"]["note"]
        self.assertIn("One hardcoded color has the same value as a token", note)
        self.assertIn("2 match no token", note)
        # The count of files scanned is a fact about the run. It is said in
        # About this run, and a note that repeated it drifted from it.
        self.assertNotIn("42", note)

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
        self.assertEqual(report["vitals"]["leakage"]["grade"], "not-visible")
        self.assertTrue(
            all(value is None for value in tiers.values()),
            "a run that scanned nothing reported a tier count: %r" % tiers)
        self.assertIn("couldn't look for hardcoded colors",
                      report["vitals"]["leakage"]["note"])

    def test_an_empty_trend_block_is_emptied_like_a_missing_one(self):
        """No baseline means no comparison, however the block is spelled.

        The section itself stays, so `#trend` still resolves: a section may
        move or empty, and never disappears.

        The stripper tested `if not report.get("trend")`, so a schema-shaped
        block of nulls survived and shipped the template's own sample
        comparison — which the validation gate then caught as leftover
        sample content, once, on every fresh report.
        """
        document = (
            '<body>'
            '\n  <section id="trend">'
            '\n    <b>Compared against <code>a91f4c07</code>.</b>'
            '\n  </section>\n'
            '</body>'
        )
        report = {"trend": {"baseline_ref": None, "compatible": None,
                            "new": [], "resolved": [], "grew": [],
                            "shrank": [], "regressions": []}}
        stripped = render_discovery.strip_trend_without_a_baseline(document, report)
        self.assertNotIn("a91f4c07", stripped)
        self.assertIn('<section id="trend">', stripped)
        self.assertIn("nothing to compare it to yet", stripped)

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
        self.assertIn("Show 2 more files", rendered)

    def test_leakage_block_keeps_every_location_visible(self):
        locations = ["styles/a.scss:1", "styles/b.scss:2", "styles/c.scss:3"]
        rendered = render_discovery.chapters.render_leakage({}, {
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
        self.assertIn("Show 2 more places", rendered)
        self.assertIn("matches a token", rendered)
        self.assertNotIn("exact-value candidate<", rendered)

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
        self.assertNotIn("view", report["rendering"])
        self.assertNotIn("available_views", report["rendering"])
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


class TestLeakageSyncRespectsTheMeasurement(unittest.TestCase):
    """The renderer was overwriting the one grade the audit had earned.

    `audit_literal_colors.py` learned to report "measured, none found" when
    a repository has no literal left to compare — the whole point being that
    leakage becomes gradeable. `sync_leakage` then hardcoded
    `redundant: None` and a note saying semantic equivalence was unmeasured,
    which forced the vital back to `not-visible`. The fix was verified at the
    audit tool and never through the renderer, so nothing caught it until a
    full pipeline ran.
    """

    CLEAN = {
        "consumer_files_scanned": 13,
        "exact_value_candidates": [],
        "uncovered_candidates": [],
        "semantic_equivalence": {"state": "counted", "findings": 0, "note": "x"},
        "near_miss": {"state": "counted", "findings": 0, "note": "y"},
    }

    def sync(self, leakage, grade="healthy"):
        report = {"vitals": {"leakage": {"grade": grade, "evidence": ["a.css:1"]}}}
        render_discovery.sync_leakage(report, leakage)
        return report["vitals"]["leakage"]

    def test_a_measured_none_found_run_keeps_its_grade(self):
        vital = self.sync(self.CLEAN)
        self.assertEqual(vital["grade"], "healthy")
        self.assertEqual(vital["tiers"]["redundant"], 0)

    def test_an_unmeasured_semantic_equivalence_still_blocks(self):
        leakage = dict(self.CLEAN, semantic_equivalence={
            "state": "not-visible", "findings": None, "note": "z"})
        vital = self.sync(leakage)
        self.assertEqual(vital["grade"], "not-visible")
        self.assertIsNone(vital["tiers"]["redundant"])

    def test_an_exact_value_candidate_blocks_until_its_role_is_proven(self):
        leakage = dict(self.CLEAN,
                       exact_value_candidates=[{"id": "a1b2c3d4e5f6"}],
                       semantic_equivalence={"state": "not-visible",
                                             "findings": None, "note": "z"})
        vital = self.sync(leakage)
        self.assertEqual(vital["grade"], "not-visible")

    def test_no_consumer_style_scanned_is_still_unmeasured(self):
        leakage = dict(self.CLEAN, consumer_files_scanned=0)
        vital = self.sync(leakage)
        self.assertEqual(vital["grade"], "not-visible")
        self.assertIsNone(vital["tiers"]["redundant"])
