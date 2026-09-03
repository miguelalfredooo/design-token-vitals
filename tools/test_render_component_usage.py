"""Tests for component-usage report rendering."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_component_usage  # noqa: E402
import analyze_component_usage  # noqa: E402


def usage():
    component = {
        "id": "a" * 12, "rank": 1, "name": "app / button", "kind": "component",
        "key": "app::button", "confidence": "path-inferred",
        "paths": ["app/button.scss"], "references": 2,
        "distinct_tokens": 1, "families": {"color": 2},
        "tokens": [{"id": "brand", "family": "color", "references": 2,
                    "syntaxes": ["css-custom-property"],
                    "locations": ["app/button.scss:4"]}],
    }
    roadmap_row = {"id": component["id"], "rank": 1, "references": 2}
    roadmap = analyze_component_usage.build_roadmap([roadmap_row])
    for field in (
            "roadmap_band", "share_of_ranked_references",
            "cumulative_share_of_ranked_references"):
        component[field] = roadmap_row[field]
    return {
        "state": "measured",
        "files_scanned": 3,
        "total_components_with_token_usage": 1,
        "additional_style_surfaces": 0,
        "shown": 1,
        "shown_components": 1,
        "fallback_surfaces": 0,
        "not_shown": 0,
        "measurement": [
            {"syntax": "css-custom-property", "state": "measured", "evidence": "var(--token)"},
        ],
        "roadmap": roadmap,
        "top_20": [component],
    }


class TestComponentUsageRendering(unittest.TestCase):
    def test_section_contains_component_token_and_evidence(self):
        section = render_component_usage.render_section(usage())
        self.assertIn(
            '<section id="component-usage" data-report-views="action evidence">',
            section,
        )
        self.assertIn("a" * 12, section)
        self.assertIn("--brand", section)
        self.assertIn("app/button.scss:4", section)
        self.assertIn('<table class="component-token-table">', section)
        self.assertIn('data-component-roadmap-json=', section)
        self.assertIn('data-roadmap-band="assess-first"', section)
        self.assertIn("Plan by token footprint", section)
        self.assertIn("100.0% of the ranked view", section)
        self.assertIn('data-component-path="app/button.scss"', section)
        self.assertIn('role="region" tabindex="0"', section)
        self.assertEqual(section.count('role="region" tabindex="0"'), 1)
        self.assertIn('<div class="component-roadmap-grid">', section)
        self.assertNotIn('<div class="component-roadmap-grid" role=', section)
        self.assertIn(
            'aria-labelledby="component-roadmap-band-assess-first-title"',
            section,
        )
        self.assertIn(
            'href="#component-detail-%s"' % ("a" * 12), section
        )

    def test_repository_content_is_escaped(self):
        data = usage()
        data["top_20"][0]["name"] = '<img src=x onerror="bad">'
        section = render_component_usage.render_section(data)
        self.assertNotIn("<img", section)
        self.assertIn("&lt;img", section)

    def test_repeated_locations_collapse_by_file_without_dropping_evidence(self):
        data = usage()
        locations = [
            "app/button.scss:4",
            "app/button.scss:8",
            "app/button.scss:12",
            "app/button.scss:20",
        ]
        data["top_20"][0]["tokens"][0]["locations"] = locations

        section = render_component_usage.render_section(data)

        self.assertIn('data-location-file="app/button.scss"', section)
        self.assertIn('data-location-count="4"', section)
        self.assertIn('data-location-preview="2"', section)
        self.assertIn('data-location-hidden="2"', section)
        self.assertIn("See 2 more locations in button.scss", section)
        self.assertEqual(
            section.count(
                '<span class="path location-file">app/button.scss</span>'
            ),
            1,
        )
        self.assertIn(">line 4</span>", section)
        self.assertIn(">line 20</span>", section)
        for location in locations:
            self.assertEqual(
                section.count('data-token-location="%s"' % location), 1
            )
            self.assertIn('aria-label="%s"' % location, section)

    def test_location_disclosure_uses_singular_grammar(self):
        data = usage()
        data["top_20"][0]["tokens"][0]["locations"] = [
            "app/button.scss:4",
            "app/button.scss:8",
            "app/button.scss:12",
        ]

        section = render_component_usage.render_section(data)

        self.assertIn("See 1 more location in button.scss", section)
        self.assertNotIn("See 1 more locations", section)

    def test_short_location_groups_remain_fully_visible(self):
        section = render_component_usage.render_section(usage())

        self.assertNotIn("location-disclosure", section)

    def test_augment_merges_json_and_inserts_before_leakage(self):
        root = tempfile.mkdtemp()
        components = os.path.join(root, "components.json")
        report = os.path.join(root, "report.json")
        page = os.path.join(root, "report.html")
        with open(components, "w", encoding="utf-8") as handle:
            json.dump(usage(), handle)
        with open(report, "w", encoding="utf-8") as handle:
            json.dump({"schema_version": 2, "run": {"generated_at": "old-time"},
                       "provenance": {"generated_at": "old-time", "skill_version": "old-version"}}, handle)
        with open(page, "w", encoding="utf-8") as handle:
            handle.write(
                '<html><!-- SLOT:at-a-glance --><!-- /SLOT:at-a-glance -->'
                '<section><div class="eyebrow">Leakage</div></section>'
                '<section id="strategy"><!-- SLOT:adoption-strategy -->'
                '<!-- /SLOT:adoption-strategy --></section></html>'
            )
        render_component_usage.augment(components, report, page)
        with open(report, encoding="utf-8") as handle:
            rendered = json.load(handle)
        self.assertEqual(rendered["component_usage"]["shown"], 1)
        self.assertNotEqual(rendered["provenance"]["skill_version"], "old-version")
        self.assertNotEqual(rendered["run"]["generated_at"], "old-time")
        self.assertEqual(
            rendered["adoption_strategy"]["evidence"]["components_with_token_usage"],
            1,
        )
        with open(page, encoding="utf-8") as handle:
            html = handle.read()
        self.assertLess(
            html.index('id="component-usage"'),
            html.index('<div class="eyebrow">Leakage</div>'),
        )
        self.assertIn('data-report-region="adoption-strategy"', html)
        self.assertIn('data-dashboard-component-roadmap-json=', html)

    def test_invalid_html_does_not_partially_update_report_json(self):
        root = tempfile.mkdtemp()
        components = os.path.join(root, "components.json")
        report = os.path.join(root, "report.json")
        page = os.path.join(root, "report.html")
        original = {"schema_version": 2, "run": {}, "provenance": {}}
        with open(components, "w", encoding="utf-8") as handle:
            json.dump(usage(), handle)
        with open(report, "w", encoding="utf-8") as handle:
            json.dump(original, handle)
        with open(page, "w", encoding="utf-8") as handle:
            handle.write("<html><body>No insertion point</body></html>")

        with self.assertRaisesRegex(ValueError, "no component-usage"):
            render_component_usage.augment(components, report, page)

        with open(report, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), original)


if __name__ == "__main__":
    unittest.main()
