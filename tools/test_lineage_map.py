"""Tests for the token lineage map.

A grade says how a system is doing. A lineage map says what the system IS:
where a value is defined, the role that names it, the variable that carries
it, and the components that spend it. That is the artifact a designer can
read, and the run already holds every part of it in three separate files.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lineage_map  # noqa: E402


def concept(token_id, tier, value, site, alias_of=None, family="color"):
    return {"id": token_id, "tier": tier, "family": family,
            "values": [value], "sites": [site], "alias_of": alias_of,
            "alias_resolved": None}


TOKENS = {"concepts": [
    concept("blue-500", "primitive", "#6b5bf0", "src/globals.css:2"),
    concept("color-action", "semantic", "var(--blue-500)", "src/globals.css:9",
            alias_of="blue-500"),
    concept("button-bg", "component", "var(--color-action)",
            "src/tokens/profiles.js:41", alias_of="color-action"),
    concept("orphan-role", "semantic", "var(--from-elsewhere)",
            "src/globals.css:12", alias_of="from-elsewhere"),
]}

COMPONENTS = {"top_20": [{
    "name": "src / Button", "key": "src::button", "references": 12,
    "tokens": [{"id": "button-bg", "family": "color", "references": 12,
                "locations": ["src/components/Button/button.css:4"]}],
}]}


class TestChains(unittest.TestCase):
    def test_a_chain_runs_from_the_consumer_back_to_a_primitive(self):
        chains = lineage_map.build(TOKENS, COMPONENTS)["chains"]
        chain = next(item for item in chains if item["token"] == "button-bg")
        self.assertEqual([hop["token"] for hop in chain["hops"]],
                         ["button-bg", "color-action", "blue-500"])
        self.assertEqual(chain["root"]["tier"], "primitive")
        self.assertEqual(chain["root"]["value"], "#6b5bf0")
        self.assertTrue(chain["complete"])

    def test_every_hop_carries_the_site_that_defines_it(self):
        chain = next(item for item in lineage_map.build(TOKENS, COMPONENTS)["chains"]
                     if item["token"] == "button-bg")
        self.assertEqual([hop["site"] for hop in chain["hops"]],
                         ["src/tokens/profiles.js:41", "src/globals.css:9",
                          "src/globals.css:2"])

    def test_a_chain_that_leaves_the_run_stops_and_says_so(self):
        chain = next(item for item in lineage_map.build(TOKENS, COMPONENTS)["chains"]
                     if item["token"] == "orphan-role")
        self.assertFalse(chain["complete"])
        self.assertIsNone(chain["root"])
        self.assertEqual(chain["stops_at"], "from-elsewhere")

    def test_consumers_are_attached_to_the_token_they_actually_spend(self):
        chain = next(item for item in lineage_map.build(TOKENS, COMPONENTS)["chains"]
                     if item["token"] == "button-bg")
        self.assertEqual(chain["consumers"],
                         [{"component": "src / Button", "references": 12,
                           "locations": ["src/components/Button/button.css:4"]}])

    def test_a_cycle_terminates_instead_of_walking_forever(self):
        tokens = {"concepts": [
            concept("a", "semantic", "var(--b)", "x.css:1", alias_of="b"),
            concept("b", "semantic", "var(--a)", "x.css:2", alias_of="a"),
        ]}
        chain = next(item for item in lineage_map.build(tokens, {})["chains"]
                     if item["token"] == "a")
        self.assertFalse(chain["complete"])
        self.assertEqual(chain["stops_at"], "a")
        self.assertIn("cycle", chain["note"].lower())


class TestSummary(unittest.TestCase):
    def test_the_summary_counts_what_traced_and_what_did_not(self):
        summary = lineage_map.build(TOKENS, COMPONENTS)["summary"]
        self.assertEqual(summary["traced_to_a_primitive"], 3)
        self.assertEqual(summary["stops_before_a_primitive"], 1)
        self.assertEqual(summary["with_a_named_consumer"], 1)

    def test_a_family_is_fully_traceable_only_when_every_token_is(self):
        result = lineage_map.build(TOKENS, COMPONENTS)
        self.assertEqual(result["fully_traceable_families"], [])

    def test_a_clean_family_is_named_as_the_win_it_is(self):
        tokens = {"concepts": [
            concept("blue-500", "primitive", "#6b5bf0", "g.css:1"),
            concept("color-action", "semantic", "var(--blue-500)", "g.css:2",
                    alias_of="blue-500"),
            concept("space-2", "primitive", "8px", "g.css:3", family="spacing"),
        ]}
        result = lineage_map.build(tokens, {})
        self.assertEqual(result["fully_traceable_families"], ["color", "spacing"])


if __name__ == "__main__":
    unittest.main()


class TestBlastRadius(unittest.TestCase):
    """The question a designer actually arrives with, and it needs no grade.

    "Changing --color-action-primary touches 11 components" is answerable
    from the chains already built: walk the alias edges the other way, and
    every consumer downstream of a token is in its blast radius — not only
    the ones that name it directly.
    """

    TOKENS = {"concepts": [
        concept("blue-500", "primitive", "#6b5bf0", "g.css:1"),
        concept("color-action", "semantic", "var(--blue-500)", "g.css:2",
                alias_of="blue-500"),
        concept("button-bg", "component", "var(--color-action)", "p.js:1",
                alias_of="color-action"),
        concept("chip-bg", "component", "var(--color-action)", "p.js:2",
                alias_of="color-action"),
        concept("grey-100", "primitive", "#eee", "g.css:3"),
    ]}
    COMPONENTS = {"top_20": [
        {"name": "Button", "tokens": [
            {"id": "button-bg", "references": 4, "locations": ["b.css:1"]}]},
        {"name": "Chip", "tokens": [
            {"id": "chip-bg", "references": 2, "locations": ["c.css:1"]}]},
        {"name": "Card", "tokens": [
            {"id": "color-action", "references": 1, "locations": ["k.css:1"]}]},
    ]}

    def radius(self):
        return {item["token"]: item for item in
                lineage_map.build(self.TOKENS, self.COMPONENTS)["blast_radius"]}

    def test_a_primitive_reaches_every_component_downstream_of_it(self):
        entry = self.radius()["blue-500"]
        self.assertEqual(entry["components"], ["Button", "Card", "Chip"])
        self.assertEqual(entry["component_count"], 3)

    def test_the_dependent_tokens_are_named_as_well_as_counted(self):
        entry = self.radius()["blue-500"]
        self.assertEqual(entry["dependent_tokens"],
                         ["button-bg", "chip-bg", "color-action"])

    def test_a_token_nothing_depends_on_has_a_radius_of_its_own_consumers(self):
        entry = self.radius()["grey-100"]
        self.assertEqual(entry["components"], [])
        self.assertEqual(entry["dependent_tokens"], [])

    def test_the_list_leads_with_the_widest_reach(self):
        order = [item["token"] for item in
                 lineage_map.build(self.TOKENS, self.COMPONENTS)["blast_radius"]]
        self.assertEqual(order[0], "blue-500")
        self.assertEqual(order[1], "color-action")

    def test_a_cycle_does_not_hang_the_walk(self):
        tokens = {"concepts": [
            concept("a", "semantic", "var(--b)", "x.css:1", alias_of="b"),
            concept("b", "semantic", "var(--a)", "x.css:2", alias_of="a"),
        ]}
        radius = lineage_map.build(tokens, {})["blast_radius"]
        self.assertEqual(len(radius), 2)
