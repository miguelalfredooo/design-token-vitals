"""One ranked list answers "what do I do first", and the order is a rule."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import moves  # noqa: E402
from vocab import CHECK_ORDER  # noqa: E402


def report(**over):
    doc = {
        "vitals": {name: {"grade": "healthy"} for name in CHECK_ORDER},
        "executive_summary": {}, "leakage_analysis": {}, "discovery": {},
        "inventory": {}, "confidence": {"unlock_path": []},
    }
    doc.update(over)
    return doc


def with_everything():
    doc = report()
    doc["vitals"]["single-source"] = {
        "grade": "needs-work", "evidence": ["src/a.css:4", "src/a.css:90"],
        "headline": "The hover color is set twice.",
        "fix": "Keep one declaration"}
    doc["vitals"]["leakage"] = {"grade": "not-visible"}
    doc["vitals"]["orphans"] = {"grade": "not-visible"}
    doc["leakage_analysis"] = {"exact_value_candidates": [
        {"id": "a", "locations": ["src/b.css:2"]},
        {"id": "b", "locations": ["src/c.css:9"]}]}
    doc["confidence"] = {"unlock_path": [
        {"capability": "import_resolution", "action": "Resolve the imports",
         "verify": "python3 tools/import_graph.py . --json g.json",
         "unlocks": ["orphans", "leakage"]}]}
    return doc


class TestTheOrderIsARule(unittest.TestCase):
    def test_a_confirmed_defect_comes_before_a_decision_before_an_unlock(self):
        kinds = [move["kind"] for move in moves.rank(with_everything())]
        self.assertEqual(kinds, ["fix", "decide", "unlock"])

    def test_a_cheap_unlock_never_outranks_a_defect(self):
        """The old page led with "Next best 15 minutes: resolve imports" while
        its own summary led with the defect. The defect leads, always."""
        self.assertEqual(moves.first(with_everything())["kind"], "fix")

    def test_with_no_defect_the_decision_leads(self):
        doc = with_everything()
        doc["vitals"]["single-source"] = {"grade": "healthy"}
        self.assertEqual(moves.first(doc)["id"], "decide:matching-colors")

    def test_with_nothing_to_fix_or_decide_the_unlock_leads(self):
        doc = with_everything()
        doc["vitals"]["single-source"] = {"grade": "healthy"}
        doc["leakage_analysis"] = {}
        first = moves.first(doc)
        self.assertEqual(first["kind"], "unlock")
        self.assertTrue(first["command"])

    def test_a_clean_run_has_no_first_move_and_invents_none(self):
        self.assertIsNone(moves.first(report()))
        self.assertEqual(moves.rank(report()), [])

    def test_two_defects_follow_the_fixed_order_of_the_checks(self):
        doc = report()
        doc["vitals"]["orphans"] = {"grade": "needs-work"}
        doc["vitals"]["tier-integrity"] = {"grade": "needs-work"}
        self.assertEqual([move["check"] for move in moves.fix_moves(doc)],
                         ["tier-integrity", "orphans"])

    def test_the_order_is_the_same_on_every_call(self):
        doc = with_everything()
        self.assertEqual([m["id"] for m in moves.rank(doc)],
                         [m["id"] for m in moves.rank(doc)])


class TestAMoveSaysWhatToDo(unittest.TestCase):
    def test_a_fix_names_the_finding_then_the_action_then_the_place(self):
        move = moves.fix_moves(with_everything())[0]
        self.assertEqual(move["title"], "The hover color is set twice.")
        self.assertEqual(move["action"], "Keep one declaration.")
        self.assertEqual(move["where"], "src/a.css:4")

    def test_the_runs_own_fix_first_feeds_the_first_defect_only(self):
        doc = report(executive_summary={
            "highest_impact": {"statement": "A thing is wrong", "blast_radius": "every button"},
            "fix_first": {"action": "Do this", "file_line": "src/z.css:1"}})
        doc["vitals"]["tier-integrity"] = {"grade": "needs-work", "note": "First note."}
        doc["vitals"]["orphans"] = {"grade": "needs-work", "note": "Second note. More."}
        first, second = moves.fix_moves(doc)
        self.assertEqual((first["title"], first["action"], first["where"], first["reach"]),
                         ("A thing is wrong.", "Do this.", "src/z.css:1", "every button"))
        self.assertEqual(second["title"], "Second note.")
        self.assertIsNone(second["reach"])

    def test_a_decision_is_already_an_instruction(self):
        move = moves.decide_moves(with_everything())[0]
        self.assertEqual(move["title"], "Decide what the 2 matching colors are.")
        self.assertEqual(move["action"], move["title"])
        self.assertEqual(move["detail"], "Leakage stays blocked until you do.")

    def test_one_matching_color_is_singular(self):
        doc = with_everything()
        doc["leakage_analysis"]["exact_value_candidates"] = [{"id": "a", "locations": []}]
        self.assertEqual(moves.decide_moves(doc)[0]["title"],
                         "Decide what the 1 matching color is.")

    def test_an_unlock_says_which_checks_it_unblocks_in_their_fixed_order(self):
        move = moves.unlock_moves(with_everything())[0]
        self.assertEqual(move["unlocks"], ["leakage", "orphans"])
        self.assertEqual(move["detail"], "Unblocks leakage and unused tokens.")

    def test_every_other_call_that_waits_on_the_reader_is_a_decision(self):
        doc = report(
            discovery={"roots": [{"path": "index.html", "ownership": "unknown"}]},
            inventory={"candidate_or_local_override_sources": [{"path": "a.css"}, {"path": "b.css"}]},
            confidence={"unlock_path": [], "decisions_owed": ["coverage"]})
        self.assertEqual([move["id"] for move in moves.decide_moves(doc)],
                         ["decide:root-owners", "decide:held-out-sources",
                          "decide:reasons-owed"])


class TestCounters(unittest.TestCase):
    def test_fix_and_unlock_count_checks_so_they_agree_with_the_strip(self):
        fix, decide, unlock = moves.counters(with_everything())
        self.assertEqual((fix["count"], fix["unit"]), (1, "confirmed defect"))
        self.assertEqual((unlock["count"], unlock["unit"]), (2, "blocked checks"))
        self.assertEqual((decide["count"], decide["unit"]), (1, "call to make"))

    def test_each_counter_links_to_its_chapter(self):
        self.assertEqual([item["href"] for item in moves.counters(report())],
                         ["#fix-now", "#decide", "#unlock"])

    def test_the_json_twin_of_the_list_is_the_list(self):
        doc = with_everything()
        self.assertEqual([row[0] for row in moves.as_rows(doc)],
                         [move["title"] for move in moves.rank(doc)])


class TestThePromptForAnAgent(unittest.TestCase):
    """The same ranked list, as a brief. Each kind of move is a different order."""

    def setUp(self):
        self.prompt = moves.agent_prompt(with_everything())

    def section(self, name):
        start = self.prompt.index(name)
        rest = self.prompt[start:].split("\n\n", 1)[0]
        return rest

    def test_a_defect_is_work_to_do_with_its_place(self):
        fix = self.section("FIX.")
        self.assertIn("The hover color is set twice. Keep one declaration. At src/a.css:4.", fix)

    def test_a_decision_is_a_question_for_a_person_and_never_a_task(self):
        ask = self.section("ASK.")
        self.assertIn("Do not decide these yourself", ask)
        self.assertIn("Decide what the 2 matching colors are.", ask)
        self.assertNotIn("matching colors", self.section("FIX."))

    def test_a_blocked_check_is_named_as_unseen_and_left_alone(self):
        leave = self.section("LEAVE ALONE:")
        self.assertIn("Leakage and Unused tokens are blocked", leave)
        self.assertIn("does not mean the code is wrong", leave)
        self.assertIn("Remove no token and replace no hardcoded color", leave)

    def test_it_says_when_the_work_is_done(self):
        self.assertIn("Single source is no longer graded Fix", self.section("DONE WHEN:"))

    def test_every_ranked_move_is_in_it_in_order(self):
        positions = [self.prompt.index(move["title"]) for move in moves.rank(with_everything())]
        self.assertEqual(positions, sorted(positions))

    def test_a_clean_run_hands_an_agent_nothing_to_invent(self):
        self.assertEqual(moves.agent_prompt(report()), "")

    def test_the_runs_own_house_rules_are_added_and_none_is_assumed(self):
        self.assertNotIn("HOUSE RULES", self.prompt)
        doc = with_everything()
        doc["handoff"] = {"house_rules": "One pull request for each change."}
        self.assertIn("HOUSE RULES: One pull request for each change.",
                      moves.agent_prompt(doc))

    def test_paths_and_commands_are_relative_and_still_run(self):
        doc = with_everything()
        doc["vitals"]["single-source"]["where"] = "/work/app/src/a.css:90"
        doc["confidence"]["unlock_path"][0]["verify"] = (
            "python3 tools/import_graph.py . --json .token-vitals/graph.json")
        prompt = moves.agent_prompt(doc, "/work/app")
        self.assertNotIn("/work/app", prompt)
        self.assertIn("At src/a.css:90.", prompt)
        self.assertIn(".token-vitals/graph.json", prompt)


if __name__ == "__main__":
    unittest.main()
