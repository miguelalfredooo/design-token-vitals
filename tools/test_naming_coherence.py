"""Tests for the naming-grammar count behind `naming-coherence`.

Every case here was watched failing before it was written down. The two
that matter most are the ones that keep the tool honest in the other
direction: a system of single-word names is `blocked` rather than `pass`,
and a system that abbreviates consistently reports no spelling pair.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import naming_coherence  # noqa: E402


def repo(**files):
    root = tempfile.mkdtemp()
    for relative, text in files.items():
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return root


def tokens_for(*paths):
    return {"sources": [{"path": path, "role": "canonical"} for path in paths]}


class TestGrammarCount(unittest.TestCase):
    def test_one_grammar_passes_and_every_name_reached_the_count(self):
        root = repo(**{"a.css": ":root{--color-bg:#fff;--space-4:4px;--radius-md:6px;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["grade"], "pass")
        self.assertEqual(result["grammar_count"], 1)
        # Guard the guard: count what reached the grammar tally, not what
        # the walk merely found. A filter that ate every name would leave
        # the count at one grammar and still read as a pass.
        self.assertEqual(result["names_seen"], 3)
        self.assertEqual(result["grammars"][0]["count"], 3)

    def test_a_second_grammar_moves_the_grade_and_names_its_line(self):
        root = repo(**{"a.css": ":root{--color-bg:#fff;\n--color_fg:#000;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["grade"], "attention")
        self.assertEqual(result["grammar_count"], 2)
        snake = [item for item in result["grammars"] if item["id"] == "snake-lower"][0]
        self.assertEqual(snake["evidence"], ["a.css:2"])

    def test_three_grammars_fail(self):
        root = repo(**{"a.css": ":root{--color-bg:#fff;--color_fg:#000;--colorAccent:#f00;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["grade"], "fail")
        self.assertEqual(result["grammar_count"], 3)

    def test_screaming_snake_is_a_different_grammar_from_snake(self):
        root = repo(**{"a.css": ":root{--color_bg:#fff;--COLOR_FG:#000;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(
            sorted(item["id"] for item in result["grammars"]),
            ["snake-lower", "snake-upper"])


class TestWhatIsNotAGrammar(unittest.TestCase):
    def test_single_word_names_are_blocked_never_pass(self):
        """Zero grammars is not one grammar.

        A one-word name carries no evidence about how this system spells a
        boundary. Grading that `pass` would let silence do the work of a
        measurement, which principle 6 forbids.
        """
        root = repo(**{"a.css": ":root{--brand:#fff;--surface:#eee;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["grade"], "blocked")
        self.assertEqual(result["grammar_count"], 0)
        self.assertEqual(result["unsegmented"]["count"], 2)

    def test_a_single_word_beside_a_grammar_does_not_add_one(self):
        root = repo(**{"a.css": ":root{--brand:#fff;--color-bg:#eee;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["grade"], "pass")
        self.assertEqual(result["grammar_count"], 1)

    def test_a_consumer_override_is_not_this_systems_grammar(self):
        root = repo(**{
            "own.css": ":root{--color-bg:#fff;}",
            "vendor.css": ":root{--vendorThing:#000;}",
        })
        tokens = {"sources": [
            {"path": "own.css", "role": "canonical"},
            {"path": "vendor.css", "role": "consumer-override"},
        ]}
        result = naming_coherence.measure(root, tokens)
        self.assertEqual(result["grammar_count"], 1)
        self.assertEqual(result["names_seen"], 1)

    def test_an_unreadable_source_is_recorded_not_dropped(self):
        root = repo(**{"a.css": ":root{--color-bg:#fff;}"})
        result = naming_coherence.measure(root, tokens_for("a.css", "gone.css"))
        self.assertEqual([item["path"] for item in result["unmeasured"]], ["gone.css"])

    def test_no_readable_source_is_blocked(self):
        root = repo(**{"a.css": ""})
        result = naming_coherence.measure(root, tokens_for("gone.css"))
        self.assertEqual(result["grade"], "blocked")
        self.assertEqual(result["names_seen"], 0)


class TestSpellingPairs(unittest.TestCase):
    def test_the_vitals_worked_example_is_found(self):
        root = repo(**{"a.css": ":root{--btn-pad-x:4px;\n--button-padding-inline:4px;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["grammar_count"], 1, "one grammar, two spellings")
        pairs = {(item["short"], item["long"]) for item in result["spelling_pairs"]}
        self.assertIn(("btn", "button"), pairs)
        self.assertIn(("pad", "padding"), pairs)
        self.assertIn(("x", "inline"), pairs)

    def test_consistent_abbreviation_reports_nothing(self):
        """Abbreviating is not the finding. Abbreviating sometimes is."""
        root = repo(**{"a.css": ":root{--btn-pad-x:4px;--btn-pad-y:2px;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["spelling_pairs"], [])

    def test_a_pair_carries_evidence_from_both_sides(self):
        root = repo(**{"a.css": ":root{--bg-base:#fff;\n--background-raised:#eee;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        pair = [item for item in result["spelling_pairs"] if item["short"] == "bg"][0]
        self.assertEqual(pair["short_evidence"], ["a.css:1"])
        self.assertEqual(pair["long_evidence"], ["a.css:2"])


class TestDeclaredGrammar(unittest.TestCase):
    def test_a_stylelint_pattern_is_the_project_declaring_its_grammar(self):
        root = repo(**{
            "a.css": ":root{--color-bg:#fff;--colorFg:#000;}",
            ".stylelintrc.json": '{"rules":{"custom-property-pattern":"^[a-z]+(-[a-z0-9]+)*$"}}',
        })
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["declared"]["state"], "declared")
        self.assertEqual(result["declared"]["site"], ".stylelintrc.json:1")
        self.assertEqual(result["conformance"]["outside"], 1)
        self.assertEqual(result["conformance"]["examples"], ["--colorFg"])

    def test_without_a_declaration_the_dominant_grammar_is_labeled_inferred(self):
        root = repo(**{"a.css": ":root{--color-bg:#fff;--color-fg:#000;--color_x:#0f0;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["declared"]["state"], "inferred")
        self.assertEqual(result["declared"]["pattern"], "kebab-lower")
        self.assertIsNone(result["conformance"],
                          "an inferred grammar is never graded against")


class TestFamilyPosition(unittest.TestCase):
    def test_position_is_reported_and_never_changes_the_grade(self):
        root = repo(**{"a.css": ":root{--color-bg-x:#fff;--x-bg-color:#000;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        self.assertEqual(result["grade"], "pass")
        self.assertEqual(result["family_position"]["leading"], 1)
        self.assertEqual(result["family_position"]["trailing"], 1)


class TestSummary(unittest.TestCase):
    """The terminal summary had no test until a mutation that breaks it
    stayed green. It is the only part of this tool most people read."""

    def test_the_summary_names_the_grade_the_grammars_and_the_pairs(self):
        root = repo(**{"a.css": ":root{--btn-pad-x:4px;\n--button_padding_inline:4px;}"})
        result = naming_coherence.measure(root, tokens_for("a.css"))
        summary = naming_coherence.summarize(result)
        self.assertIn("naming-coherence: attention", summary)
        self.assertIn("kebab-lower", summary)
        self.assertIn("snake-lower", summary)
        self.assertIn("same word two ways: btn and button", summary)

    def test_the_summary_names_an_unmeasured_source(self):
        root = repo(**{"a.css": ":root{--color-bg:#fff;}"})
        result = naming_coherence.measure(root, tokens_for("a.css", "gone.css"))
        self.assertIn("unmeasured: gone.css", naming_coherence.summarize(result))


class TestSyntaxBoundary(unittest.TestCase):
    """A JS identifier cannot hold a hyphen.

    Found by running the tool against a real repository: it graded `fail`
    on a system whose CSS custom properties are uniformly kebab, because
    two JS object keys and a dotted path were counted beside them. That
    is grading the language rather than the system.
    """

    def test_camel_in_js_beside_kebab_in_css_is_one_convention(self):
        root = repo(**{
            "a.css": ":root{--color-bg:#fff;--color-fg:#000;}",
            "theme.ts": "export const tokens = {\n"
                        "  colorAccent: '#f00',\n"
                        "  spaceSmall: '4px',\n}\n",
        })
        result = naming_coherence.measure(
            root, tokens_for("a.css", "theme.ts"))
        self.assertEqual(result["grade"], "pass")
        self.assertEqual(result["grammar_count"], 1)
        self.assertEqual(
            result["grammars_per_syntax"],
            {"css": ["kebab-lower"], "js": ["camel-mixed"]})

    def test_two_grammars_inside_one_syntax_still_counts(self):
        root = repo(**{
            "a.css": ":root{--color-bg:#fff;--color_fg:#000;}",
            "theme.ts": "export const tokens = {\n"
                        "  colorAccent: '#f00',\n"
                        "  colorBase: '#0f0',\n}\n",
        })
        result = naming_coherence.measure(
            root, tokens_for("a.css", "theme.ts"))
        self.assertEqual(result["grade"], "attention")
        self.assertEqual(result["grammar_count"], 2)
        self.assertEqual(result["grammars_per_syntax"]["css"],
                         ["kebab-lower", "snake-lower"])


    def test_a_nesting_path_is_structure_and_the_leaf_is_the_name(self):
        """A DTCG file reaches the tool as `color.primitive.blue-500`.

        Read whole, that name spells no boundary and lands in the
        unsegmented pile, which grades `blocked` on a system whose leaves
        are uniformly kebab. Read as a leaf, it is a kebab name.
        """
        root = repo(**{"tokens.json": (
            '{\n "color": {\n  "primitive": {\n'
            '   "blue-500": { "value": "#3b82f6", "type": "color" },\n'
            '   "gray-100": { "value": "#f3f4f6", "type": "color" }\n'
            '  }\n }\n}\n')})
        result = naming_coherence.measure(root, tokens_for("tokens.json"))
        self.assertEqual(result["grade"], "pass")
        self.assertEqual(result["grammars_per_syntax"], {"json": ["kebab-lower"]})
        self.assertEqual(result["unsegmented"]["count"], 0)

    def test_a_nesting_group_does_not_lend_its_spelling_to_the_leaf(self):
        """The discriminating case: hyphen in the group, one word in the leaf.

        Read whole, every name here spells a boundary and the file grades
        `pass` on a grammar none of its tokens actually use. Read as
        leaves, the file is single-word names and grades `blocked`, which
        is the honest answer.
        """
        root = repo(**{"tokens.json": (
            '{\n "brand-colors": {\n'
            '  "primary": { "value": "#3b82f6", "type": "color" },\n'
            '  "secondary": { "value": "#f3f4f6", "type": "color" }\n'
            ' }\n}\n')})
        result = naming_coherence.measure(root, tokens_for("tokens.json"))
        self.assertEqual(result["grade"], "blocked")
        self.assertEqual(result["grammar_count"], 0)
        self.assertEqual(result["unsegmented"]["count"], 2)


if __name__ == "__main__":
    unittest.main()
