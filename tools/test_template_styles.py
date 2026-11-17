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
# `left` is where a marker sits on a track: a reading, placed. It is data in
# the same way a bar's width is.
DATA_PROPS = re.compile(r"^(background|width|font-size|color|left)\s*:")
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
        self.assertTrue(is_data("left:47.000%"))
        self.assertFalse(is_data("left:12px"))
        self.assertTrue(is_data("font-size:26px;color:var(--warn)"))
        self.assertFalse(is_data("margin-top:16px"))
        self.assertFalse(is_data("padding:2px 8px"))


class TestPrintLocationEvidence(unittest.TestCase):
    def test_print_uses_the_full_structured_location(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()

        self.assertIn("content: attr(data-token-location)", template)


class TestComponentTable(unittest.TestCase):
    """The components are one table, and its share bars share one scale."""

    def setUp(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            self.template = fh.read()

    def test_the_share_bar_is_one_width_in_every_row(self):
        """Bars that are a share of the same whole have to be the same length
        at 100%, or two rows cannot be compared by eye."""
        self.assertIn(".component-table .mk-share { width: 180px; }", self.template)

    def test_the_table_scrolls_inside_itself_and_can_be_reached_by_keyboard(self):
        self.assertIn(".tbl-scroll { overflow-x: auto; }", self.template)
        self.assertIn(".tbl-scroll[tabindex]:focus-visible", self.template)


if __name__ == "__main__":
    unittest.main()
