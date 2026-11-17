"""The report's page as data: `report.json` carries what the HTML shows first.

Another page should be able to draw this report from `report.json` alone. So
the page object is held to three things: it says what the rendered page says,
its checker rejects each way it can be wrong, and the schema a non-Python
reader uses agrees with the checker.
"""
import copy
import json
import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chapters  # noqa: E402
import family  # noqa: E402
import moves  # noqa: E402
import sample_report  # noqa: E402
import validate_run  # noqa: E402
import vocab  # noqa: E402
from test_report_shape import region, render, text_of  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "assets", "page.schema.json")
TEMPLATE = os.path.join(ROOT, "assets", "report-template.html")


def built():
    report, html = render()
    return report, html, family.build(report, html)


class TestThePageSaysWhatTheReportSays(unittest.TestCase):
    def setUp(self):
        self.report, self.html, self.page = built()

    def test_the_sample_page_is_sound(self):
        self.assertEqual(family.problems(self.page), [])

    def test_the_fact_line_is_the_one_under_the_title(self):
        self.assertEqual(self.page["factLine"],
                         text_of(region(self.html, "runhead-meta")))

    def test_the_sentence_is_the_headline(self):
        self.assertEqual(self.page["verdict"]["sentence"],
                         text_of(region(self.html, "headline")))

    def test_the_strip_is_the_eight_checks_in_the_five_words(self):
        strip = self.page["verdict"]["strip"]
        self.assertEqual([cell["key"] for cell in strip], list(vocab.CHECK_ORDER))
        for cell in strip:
            self.assertEqual(cell["state"], vocab.GRADE_LABEL[cell["grade"]])
            self.assertIn(cell["state"], family.STATES)

    def test_the_counters_are_the_pages_counters(self):
        self.assertEqual(
            [(item["label"], item["count"]) for item in self.page["verdict"]["counters"]],
            [(item["label"], item["count"]) for item in moves.counters(self.report)])

    def test_the_first_moves_are_the_first_three_of_the_one_ranked_list(self):
        ranked = moves.rank(self.report)
        first = self.page["verdict"]["firstMoves"]
        self.assertEqual(len(first), min(3, len(ranked)))
        self.assertEqual([move["kind"] for move in first],
                         [move["kind"] for move in ranked[:3]])
        self.assertIn(first[0]["action"], text_of(region(self.html, "exec-summary")))

    def test_the_chapters_are_the_contents_list_with_the_line_under_each_name(self):
        self.assertEqual(
            [(chapter["n"], chapter["id"], chapter["name"]) for chapter in self.page["chapters"]],
            [tuple(item) for item in validate_run.CHAPTERS])
        for chapter in self.page["chapters"][1:]:
            self.assertIn(chapter["stat"], text_of(self.html))
        self.assertEqual(self.page["chapters"][0]["stat"],
                         vocab.breakdown(vocab.grade_counts(self.report)))

    def test_only_the_verdict_and_the_three_queues_carry_a_state(self):
        stated = [chapter["id"] for chapter in self.page["chapters"]
                  if chapter["state"] is not None]
        self.assertEqual(stated, ["verdict", "fix-now", "decide", "unlock-chapter"])

    def test_an_empty_queue_is_healthy(self):
        report = sample_report.build()
        for name in vocab.CHECK_ORDER:
            report["vitals"][name] = {"grade": "healthy", "evidence": ["a.css:1"], "note": "Fine."}
        _report, html = render(report)
        page = family.build(report, html)
        states = {chapter["id"]: chapter["state"] for chapter in page["chapters"]}
        self.assertEqual(page["verdict"]["state"], "Healthy")
        self.assertEqual(states["fix-now"], "Healthy")
        self.assertEqual(states["unlock-chapter"], "Healthy")

    def test_about_this_run_is_grouped_as_the_page_groups_it(self):
        groups = [group["group"] for group in self.page["about"]]
        self.assertEqual(groups, ["What we read", "Your setup", "What we left out",
                                  "How current it is", "Versions"])
        read = {item["label"]: item["value"] for item in self.page["about"][0]["items"]}
        self.assertEqual(read["source files in scope"],
                         vocab.fmt(chapters.files_in_scope(self.report)))

    def test_the_two_texts_keep_their_limits_and_hold_no_machine_path(self):
        self.assertLessEqual(len(self.page["verdictText"]), family.VERDICT_LIMIT)
        self.assertLessEqual(len(self.page["askText"]), family.ASK_LIMIT)
        self.assertIn(self.page["verdict"]["sentence"], self.page["verdictText"])
        self.assertTrue(self.page["askText"].rstrip().endswith("Start from VERDICT.md."))
        report = sample_report.build()
        report["discovery"]["repository"]["root"] = "/Users/someone/work/northwind-ds"
        for name in ("single-source",):
            report["vitals"][name]["where"] = "/Users/someone/work/northwind-ds/src/button.css:118"
        _report, html = render(report)
        page = family.build(report, html)
        self.assertNotIn("/Users/", page["verdictText"] + page["askText"])

    def test_the_ask_asks_for_evidence_and_never_tells_an_agent_to_fix(self):
        ask = self.page["askText"]
        self.assertIn("change no product code", ask)
        self.assertNotRegex(ask, r"(?m)^- Fix\b")

    def test_a_long_list_is_three_by_name_and_the_rest_as_a_count(self):
        report = sample_report.build()
        calls = report.setdefault("decisions", [])
        self.assertIsInstance(calls, list)
        ranked = moves.rank(report)
        page = family.build(report, render(report)[1])
        if len(ranked) > 3:
            self.assertIn("%d more in the report" % (len(ranked) - 3), page["askText"])
        self.assertLessEqual(page["askText"].count("\n- "), 4)


class TestTheCheckerRejects(unittest.TestCase):
    """A checker is tested by what it refuses."""

    def setUp(self):
        _report, _html, self.page = built()

    def broken(self, change):
        page = copy.deepcopy(self.page)
        change(page)
        return " | ".join(family.problems(page))

    def test_a_shape_it_does_not_know(self):
        self.assertIn("shape", self.broken(lambda p: p.update(shape=2)))

    def test_a_state_outside_the_five_words(self):
        self.assertIn("five states", self.broken(
            lambda p: p["verdict"]["strip"][0].update(state="needs-work")))

    def test_a_word_that_disagrees_with_its_grade(self):
        self.assertIn("for the grade", self.broken(
            lambda p: p["verdict"]["strip"][0].update(state="Healthy", grade="needs-work")))

    def test_a_strip_that_is_not_the_eight_in_order(self):
        self.assertIn("eight checks in order", self.broken(
            lambda p: p["verdict"]["strip"].pop()))

    def test_an_unlock_counter_that_disagrees_with_the_strip(self):
        self.assertIn("Unlock counter", self.broken(
            lambda p: p["verdict"]["counters"][2].update(count=7)))

    def test_counters_out_of_order(self):
        self.assertIn("in order", self.broken(
            lambda p: p["verdict"]["counters"].reverse()))

    def test_more_than_three_first_moves(self):
        self.assertIn("the most is 3", self.broken(
            lambda p: p["verdict"]["firstMoves"].extend(p["verdict"]["firstMoves"])))

    def test_first_moves_out_of_rank_order(self):
        self.assertIn("order fix, decide, unlock", self.broken(
            lambda p: p["verdict"]["firstMoves"].reverse()))

    def test_a_chapter_with_no_line_under_its_name(self):
        self.assertIn("no line under its name", self.broken(
            lambda p: p["chapters"][4].update(stat="")))

    def test_chapters_out_of_order(self):
        self.assertIn("numbered 00 upward", self.broken(
            lambda p: p["chapters"].reverse()))

    def test_a_verdict_text_over_its_limit(self):
        self.assertIn("verdictText is over", self.broken(
            lambda p: p.update(verdictText="x" * (family.VERDICT_LIMIT + 1))))

    def test_an_ask_over_its_limit(self):
        self.assertIn("askText is over", self.broken(
            lambda p: p.update(askText="x" * (family.ASK_LIMIT + 1))))

    def test_a_machine_path_in_a_text(self):
        self.assertIn("absolute path", self.broken(
            lambda p: p.update(askText="read /Users/someone/repo/a.css")))

    def test_an_empty_about_group(self):
        self.assertIn("is empty", self.broken(
            lambda p: p["about"][0].update(items=[])))

    def test_no_page_at_all(self):
        self.assertEqual(family.problems(None), ["page is not an object"])


class TestTheSchemaAgreesWithTheChecker(unittest.TestCase):
    def setUp(self):
        with open(SCHEMA, encoding="utf-8") as handle:
            self.schema = json.load(handle)
        _report, _html, self.page = built()

    def test_it_is_2020_12_with_a_versioned_id(self):
        self.assertEqual(self.schema["$schema"],
                         "https://json-schema.org/draft/2020-12/schema")
        self.assertRegex(self.schema["$id"], r"/page/%d\.\d+\.\d+$" % family.SHAPE)
        self.assertEqual(self.schema["properties"]["shape"]["const"], family.SHAPE)

    def test_it_requires_exactly_the_keys_the_page_has(self):
        self.assertEqual(sorted(self.schema["required"]), sorted(self.page))
        self.assertEqual(sorted(self.schema["properties"]), sorted(self.page))
        verdict = self.schema["properties"]["verdict"]
        self.assertEqual(sorted(verdict["required"]), sorted(self.page["verdict"]))
        chapter = self.schema["properties"]["chapters"]["items"]
        self.assertEqual(sorted(chapter["required"]), sorted(self.page["chapters"][0]))
        cell = verdict["properties"]["strip"]["items"]
        self.assertEqual(sorted(cell["required"]), sorted(self.page["verdict"]["strip"][0]))
        move = verdict["properties"]["firstMoves"]["items"]["properties"]
        for item in self.page["verdict"]["firstMoves"]:
            self.assertLessEqual(set(item), set(move))

    def test_it_names_the_same_five_states_grades_and_limits(self):
        self.assertEqual(tuple(self.schema["$defs"]["state"]["enum"]), family.STATES)
        cell = self.schema["properties"]["verdict"]["properties"]["strip"]["items"]
        self.assertEqual(tuple(cell["properties"]["grade"]["enum"]), vocab.GRADES)
        self.assertEqual(self.schema["properties"]["verdictText"]["maxLength"],
                         family.VERDICT_LIMIT)
        self.assertEqual(self.schema["properties"]["askText"]["maxLength"],
                         family.ASK_LIMIT)
        moves_schema = self.schema["properties"]["verdict"]["properties"]["firstMoves"]
        self.assertEqual(moves_schema["maxItems"], family.FIRST_MOVES)


class TestItIsWrittenWhereverTheReportIs(unittest.TestCase):
    def test_both_renderers_attach_the_page_before_they_write(self):
        for name in ("render_discovery.py", "render_component_usage.py"):
            with open(os.path.join(ROOT, "tools", name), encoding="utf-8") as handle:
                source = handle.read()
            attach = source.index("family.attach(report, document)")
            self.assertLess(attach, source.index("write_json(report_path, report)", attach))
            self.assertIn("family.write_beside(report_path, page)", source)

    def test_the_command_writes_the_page_and_the_two_texts_and_check_reads_them(self):
        report, html = render()
        with tempfile.TemporaryDirectory() as folder:
            report_path = os.path.join(folder, "report.json")
            html_path = os.path.join(folder, "report.html")
            with open(report_path, "w", encoding="utf-8") as handle:
                json.dump(report, handle)
            with open(html_path, "w", encoding="utf-8") as handle:
                handle.write(html)
            self.assertEqual(family.main([report_path, "--check"]), family.EXIT_PROBLEMS)
            self.assertEqual(family.main([report_path, "--html", html_path]), family.EXIT_OK)
            self.assertEqual(family.main([report_path, "--check"]), family.EXIT_OK)
            with open(report_path, encoding="utf-8") as handle:
                page = json.load(handle)["page"]
            for name, key in (("VERDICT.md", "verdictText"), ("ASK.md", "askText")):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    self.assertEqual(handle.read(), page[key] + "\n")


class TestAPassIsSaidInThePageToo(unittest.TestCase):
    def test_stamping_a_pass_refreshes_the_page_kept_in_the_json(self):
        report, html = render()
        family.attach(report, html)
        said = lambda page: [item["value"] for group in page["about"]
                             if group["group"] == "How current it is"
                             for item in group["items"]]
        self.assertIn("Not validated yet.", said(report["page"]))
        with tempfile.TemporaryDirectory() as folder:
            report_path = os.path.join(folder, "report.json")
            html_path = os.path.join(folder, "report.html")
            validate_run.stamp_pass(report_path, report, html_path, html)
            with open(report_path, encoding="utf-8") as handle:
                stamped = json.load(handle)
            self.assertTrue(stamped["provenance"]["validation_gate"]["passed"])
            self.assertNotIn("Not validated yet.", said(stamped["page"]))
            self.assertTrue(any(line.startswith("\u2713 Checked: all")
                                for line in said(stamped["page"])))
            self.assertEqual(family.problems(stamped["page"]), [])

    def test_a_report_with_no_page_is_stamped_as_before(self):
        report, html = render()
        report.pop("page", None)
        with tempfile.TemporaryDirectory() as folder:
            report_path = os.path.join(folder, "report.json")
            validate_run.stamp_pass(report_path, report, None, None)
            with open(report_path, encoding="utf-8") as handle:
                self.assertNotIn("page", json.load(handle))


class TestDensity(unittest.TestCase):
    """The same page, the same order, less of it showing."""

    def setUp(self):
        _report, self.html = render()
        with open(TEMPLATE, encoding="utf-8") as handle:
            self.template = handle.read()

    def test_the_page_root_says_its_density_and_opens_comfortable(self):
        self.assertRegex(self.html, r'<html lang="en" data-density="comfortable">')

    def test_the_switch_offers_the_two_and_only_the_two(self):
        self.assertEqual(re.findall(r'data-density-set="([a-z]+)"', self.html),
                         ["compact", "comfortable"])

    def test_compact_hides_and_never_removes(self):
        compact = re.findall(r'\[data-density="compact"\][^{]*\{([^}]*)\}', self.template)
        self.assertTrue(compact)
        self.assertTrue(any("display: none" in rule for rule in compact))
        for chapter_id in (item[1] for item in validate_run.CHAPTERS):
            self.assertIn('id="%s"' % chapter_id, self.html)

    def test_compact_is_for_a_screen_and_print_is_always_comfortable(self):
        start = self.template.index("/* ---------- density")
        block = self.template[start:self.template.index("/* ---------- a chapter", start)]
        rules = block[block.index("@media screen"):block.index("@media print")]
        self.assertEqual(block.count('[data-density="compact"]'),
                         rules.count('[data-density="compact"]'),
                         "a compact rule outside @media screen would reach print")

    def test_the_controller_keeps_the_choice_and_a_link_into_a_chapter_opens_it(self):
        import render_discovery
        script = render_discovery.INVENTORY_TABS_SCRIPT
        self.assertIn('document.documentElement.dataset.density = value', script)
        self.assertIn('"token-vitals-density"', script)
        self.assertIn('"hashchange"', script)


if __name__ == "__main__":
    unittest.main()
