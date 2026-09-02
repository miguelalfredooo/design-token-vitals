"""Tests for component-usage report rendering."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render_component_usage  # noqa: E402


def usage():
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
        "top_20": [{
            "id": "a" * 12, "rank": 1, "name": "app / button", "kind": "component",
            "confidence": "path-inferred", "paths": ["app/button.scss"],
            "references": 2, "distinct_tokens": 1, "families": {"color": 2},
            "tokens": [{"id": "brand", "family": "color", "references": 2,
                        "syntaxes": ["css-custom-property"],
                        "locations": ["app/button.scss:4"]}],
        }],
    }


class TestComponentUsageRendering(unittest.TestCase):
    def test_section_contains_component_token_and_evidence(self):
        section = render_component_usage.render_section(usage())
        self.assertIn("a" * 12, section)
        self.assertIn("--brand", section)
        self.assertIn("app/button.scss:4", section)

    def test_repository_content_is_escaped(self):
        data = usage()
        data["top_20"][0]["name"] = '<img src=x onerror="bad">'
        section = render_component_usage.render_section(data)
        self.assertNotIn("<img", section)
        self.assertIn("&lt;img", section)

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
            handle.write('<html><section><div class="eyebrow">Leakage</div></section></html>')
        render_component_usage.augment(components, report, page)
        with open(report, encoding="utf-8") as handle:
            rendered = json.load(handle)
        self.assertEqual(rendered["component_usage"]["shown"], 1)
        self.assertNotEqual(rendered["provenance"]["skill_version"], "old-version")
        self.assertNotEqual(rendered["run"]["generated_at"], "old-time")
        with open(page, encoding="utf-8") as handle:
            html = handle.read()
        self.assertLess(html.index('id="component-usage"'), html.index("Leakage"))

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
