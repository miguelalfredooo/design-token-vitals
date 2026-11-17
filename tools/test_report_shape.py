"""A whole rendered report, held to the rules a reader would notice it breaking.

These are the page's promises: it opens on one sentence, a grade is stated
once, every breakdown of the eight checks sums to eight, the first move is
the same wherever it is shown, a fact about the whole run is said in one
place, and no old word or machine path reaches the reader. Each test names
the promise; each was a real defect in the report this shape replaced.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moves  # noqa: E402
import render_component_usage  # noqa: E402
import render_discovery  # noqa: E402
import sample_report  # noqa: E402
import validate_run  # noqa: E402
import vocab  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "assets", "report-template.html")


def render(report=None):
    report = report or sample_report.build()
    with open(TEMPLATE, encoding="utf-8") as handle:
        document = render_discovery.TEMPLATE_INSTRUCTIONS.sub(
            r"\1", handle.read(), count=1)
    document = render_discovery.fill_document(
        document, report, report["discovery"], None,
        report.get("leakage_analysis"), "0.0.0-test")
    return report, render_discovery.prepare_progressive_disclosures(document)


def text_of(fragment):
    return re.sub(r"\s+", " ", validate_run.visible_text(fragment)).strip()


def region(html, name):
    return re.search(r"<!-- SLOT:%s -->(.*?)<!-- /SLOT:%s -->" % (name, name),
                     html, re.S).group(1)


def chapter(html, chapter_id):
    return re.search(
        r'<div class="chapter[^"]*" id="%s".*?(?=\n  <div class="chapter|\n  <footer>)'
        % chapter_id, html, re.S).group(0)


class TestTheVerdict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.html = render()
        cls.verdict = chapter(cls.html, "verdict")

    def test_it_opens_on_one_sentence_that_states_the_finding(self):
        line = text_of(region(self.html, "headline"))
        self.assertEqual(
            line, "One confirmed defect: the button's hover color is set "
                  "twice, so the first value never ships.")

    def test_it_holds_the_strip_the_counters_and_the_first_move_and_no_more(self):
        self.assertEqual(len(re.findall(r'class="mk-strip-cell"', self.verdict)), 8)
        self.assertEqual(len(re.findall(r'class="counter"', self.verdict)), 3)
        self.assertEqual(len(re.findall(r'class="move"', self.verdict)), 1)
        self.assertNotIn("<table", self.verdict)

    def test_the_counters_agree_with_the_strip(self):
        counts = vocab.grade_counts(self.report)
        shown = dict(re.findall(r'class="counter" data-kind="(\w+)" data-count="(\d+)"',
                                self.verdict))
        self.assertEqual(int(shown["fix"]), counts["needs-work"])
        self.assertEqual(int(shown["unlock"]), counts["not-visible"])

    def test_a_command_is_inline_only_when_the_first_move_is_an_unlock(self):
        self.assertEqual(moves.first(self.report)["kind"], "fix")
        self.assertNotIn("data-copy-source", self.verdict)

        unlock_only = sample_report.build()
        unlock_only["vitals"]["single-source"] = {"grade": "healthy"}
        unlock_only["leakage_analysis"]["exact_value_candidates"] = []
        _report, html = render(unlock_only)
        self.assertEqual(moves.first(unlock_only)["kind"], "unlock")
        self.assertIn("data-copy-source", chapter(html, "verdict"))


class TestAGradeIsStatedOnce(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.html = render()

    def test_the_five_state_words_label_the_strip_and_nothing_else(self):
        page = self.html[self.html.index("<body"):]
        self.assertNotIn("mk-strip-state", page.replace(chapter(page, "verdict"), ""))
        cards = region(self.html, "vitals-grid")
        for word in ("Healthy", "Watch", "Blocked", "Not needed"):
            self.assertNotIn(">%s<" % word, cards)

    def test_a_check_card_draws_its_grade_and_links_back_for_the_word(self):
        cards = region(self.html, "vitals-grid")
        self.assertEqual(len(re.findall(r'<article class="vital" id="vital-', cards)), 8)
        self.assertEqual(cards.count('href="#confidence"'), 8)
        self.assertNotIn('class="grade"', cards)

    def test_the_retired_label_sets_are_gone(self):
        text = text_of(self.html)
        for retired in ("Worth a look", "Needs evidence", "Well supported",
                        "Needs action", "Needs focus", "Attention —", "Pass —",
                        "To fix in your code", "The audit cannot see"):
            self.assertNotIn(retired, text)


class TestEveryBreakdownSumsToEight(unittest.TestCase):
    def test_across_a_spread_of_reports(self):
        clean = sample_report.build()
        clean["vitals"] = {name: {"grade": "healthy"} for name in vocab.CHECK_ORDER}
        blocked = sample_report.build()
        blocked["vitals"] = {name: {"grade": "not-visible"} for name in vocab.CHECK_ORDER}
        for report in (sample_report.build(), clean, blocked):
            report["confidence"]["split"] = vocab.grade_counts(report)
            _report, html = render(report)
            strip = re.search(r'<div class="verdict-strip"[^>]*>', html).group(0)
            counts = [int(n) for n in re.findall(r'data-count-[a-z-]+="(\d+)"', strip)]
            self.assertEqual(sum(counts), 8)
            self.assertEqual(len(re.findall(r'class="mk-strip-cell"', html)), 8)
            measured = re.search(r"(\d+) of 8 checks measured", text_of(html))
            self.assertEqual(int(measured.group(1)),
                             vocab.measured(vocab.grade_counts(report)))


class TestTheFirstMoveIsTheSameEverywhere(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.html = render()
        cls.first = moves.first(cls.report)

    def blocks(self, fragment, move_id):
        return re.findall(
            r'<div class="move" data-move="%s".*?</div></div>' % re.escape(move_id),
            fragment, re.S)

    def test_the_verdict_the_chapter_and_the_closing_list_render_one_move(self):
        places = [chapter(self.html, "verdict"), chapter(self.html, "fix-now"),
                  region(self.html, "next-steps")]
        seen = []
        for place in places:
            found = self.blocks(place, self.first["id"])
            self.assertEqual(len(found), 1)
            seen.append(re.sub(r'<span class="move-n">\d+</span>', "", found[0]))
        self.assertEqual(len(set(seen)), 1, "the first move is worded two ways")

    def test_the_closing_list_is_the_ranked_list_in_order(self):
        listed = re.findall(r'data-move="([^"]+)"', region(self.html, "next-steps"))
        self.assertEqual(listed, [move["id"] for move in moves.rank(self.report)])

    def test_nothing_else_offers_a_competing_first_step(self):
        text = text_of(self.html)
        for retired in ("Next best 15 minutes", "Start here", "Fix first",
                        "Start with the one"):
            self.assertNotIn(retired, text)


class TestBlockedChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.html = render()
        cls.unlock = chapter(cls.html, "unlock-chapter")

    def test_each_blocked_check_appears_once_in_unlock(self):
        self.assertEqual(re.findall(r'data-blocked-check="([^"]+)"', self.html),
                         moves.blocked_checks(self.report))

    def test_each_is_one_plain_sentence(self):
        sentence = text_of(re.search(
            r'<li data-blocked-check="mode-completeness".*?<div class="unlock-body"><p>(.*?)</p>',
            self.unlock, re.S).group(1))
        self.assertEqual(sentence, "Themes is blocked until themes resolve.")

    def test_its_command_waits_behind_show_command_with_a_copy_button(self):
        disclosure = re.search(
            r'<details open data-report-default-open="false" class="cmd">.*?</details>',
            self.unlock, re.S)
        self.assertIsNotNone(disclosure, "the command is not in a closed disclosure")
        self.assertIn("<summary>Show command</summary>", disclosure.group(0))
        self.assertIn("data-copy-source", disclosure.group(0))
        self.assertIn('class="copy" data-copy', disclosure.group(0))

    def test_a_command_is_relative_to_the_repository(self):
        commands = re.findall(r"<code data-copy-source>(.*?)</code>", self.html)
        self.assertTrue(commands)
        for command in commands:
            self.assertNotIn(self.report["discovery"]["repository"]["root"], command)
            self.assertNotIn("&lt;root&gt;", command)

    def test_the_unlocks_line_is_not_repeated_under_the_sentence(self):
        self.assertNotRegex(text_of(self.unlock), r"Unlocks \d")


class TestRunWideFactsLiveInOnePlace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.html = render()
        cls.about = region(cls.html, "about-run")
        header = cls.html[cls.html.index('<header class="runhead">'):
                          cls.html.index("</header>")]
        cls.rest = text_of(cls.html[cls.html.index("<body"):].replace(header, ""))

    def test_about_this_run_is_collapsed_and_names_each_count_of_files(self):
        self.assertIn('<details open data-report-default-open="false" class="about"',
                      self.about)
        named = re.findall(r'data-run-fact="([^"]+)"', self.about)
        self.assertEqual(named, ["source-files-in-scope", "CSS-files-scanned",
                                 "files-that-use-a-token",
                                 "files-read-for-component-use"])

    def test_the_commit_the_versions_and_the_date_appear_nowhere_else(self):
        for fact in ("7f0c22ab", "0.0.0-test", "Jan 1, 2026", "tailwindcss 4.3.0"):
            with self.subTest(fact=fact):
                self.assertIn(fact, text_of(self.html))
                self.assertNotIn(fact, self.rest)

    def test_a_count_of_files_elsewhere_is_a_link_back(self):
        """`1,645 files in scope` is said once. A chapter that needs a
        denominator points at it."""
        self.assertNotIn("1,645", self.rest)
        for match in re.finditer(r"96 CSS files?", self.html):
            before = self.html[max(0, match.start() - 60):match.start()]
            self.assertTrue('href="#about-run"' in before or
                            'data-run-fact' in self.html[max(0, match.start() - 400):match.start()],
                            "a run-wide count outside About this run is not a link to it")

    def test_the_footer_says_one_thing(self):
        footer = text_of(self.html[self.html.index("<footer>"):])
        self.assertTrue(footer.startswith(
            "Every number here was read from your repository. Nothing left your machine."))
        self.assertNotRegex(footer, r"\d")


class TestNoOldWordReachesAReader(unittest.TestCase):
    def test_the_rendered_report_passes_its_own_shape_rules(self):
        report, html = render()
        self.assertEqual(validate_run.report_shape_problems(report, html), [])

    def test_an_audits_own_notes_are_put_in_the_reports_words(self):
        report = sample_report.build()
        report["vitals"]["leakage"]["note"] = (
            "leakage is not-visible: 3 vital(s) unmeasured, blast radius unknown, "
            "see /work/northwind-ds/src/a.css:4")
        report["decisions"][0]["moved"] = "tier-integrity: needs-work"
        _report, html = render(report)
        text = text_of(html).lower()
        for word, _instead in validate_run.BANNED_WORDS:
            self.assertNotIn(word, text)
        self.assertNotIn("/work/northwind-ds", html)
        self.assertIn("src/a.css:4", html)

    def test_plurals_are_real(self):
        _report, html = render()
        self.assertNotRegex(text_of(html), r"\w\(s\)")


class TestShowDoNotTell(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report, cls.html = render()

    def test_a_denominator_is_drawn_with_its_figure_and_one_line(self):
        lead = region(self.html, "lineage-lead")
        self.assertIn('class="mk-bar"', lead)
        self.assertIn('<span class="mk-num">226 of 240 (94%)</span>', lead)
        self.assertEqual(lead.count('class="mk-means"'), 1)

    def test_a_threshold_is_a_marker_on_a_track(self):
        card = re.search(r'id="vital-tier-integrity".*?</article>', self.html, re.S).group(0)
        self.assertIn('class="mk-marker"', card)
        self.assertIn('class="mk-tick"', card)

    def test_a_defect_is_shown_as_the_two_declarations_side_by_side(self):
        card = chapter(self.html, "fix-now")
        self.assertEqual(card.count('class="mk-decl"'), 2)
        self.assertEqual(card.count("<s><code>"), 1)

    def test_a_matching_color_is_drawn_beside_its_token(self):
        decide = chapter(self.html, "decide")
        self.assertRegex(decide, r'class="match".*?style="background:#0F8A83".*?'
                                 r'class="tok">color\.semantic\.brand\.base')

    def test_what_we_could_not_see_is_hatched_in_the_cell_that_would_hold_it(self):
        matrix = region(self.html, "coverage-matrix")
        self.assertIn('data-s="not-visible"', matrix)
        self.assertNotRegex(matrix, r'data-s="not-visible"[^>]*>\s*0\s*<')
        self.assertIn('class="mk-hatch"', chapter(self.html, "checks"))

    def test_the_close_calls_are_two_columns_of_dots_with_prose_behind(self):
        calls = region(self.html, "decisions")
        self.assertIn("<th>This reading</th><th>Other reading</th>", calls)
        row = re.search(r'<tr data-decision-index="0".*?</tr>', calls, re.S).group(0)
        self.assertIn('data-g="watch"', row)
        self.assertIn('data-g="needs-work"', row)
        self.assertIn('class="call-more"', row)

    def test_a_call_with_no_other_grade_is_a_ring_and_never_a_guess(self):
        report = sample_report.build()
        report["decisions"] = [{"decision": "We left the docs out.", "moved": "x",
                                "other_reading": "y", "vitals": ["coverage"]}]
        _report, html = render(report)
        row = re.search(r'<tr data-decision-index="0".*?</tr>',
                        region(html, "decisions"), re.S).group(0)
        self.assertIn('data-g="none"', row)


class TestComponentShares(unittest.TestCase):
    def usage(self, **over):
        rows = [{"id": "a" * 12, "rank": 1, "name": "Button", "references": 50},
                {"id": "b" * 12, "rank": 2, "name": "Card", "references": 30}]
        usage = {"state": "counted", "top_20": rows, "shown": 2,
                 "fallback_surfaces": 0, "total_components_with_token_usage": 40,
                 "roadmap": {"ranked_references": 80}}
        usage.update(over)
        return usage

    def test_a_share_is_of_every_component_and_says_so(self):
        usage = self.usage(component_references_total=400)
        self.assertEqual(render_component_usage.share_label(usage["top_20"][0], usage), "12.5%")
        self.assertEqual(render_component_usage.share_whole(usage), (400, "all 40 components"))
        self.assertEqual(render_component_usage.subtitle(usage),
                         "40 components · top 2 carry 20% of token use")

    def test_an_older_run_without_the_total_is_a_share_of_the_rows_shown(self):
        """And says so: a share of twenty rows must not read as a share of all."""
        usage = self.usage()
        self.assertEqual(render_component_usage.share_whole(usage), (80, "the 2 rows shown"))
        self.assertEqual(render_component_usage.share_label(usage["top_20"][0], usage), "62.5%")


if __name__ == "__main__":
    unittest.main()
