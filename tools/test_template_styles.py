"""No layout decision lives inline in the template.

Wave 1 moved sixty of them into a spacing scale. This keeps the count at
zero, so the next region added does not quietly bring them back. Inline
styles that carry data — a swatch's color, a bar's width, a specimen's
size — are the content and stay.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "report-template.html")

STYLE = re.compile(r'style="([^"]*)"')
DATA_PROPS = re.compile(r"^(background|width|font-size|color)\s*:")
DATA_VALUE = re.compile(r"#[0-9a-fA-F]{3,6}|\d+(?:\.\d+)?%|^width\s*:\s*\d+px")


def is_data(style):
    decls = [d.strip() for d in style.strip().rstrip(";").split(";") if d.strip()]
    if not all(DATA_PROPS.match(d) for d in decls):
        return False
    if any(DATA_VALUE.search(d) for d in decls):
        return True
    return len(decls) <= 2 and any(d.startswith("font-size") for d in decls)


class TestNoLayoutInline(unittest.TestCase):
    def test_every_inline_style_carries_data(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            styles = STYLE.findall(fh.read())
        layout = [s for s in styles if not is_data(s)]
        self.assertEqual(layout, [], "layout decisions inline; give them a class")

    def test_the_classifier_knows_data_from_layout(self):
        self.assertTrue(is_data("background:#0B7285"))
        self.assertTrue(is_data("width:37.5%"))
        self.assertTrue(is_data("font-size:26px;color:var(--warn)"))
        self.assertFalse(is_data("margin-top:16px"))
        self.assertFalse(is_data("padding:2px 8px"))


class TestPrintLocationEvidence(unittest.TestCase):
    def test_print_uses_the_full_structured_location(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()

        self.assertIn("content: attr(data-token-location)", template)


class TestComponentRoadmapTable(unittest.TestCase):
    def setUp(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            self.template = fh.read()

    def test_roadmap_headers_have_protected_readable_widths(self):
        self.assertIn(
            ".component-roadmap-band table { min-width: 600px; table-layout: fixed;",
            self.template,
        )
        self.assertIn(
            ".component-roadmap-band th { padding-top: 10px; font-size: 10.5px; white-space: nowrap; }",
            self.template,
        )
        widths = {1: 34, 2: 250, 3: 84, 4: 62, 5: 58, 6: 64}
        for column, width in widths.items():
            selector = (
                ".component-roadmap-band th:nth-child(%d), "
                ".component-roadmap-band td:nth-child(%d) { width: %dpx; }"
                % (column, column, width)
            )
            self.assertIn(selector, self.template)

    def test_roadmap_scroll_is_contained_and_print_can_reflow(self):
        self.assertIn("overscroll-behavior-inline: contain; scrollbar-gutter: stable", self.template)
        self.assertIn(
            ".component-roadmap-band .tbl-scroll[tabindex]:focus-visible { outline-offset: -2px; }",
            self.template,
        )
        # WAS a max-width:1120px override that stacked the grid and turned its
        # scroller off. The grid now stacks at EVERY width — the bands are a
        # sequence, and a band's table is the evidence, so it should never need
        # dragging to read — which made that override dead code restating the
        # base rule. The contract this guarded is unchanged and strictly
        # stronger, so it is asserted as a PROPERTY rather than as the old
        # spelling: one column, and no horizontal scroller on the grid itself.
        # Containment is unaffected: .tbl-scroll inside each band keeps its own
        # overflow-x for a table too wide even at full measure.
        grid_rule = re.search(r"\.component-roadmap-grid \{[^}]*\}", self.template)
        self.assertIsNotNone(grid_rule, "the roadmap grid rule has been renamed or removed")
        self.assertIn("grid-template-columns: 1fr", grid_rule.group(0))
        self.assertNotIn("overflow", grid_rule.group(0))
        # Deliberately NOT a document-wide assertNotIn on "repeat(3," — other
        # grids in this template use three columns legitimately, and a guard
        # that fires on correct code elsewhere is as broken as one that never
        # fires. Scoped to this rule's own body, above.
        self.assertIn(
            ".component-roadmap-band table { min-width: 0; table-layout: auto; }",
            self.template,
        )

    def test_roadmap_scrollers_have_keyboard_labels(self):
        heading_ids = re.findall(
            r'<h3 id="(component-roadmap-band-[^"]+-title)">',
            self.template,
        )
        scroller_ids = re.findall(
            r'<div class="tbl-scroll" role="region" tabindex="0" '
            r'aria-labelledby="(component-roadmap-band-[^"]+-title)">',
            self.template,
        )
        table_ids = re.findall(
            r'<table aria-labelledby="(component-roadmap-band-[^"]+-title)">',
            self.template,
        )
        self.assertEqual(len(heading_ids), 3)
        self.assertEqual(len(set(heading_ids)), 3)
        self.assertCountEqual(scroller_ids, heading_ids)
        self.assertCountEqual(table_ids, heading_ids)
        self.assertIn('<div class="component-roadmap-grid">', self.template)
        self.assertNotIn('<div class="component-roadmap-grid" role=', self.template)


if __name__ == "__main__":
    unittest.main()
