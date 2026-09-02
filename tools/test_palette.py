"""Tests for palette.

The check itself is arithmetic; what needs guarding is that the template
keeps passing and that the check cannot be satisfied vacuously.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import palette  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "report-template.html")


class TestArithmetic(unittest.TestCase):
    def test_black_on_white_is_twenty_one(self):
        self.assertAlmostEqual(palette.contrast("#000000", "#FFFFFF"), 21.0, places=1)

    def test_contrast_is_symmetric(self):
        self.assertEqual(palette.contrast("#123456", "#ABCDEF"), palette.contrast("#ABCDEF", "#123456"))


class TestTemplate(unittest.TestCase):
    def setUp(self):
        with open(TEMPLATE, encoding="utf-8") as fh:
            self.html = fh.read()

    def test_all_three_theme_blocks_are_found(self):
        """Bare :root, the media-query override, and the data-theme override."""
        self.assertEqual(len(palette.theme_blocks(self.html)), 3)

    def test_every_status_pair_clears_aa_in_every_theme(self):
        table, failures = palette.check(self.html)
        self.assertGreaterEqual(len(table), 20, "too few pairs checked — did the token names change?")
        self.assertEqual(failures, [], "\n".join(
            "%s: %s on %s = %.2f" % (l, fg, bg, r) for l, fg, _, bg, _, r in failures))

    def test_blocked_hatch_is_light_pink_and_clears_graphic_contrast(self):
        table, _ = palette.check(self.html)
        rows = [row for row in table if row[1] == "--block-line"]
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(color == "#C86D84" for _, _, color, _, _, _ in rows))
        self.assertTrue(all(
            ratio >= palette.GRAPHIC_AA
            for _, _, _, _, _, ratio in rows
        ))
        self.assertNotRegex(
            self.html,
            r'blocked[^\{]*\{[^\}]*repeating-linear-gradient\([^\)]*var\(--block\)',
        )

    def test_blocked_text_is_checked_against_its_actual_tint(self):
        broken = self.html.replace("--block: #5B5B7A", "--block: #6D6D6D", 1)
        _, failures = palette.check(broken)
        self.assertTrue(any(
            foreground == "--block" and background == "--block-bg"
            for _, foreground, _, background, _, _ in failures
        ))

    def test_the_check_is_not_vacuous(self):
        """A template with a failing pair must be reported, or the test above means nothing."""
        broken = self.html.replace("--pass: #397248", "--pass: #A0D0A8", 1)
        _, failures = palette.check(broken)
        self.assertTrue(any(fg == "--pass" for _, fg, _, _, _, _ in failures))


if __name__ == "__main__":
    unittest.main()
