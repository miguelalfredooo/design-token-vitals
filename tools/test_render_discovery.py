"""Tests for universal discovery report rendering."""
import json
import hashlib
from html.parser import HTMLParser
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover_environment  # noqa: E402
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

    def test_at_a_glance_keeps_visual_marks_with_an_empty_fix_queue(self):
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
            "inventory": {"families": {}},
        })
        self.assertIn('class="ladder" data-glance-mark="stage"', rendered)
        self.assertEqual(rendered.count('class="seg" data-glance-mark='), 3)
        self.assertIn('class="ring" data-glance-mark="fix-queue"', rendered)
        self.assertEqual(rendered.count("data-glance-mark="), 6)
        self.assertIn('data-fix-total="0" data-fix-verified="0"', rendered)
        self.assertIn('stroke-dasharray="0.0 125.7"', rendered)

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
