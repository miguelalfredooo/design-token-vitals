"""Tests for the audit-gap / system-gap split and the unlock path.

`not-visible` says two completely different things with one word: your system
has a problem, and this audit cannot see far enough yet. A repository whose
token layer is in good shape reads as mostly blocked, which is both wrong
and demoralizing. These tests pin the separation.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unlock_path  # noqa: E402


CAPABILITIES = {
    "detection": "verified",
    "production_roots": "verified",
    "import_resolution": "verified",
    "token_source_discovery": "verified",
    "ownership": "verified",
    "mode_resolution": "not-visible",
    "runtime_verification": "not-visible",
}


def report(**grades):
    base = {
        "tier-integrity": "healthy", "leakage": "healthy", "coverage": "healthy",
        "mode-completeness": "not-visible", "naming-coherence": "healthy",
        "single-source": "healthy", "orphans": "healthy", "enforcement": "healthy",
    }
    base.update(grades)
    return {"vitals": {name: {"grade": grade} for name, grade in base.items()}}


class TestConfidence(unittest.TestCase):
    def test_a_real_problem_is_system_work_not_a_blocked_check(self):
        state = unlock_path.build(report(leakage="needs-work"), CAPABILITIES)
        self.assertEqual(state["confidence"]["leakage"]["state"],
                         "needs-work")

    def test_a_check_that_could_not_run_names_the_capability_it_waits_on(self):
        state = unlock_path.build(report(), CAPABILITIES)
        entry = state["confidence"]["mode-completeness"]
        self.assertEqual(entry["state"], "not-visible")
        self.assertEqual(entry["blocked_by"], ["mode_resolution"])

    def test_a_declared_boundary_is_not_a_gap_of_either_kind(self):
        state = unlock_path.build(
            report(**{"mode-completeness": "not-needed"}), CAPABILITIES)
        entry = state["confidence"]["mode-completeness"]
        self.assertEqual(entry["state"], "not-needed")
        self.assertEqual(state["split"]["not_visible"], 0)
        self.assertEqual(state["split"]["your_code"], 0)

    def test_the_two_kinds_of_gap_are_counted_separately_and_never_summed(self):
        state = unlock_path.build(report(leakage="needs-work", orphans="watch"),
                                  CAPABILITIES)
        self.assertEqual(state["split"]["your_code"], 2)
        self.assertEqual(state["split"]["not_visible"], 1)
        self.assertEqual(state["split"]["healthy"], 5)
        self.assertNotIn("total_gaps", state["split"])

    def test_every_vital_gets_exactly_one_confidence_state(self):
        state = unlock_path.build(report(), CAPABILITIES)
        self.assertEqual(set(state["confidence"]), set(unlock_path.VITALS))
        for name, entry in state["confidence"].items():
            self.assertIn(entry["state"], unlock_path.CONFIDENCE_STATES, name)


class TestUnlockPath(unittest.TestCase):
    def test_a_step_says_how_many_vitals_it_unlocks(self):
        capabilities = dict(CAPABILITIES, import_resolution="not-visible")
        state = unlock_path.build(report(
            leakage="not-visible", orphans="not-visible", **{"single-source": "not-visible"}),
            capabilities)
        step = next(item for item in state["unlock_path"]
                    if item["capability"] == "import_resolution")
        self.assertEqual(sorted(step["unlocks"]),
                         ["leakage", "orphans", "single-source"])
        self.assertEqual(step["unlocks_count"], 3)
        self.assertTrue(step["action"])
        self.assertTrue(step["verify"])

    def test_the_path_leads_with_the_step_that_unlocks_the_most(self):
        capabilities = dict(CAPABILITIES, import_resolution="not-visible")
        state = unlock_path.build(report(
            leakage="not-visible", orphans="not-visible",
            **{"single-source": "not-visible", "mode-completeness": "not-visible"}),
            capabilities)
        self.assertEqual([item["capability"] for item in state["unlock_path"]],
                         ["import_resolution", "mode_resolution"])

    def test_a_verified_capability_is_not_a_step(self):
        state = unlock_path.build(report(), CAPABILITIES)
        self.assertNotIn("import_resolution",
                         [item["capability"] for item in state["unlock_path"]])

    def test_a_capability_gap_that_blocks_nothing_is_not_a_step(self):
        """runtime_verification is unmeasured here and no vital waits on it."""
        state = unlock_path.build(
            report(**{"mode-completeness": "not-needed"}), CAPABILITIES)
        self.assertEqual(state["unlock_path"], [])


class TestRunInputGaps(unittest.TestCase):
    """A blocked check with every capability verified still owes a reason.

    `coverage` can be blocked because the run was never told which framework
    version it was reading, which is not a capability the engine lacks — it
    is an input nobody supplied. Left unnamed it produced the one useless
    line in the whole report: blocked, and no gap explains it.
    """

    def test_a_missing_run_input_is_named_and_becomes_a_step(self):
        state = unlock_path.build(
            report(coverage="not-visible",
                   **{"mode-completeness": "not-needed"}),
            dict(CAPABILITIES, framework_versions="not-visible"))
        entry = state["confidence"]["coverage"]
        self.assertEqual(entry["blocked_by"], ["framework_versions"])
        self.assertEqual([item["capability"] for item in state["unlock_path"]],
                         ["framework_versions"])

    def test_a_supplied_run_input_leaves_coverage_unblocked(self):
        state = unlock_path.build(
            report(**{"mode-completeness": "not-needed"}),
            dict(CAPABILITIES, framework_versions="verified"))
        self.assertEqual(state["confidence"]["coverage"]["state"], "healthy")
        self.assertEqual(state["unlock_path"], [])

    def test_a_blocked_vital_no_gap_explains_says_exactly_that(self):
        state = unlock_path.build(
            report(**{"naming-coherence": "not-visible",
                      "mode-completeness": "not-needed"}),
            dict(CAPABILITIES, framework_versions="verified"))
        entry = state["confidence"]["naming-coherence"]
        self.assertEqual(entry["blocked_by"], [])
        self.assertIn("gap in this tool, not in your code", entry["reason"])


class TestNextBestQuarterHour(unittest.TestCase):
    def test_an_audit_gap_leads_when_one_exists(self):
        state = unlock_path.build(report(), CAPABILITIES)
        card = state["next_15_minutes"]
        self.assertIn("mode", card["action"].lower())
        self.assertTrue(card["payoff"])
        self.assertTrue(card["verify"])

    def test_with_nothing_blocked_the_card_names_the_worst_real_finding(self):
        state = unlock_path.build(
            report(leakage="needs-work", **{"mode-completeness": "not-needed"}),
            CAPABILITIES)
        self.assertIn("leakage", state["next_15_minutes"]["action"])

    def test_a_clean_verified_run_says_so_rather_than_inventing_work(self):
        state = unlock_path.build(
            report(**{"mode-completeness": "not-needed"}), CAPABILITIES)
        self.assertIsNone(state["next_15_minutes"])


class TestWins(unittest.TestCase):
    def test_a_verified_capability_is_reported_as_ground_gained(self):
        """And only when the run can put a number beside it."""
        wins = unlock_path.build(
            report(), CAPABILITIES,
            discovery={"import_graph": {"reachable": {"a": {}},
                                        "unresolved": []}})["wins"]
        claims = [win["claim"].lower() for win in wins]
        self.assertTrue(any("import" in claim for claim in claims), claims)

    def test_an_explained_boundary_reads_as_a_decision_not_a_hole(self):
        doc = report(**{"mode-completeness": "not-needed"})
        doc["vitals"]["mode-completeness"]["rationale"] = (
            "One scheme ships, by product decision.")
        state = unlock_path.build(doc, CAPABILITIES)
        self.assertTrue(any("mode-completeness" in win["claim"]
                            for win in state["wins"]))

    def test_nothing_verified_produces_no_invented_win(self):
        capabilities = {name: "not-visible" for name in CAPABILITIES}
        state = unlock_path.build(
            {"vitals": {name: {"grade": "not-visible"} for name in unlock_path.VITALS}},
            capabilities)
        self.assertEqual(state["wins"], [])


if __name__ == "__main__":
    unittest.main()


class TestHeadline(unittest.TestCase):
    """A report opens on a sentence. The grid is the detail under it."""

    def test_the_sentence_leads_with_what_is_proven(self):
        line = unlock_path.build(report(), CAPABILITIES)["headline"]
        self.assertIn("7 of 8", line)
        self.assertIn("healthy", line)

    def test_it_says_audit_capability_rather_than_blaming_the_codebase(self):
        line = unlock_path.build(report(), CAPABILITIES)["headline"]
        self.assertIn("audit", line.lower())
        self.assertNotIn("needs-work", line.lower())

    def test_a_real_problem_is_named_as_one(self):
        line = unlock_path.build(report(leakage="needs-work"), CAPABILITIES)["headline"]
        self.assertIn("fix in your code", line.lower())

    def test_a_fully_verified_run_says_so_without_hedging(self):
        clean = {"vitals": {name: {"grade": "healthy"} for name in unlock_path.VITALS}}
        line = unlock_path.build(clean, dict(
            CAPABILITIES, mode_resolution="verified",
            runtime_verification="verified", framework_versions="verified"))["headline"]
        self.assertIn("all 8", line.lower())


class TestNotApplicableOwesAReason(unittest.TestCase):
    """An unexplained N/A is how a check gets switched off quietly.

    `not-needed` is the one grade that removes a vital from the report
    without anybody having to fix anything, so it is the one grade that has
    to carry a reason. Recorded as owed rather than silently accepted.
    """

    def test_a_rationale_is_carried_through_to_the_state(self):
        doc = report(**{"mode-completeness": "not-needed"})
        doc["vitals"]["mode-completeness"]["rationale"] = (
            "The product ships one scheme by product decision.")
        state = unlock_path.build(doc, CAPABILITIES)
        entry = state["confidence"]["mode-completeness"]
        self.assertEqual(entry["state"], "not-needed")
        self.assertIn("product decision", entry["rationale"])
        self.assertEqual(state["decisions_owed"], [])

    def test_an_unexplained_not_applicable_is_recorded_as_owed(self):
        state = unlock_path.build(
            report(**{"mode-completeness": "not-needed"}), CAPABILITIES)
        self.assertEqual(state["decisions_owed"], ["mode-completeness"])
        self.assertIsNone(
            state["confidence"]["mode-completeness"]["rationale"])

    def test_an_unexplained_boundary_is_not_celebrated_as_a_win(self):
        state = unlock_path.build(
            report(**{"mode-completeness": "not-needed"}), CAPABILITIES)
        self.assertFalse(any("mode-completeness" in win["claim"]
                             for win in state["wins"]))

    def test_an_explained_boundary_is(self):
        doc = report(**{"mode-completeness": "not-needed"})
        doc["vitals"]["mode-completeness"]["rationale"] = "One scheme, by decision."
        state = unlock_path.build(doc, CAPABILITIES)
        self.assertTrue(any("mode-completeness" in win["claim"]
                            for win in state["wins"]))


class TestNoUnprovenClaims(unittest.TestCase):
    """Every line handed to a reader is an observation or it is not shipped.

    Two lines failed that: "Framework detected — the adapters that ran are
    the right ones" is an interpretation that detection cannot support, and
    a verify command containing `<root>` is not a command. A congratulation
    nobody can check is worse than silence, so a win with no measurement
    behind it is not emitted at all.
    """

    DISCOVERY = {
        "repository": {"root": "/repo", "ref": "abc123def456"},
        "capabilities": dict(CAPABILITIES),
        "environment": ["vite"],
        "roots": [{"path": "index.html"}, {"path": "src/main.js"}],
        "import_graph": {
            "reachable": {"a": {}, "b": {}, "c": {}},
            "unresolved": [{"reason": "external package"},
                           {"reason": "remote dependency"}],
        },
        "ownership": {"owned_patterns": ["src/**"]},
    }

    def build(self, discovery=None):
        discovery = self.DISCOVERY if discovery is None else discovery
        return unlock_path.build(report(), discovery.get("capabilities", {}),
                                 discovery=discovery)

    def test_every_win_carries_its_own_measurement(self):
        for win in self.build()["wins"]:
            self.assertTrue(win.get("evidence"), win)

    def test_a_win_with_nothing_to_measure_is_not_emitted(self):
        bare = {"capabilities": dict(CAPABILITIES)}
        for win in unlock_path.build(report(), bare["capabilities"],
                                     discovery=bare)["wins"]:
            self.assertTrue(win.get("evidence"), win)

    def test_the_framework_win_names_what_was_detected_not_a_judgement(self):
        wins = {win["claim"]: win for win in self.build()["wins"]}
        framework = next(k for k in wins if "ramework" in k)
        self.assertIn("vite", wins[framework]["evidence"][0])
        self.assertNotIn("right ones", framework)

    def test_the_import_win_carries_the_count_it_is_claiming_about(self):
        wins = {win["claim"]: win for win in self.build()["wins"]}
        imports = next(k for k in wins if "import" in k.lower())
        self.assertIn("2", " ".join(wins[imports]["evidence"]))

    def test_evidence_recorded_only_in_the_ladder_is_still_found(self):
        """A provable win dropped because one lookup missed is a false zero.

        `token_source_discovery` records its evidence on its capability
        ladder step, not under a `token_sources` key, so looking in one
        place suppressed a win the run had fully established.
        """
        discovery = dict(self.DISCOVERY, capability_ladder={"steps": [
            {"capability": "token_source_discovery",
             "state": "verified",
             "evidence": ["src/globals.css", "src/tokens/colors.js"]},
        ]})
        wins = {win["claim"]: win for win in self.build(discovery)["wins"]}
        token_win = next(k for k in wins if "Token source" in k)
        self.assertIn("src/globals.css", " ".join(wins[token_win]["evidence"]))

    def test_a_capability_with_no_evidence_anywhere_still_produces_no_win(self):
        discovery = dict(self.DISCOVERY, capability_ladder={"steps": [
            {"capability": "token_source_discovery", "state": "verified",
             "evidence": []},
        ]})
        claims = [win["claim"] for win in self.build(discovery)["wins"]]
        self.assertFalse([c for c in claims if "Token source" in c], claims)

    def test_a_verify_command_has_no_placeholder_left_in_it(self):
        state = self.build()
        commands = [step["verify"] for step in state["unlock_path"]]
        commands.append(state["next_15_minutes"]["verify"])
        for command in commands:
            self.assertNotIn("<", command, command)
            self.assertIn("/repo", command)

    def test_no_python_repr_reaches_a_reader(self):
        """`detected_by` is a list, and it was printing as one."""
        for win in self.build()["wins"]:
            for line in win["evidence"]:
                self.assertNotIn("['", line, win)
                self.assertNotIn("{'", line, win)
