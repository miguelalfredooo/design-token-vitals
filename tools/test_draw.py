"""A number the page could draw is drawn, and nothing is readable only by eye."""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draw  # noqa: E402


def widths(markup):
    return [float(value) for value in re.findall(r"width:([0-9.]+)%", markup)]


class TestEveryMarkHasWords(unittest.TestCase):
    def test_each_mark_carries_its_figure_for_a_screen_reader(self):
        marks = {
            "bar": draw.bar(1088, 1216, "tokens"),
            "dots": draw.dots(74, 729, "custom properties"),
            "cells": draw.cells(11, 11, "categories"),
            "stack": draw.stack([("match a token", 3, "warn"), ("match nothing", 31, "mute")]),
            "threshold": draw.threshold(4.7, 10, [{"at": 5, "label": "Fix above"}], "%"),
            "hatch": draw.hatch(),
            "dot": draw.grade_dot("watch"),
        }
        for name, markup in marks.items():
            with self.subTest(mark=name):
                self.assertRegex(markup, r'role="img" aria-label="[^"]+"')

    def test_the_figure_beside_a_mark_is_text(self):
        figure = draw.figure(draw.bar(1088, 1216), "1,088 of 1,216 (89%)",
                             "Most tokens trace back.")
        self.assertIn('<span class="mk-num">1,088 of 1,216 (89%)</span>', figure)
        self.assertIn('<figcaption class="mk-means">Most tokens trace back.</figcaption>', figure)


class TestSharesAreDrawnToScale(unittest.TestCase):
    def test_a_bar_is_as_wide_as_its_share(self):
        self.assertAlmostEqual(widths(draw.bar(1088, 1216))[0], 89.474, places=3)

    def test_a_bar_never_overflows_or_divides_by_nothing(self):
        self.assertEqual(widths(draw.bar(5, 0)), [0.0])
        self.assertEqual(widths(draw.bar(9, 3)), [100.0])

    def test_a_stack_adds_up_to_the_whole(self):
        markup = draw.stack([("a", 3, "warn"), ("b", 31, "mute")])
        self.assertAlmostEqual(sum(widths(markup)), 100.0, places=2)

    def test_a_stack_short_of_its_whole_draws_the_rest(self):
        """Parts that stop at 25% must not be stretched to look like all of it."""
        markup = draw.stack([("top 5", 322, "ink")], 1288)
        self.assertAlmostEqual(widths(markup)[0], 25.0, places=2)
        self.assertIn('data-tone="rest"', markup)
        self.assertAlmostEqual(sum(widths(markup)), 100.0, places=2)

    def test_table_shares_use_one_scale(self):
        first, second = draw.share(92, 1288), draw.share(46, 1288)
        self.assertAlmostEqual(widths(first)[0], 2 * widths(second)[0], places=2)


class TestCountsOutOfAWhole(unittest.TestCase):
    def test_there_is_one_dot_for_each_thing(self):
        markup = draw.dots(74, 729)
        self.assertEqual(markup.count("<circle"), 729)
        self.assertEqual(markup.count('class="mk-dot-mark"'), 74)

    def test_a_whole_too_large_to_draw_as_dots_becomes_a_bar(self):
        markup = draw.dots(10, draw.MAX_DOTS + 1)
        self.assertIn('class="mk-bar"', markup)
        self.assertNotIn("<circle", markup)

    def test_cells_show_what_is_missing_as_well_as_what_is_there(self):
        markup = draw.cells(10, 11)
        self.assertEqual(markup.count('class="on"'), 10)
        self.assertEqual(markup.count('class="off"'), 1)


class TestThresholds(unittest.TestCase):
    def test_the_marker_and_the_line_are_placed_and_not_described(self):
        markup = draw.threshold(4.7, 10, [{"at": 5, "label": "Fix above"}], "%")
        self.assertIn('class="mk-marker" style="left:47.000%"', markup)
        self.assertIn('class="mk-tick" style="left:50.000%"', markup)
        self.assertIn("<b>Fix above 5%</b>", markup)

    def test_a_reading_is_never_rounded_onto_its_line(self):
        """4.7 against a line at 5 is under it. `5%` would say it is on it."""
        markup = draw.threshold(4.7, 10, [{"at": 5, "label": "Fix above"}], "%")
        self.assertIn("4.7%", markup)
        self.assertNotIn('aria-label="5%', markup)


class TestUnseenIsHatchedAndNeverZero(unittest.TestCase):
    def test_a_blocked_dot_is_not_an_empty_one(self):
        self.assertIn('data-g="not-visible"', draw.grade_dot("not-visible"))
        self.assertIn('data-g="none"', draw.grade_dot(None))
        self.assertNotEqual(draw.grade_dot("not-visible"), draw.grade_dot(None))

    def test_the_hatch_says_we_could_not_see_it(self):
        self.assertIn("We couldn't see it", draw.hatch().replace("&#x27;", "'"))


class TestTheStrip(unittest.TestCase):
    STATES = [("leakage", "Leakage", "not-visible"), ("coverage", "Coverage", "healthy")]

    def test_a_cell_states_the_grade_in_the_readers_word(self):
        markup = draw.strip(self.STATES)
        self.assertIn('<span class="mk-strip-state">Blocked</span>', markup)
        self.assertIn('<span class="mk-strip-state">Healthy</span>', markup)
        self.assertNotIn(">not-visible<", markup)

    def test_a_cell_links_to_the_evidence_for_its_check(self):
        self.assertIn('href="#vital-leakage"', draw.strip(self.STATES))


class TestPairs(unittest.TestCase):
    def test_the_declaration_that_loses_is_struck_through(self):
        markup = draw.declarations([
            {"location": "a.css:4", "code": "--x: 4%;", "wins": False},
            {"location": "a.css:90", "code": "--x: 8%;", "wins": True}])
        self.assertIn("<s><code>--x: 4%;</code></s>", markup)
        self.assertIn("<code>--x: 8%;</code>", markup)
        self.assertNotIn("<s><code>--x: 8%;</code></s>", markup)

    def test_repository_content_is_escaped(self):
        markup = draw.declarations([{"location": "a.css:1", "code": "<script>", "wins": True}])
        self.assertNotIn("<script>", markup)
        self.assertNotIn("<img", draw.swatch('"><img src=x>'))


if __name__ == "__main__":
    unittest.main()
