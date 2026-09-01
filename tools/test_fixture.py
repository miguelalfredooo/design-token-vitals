"""The fixture repository, checked against its own golden output.

`fixtures/expected.json` records what a correct run must find. Most of it
needs a language model to produce, and a useful part of it does not: the
import graph, the token count, which tokens are orphaned, and whether the
excluded directories really do hold the decoy literals that make excluding
them meaningful.

Those are checked here, so a change to reachability or to the taxonomy
fails a test rather than quietly changing what the fixture proves.

The parts that need a real run — grades, leak classification, the fix
queue — stay a manual comparison against `fixtures/expected.json`.
"""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_graph  # noqa: E402
from validate_run import FAMILIES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "fixtures", "repo")
EXPECTED = json.load(open(os.path.join(ROOT, "fixtures", "expected.json"), encoding="utf-8"))

DECL = re.compile(r"^\s*(--[a-z0-9-]+)\s*:", re.M)
USE = re.compile(r"var\((--[a-z0-9-]+)")
SCSS_VAR = re.compile(r"^\$([a-z0-9-]+)\s*:", re.M)

# The sources that define tokens, from expected.json's classification.
DEFINING = ["app/globals.css", "app/theme.css", "styles/_primitives.scss"]
CONSUMING = ["app/components.css", "packages/ui/src/theme.css"]


def read(rel):
    with open(os.path.join(FIXTURE, rel), encoding="utf-8") as fh:
        return fh.read()


THEME_ROOT = re.compile(r"^\s*(:root|html|\[data-theme[^\]]*\]|\.dark|\.light|@theme|@media\s*\(prefers-color-scheme[^)]*\))\s*$")


def theme_root_declarations(text):
    """Custom properties declared under a theme root, by selector scope.

    A property inside a component rule is local state, whichever file it
    sits in — the rule vitals.md pins. This walks blocks and keeps only
    what sits directly under :root, a scheme class, @theme, or a mode
    media query.
    """
    text = re.sub(r"#\{[^}]*\}", "INTERP", text)  # #{$x} is a value, never a block
    out, stack, buf = set(), [], ""
    for ch in text:
        if ch == "{":
            stack.append(buf.strip().split("\n")[-1].strip())
            buf = ""
        elif ch == "}":
            if stack:
                stack.pop()
            buf = ""
        else:
            buf += ch
            if ch == ";" and stack and THEME_ROOT.match(stack[-1]):
                m = re.match(r"\s*(--[a-z0-9-]+)\s*:", buf)
                if m:
                    out.add(m.group(1))
                buf = ""
    return out


def declared_tokens():
    out = set()
    for rel in DEFINING:
        out |= theme_root_declarations(read(rel))
    return out


class TestFixtureExists(unittest.TestCase):
    def test_every_file_expected_json_names_is_present(self):
        for src in EXPECTED["discovery"]["token_sources"]:
            self.assertTrue(os.path.isfile(os.path.join(FIXTURE, src["path"])), src["path"])

    def test_the_excluded_directories_survived_gitignore(self):
        """A global gitignore excludes node_modules/ and dist/ by default.

        If these go missing from a clone, the fixture stops proving that a
        run excludes them, and it does it silently.
        """
        for rel in ("node_modules/pkg/theme.css", "dist/bundle.css"):
            self.assertTrue(os.path.isfile(os.path.join(FIXTURE, rel)),
                            "%s is missing — check fixtures/.gitignore" % rel)


class TestImportGraph(unittest.TestCase):
    def setUp(self):
        self.graph = import_graph.build(FIXTURE, ["app/layout.tsx"])

    def test_reachable_set_matches_expected(self):
        self.assertEqual(
            set(self.graph["reachable"]),
            set(EXPECTED["discovery"]["import_graph"]["reachable"]),
        )

    def test_the_orphan_stylesheet_is_the_only_orphan(self):
        self.assertEqual(self.graph["orphans"],
                         EXPECTED["discovery"]["import_graph"]["orphans"])

    def test_the_semantic_layer_is_reached_through_the_primitives(self):
        via = self.graph["reachable"]["app/theme.css"]["via"]
        self.assertIn("app/globals.css", via)

    def test_the_scss_partial_is_reached_through_its_entry(self):
        via = self.graph["reachable"]["styles/_primitives.scss"]["via"]
        self.assertIn("styles/main.scss", via)

    def test_a_workspace_package_resolves_by_name(self):
        """globals.css imports "ui/theme.css"; the file is packages/ui/src/theme.css."""
        self.assertIn("packages/ui/src/theme.css", self.graph["reachable"])
        self.assertEqual(self.graph["workspace_packages"], {"ui": "packages/ui"})
        self.assertEqual([u["spec"] for u in self.graph["unresolved"]], ["tailwindcss"])

    def test_excluded_directories_contribute_nothing(self):
        joined = " ".join(self.graph["reachable"]) + " ".join(self.graph["orphans"])
        self.assertNotIn("node_modules", joined)
        self.assertNotIn("dist/", joined)


class TestTokenAccounting(unittest.TestCase):
    def test_token_count_matches_expected(self):
        self.assertEqual(len(declared_tokens()), EXPECTED["counts"]["token_count"])

    def test_the_projection_pair_is_one_concept_per_name(self):
        """Two SCSS variables and two custom properties, not four tokens."""
        scss = read("styles/_primitives.scss")
        variables = SCSS_VAR.findall(scss)
        projected = DECL.findall(scss)
        self.assertEqual(len(variables), 2)
        self.assertEqual(len(projected), 2)
        # Each variable is interpolated into the property of the same name.
        for name in variables:
            self.assertIn("--%s: #{$%s}" % (name, name), scss)

    def test_counting_both_sides_would_give_the_wrong_answer(self):
        """The number the fixture exists to catch."""
        naive = len(declared_tokens()) + len(SCSS_VAR.findall(read("styles/_primitives.scss")))
        self.assertEqual(naive, 23)
        self.assertNotEqual(naive, EXPECTED["counts"]["token_count"])

    def test_the_orphan_token_is_the_only_unreferenced_one(self):
        used = set()
        for rel in CONSUMING + DEFINING:
            used |= set(USE.findall(read(rel)))
        unreferenced = sorted(declared_tokens() - used)
        self.assertEqual(unreferenced, EXPECTED["counts"]["orphan_tokens"])

    def test_a_scoped_property_is_never_counted(self):
        """--panel-gap is declared inside .panel; it is state, whichever file holds it."""
        text = read("app/components.css")
        self.assertIn("--panel-gap: 12px", text)
        self.assertNotIn("--panel-gap", theme_root_declarations(text))
        self.assertNotIn("--panel-gap", declared_tokens())
        self.assertEqual(EXPECTED["counts"]["scoped_properties_not_counted"], ["--panel-gap"])

    def test_a_theme_block_declaration_is_counted(self):
        """--spacing sits in @theme, which is a theme root."""
        self.assertIn("--spacing", declared_tokens())

    def test_counting_by_file_would_give_the_wrong_answer(self):
        """The trap the afternoon runs fell into, from both sides."""
        by_file = set()
        for rel in DEFINING + ["app/components.css"]:
            by_file |= set(DECL.findall(read(rel)))
        self.assertIn("--panel-gap", by_file)
        self.assertGreater(len(by_file), EXPECTED["counts"]["token_count"])

    def test_a_derived_scale_step_has_no_named_token(self):
        """20px is covered only by --spacing x 5, which is not a name to swap to."""
        self.assertIn("20px", read("components/card.tsx"))
        named_values = re.findall(r"--[a-z0-9-]+\s*:\s*([^;]+);", read("app/globals.css"))
        self.assertNotIn("20px", [v.strip() for v in named_values])
        uncovered = [l["literal"] for l in EXPECTED["leaks"]["uncovered"]]
        self.assertIn("20px", uncovered)

    def test_a_name_at_two_theme_roots_counts_once(self):
        """--spacing sits in @theme and again under .theme-compact. One token."""
        text = read("app/globals.css")
        self.assertEqual(text.count("--spacing:"), 2)
        self.assertEqual(sum(1 for t in declared_tokens() if t == "--spacing"), 1)

    def test_leakage_grades_on_findings_and_reports_occurrences(self):
        """8px is one finding in two files: the grade reads 3, the blast radius reads 4."""
        red = EXPECTED["leaks"]["redundant"]
        self.assertEqual(len(red), EXPECTED["leaks"]["redundant_findings"])
        self.assertEqual(sum(len(r["files"]) for r in red), EXPECTED["leaks"]["redundant_occurrences"])
        self.assertEqual(EXPECTED["vitals"]["leakage"], "attention")

    def test_the_unreachable_source_holds_real_declarations(self):
        """An empty decoy would prove nothing about reachability."""
        self.assertEqual(len(DECL.findall(read("app/orphan-tokens.css"))), 3)


class TestFamilies(unittest.TestCase):
    def test_measured_and_absent_together_cover_the_taxonomy(self):
        fams = EXPECTED["inventory_families"]
        listed = set(fams["measured"]) | set(fams["absent"]) | set(fams["unmeasured"])
        self.assertEqual(listed, set(FAMILIES),
                         "fixtures/expected.json and the taxonomy in validate_run.py disagree")

    def test_no_family_is_listed_in_two_states(self):
        fams = EXPECTED["inventory_families"]
        total = len(fams["measured"]) + len(fams["absent"]) + len(fams["unmeasured"])
        self.assertEqual(total, len(FAMILIES))


class TestModes(unittest.TestCase):
    def test_a_declared_mode_resolves_nowhere(self):
        """This is what forces mode-completeness to blocked."""
        declared = set(json.loads(read("theme.config.json"))["modes"])
        resolved = set(EXPECTED["discovery"]["resolved_modes"])
        self.assertTrue(declared - resolved)
        self.assertEqual(EXPECTED["vitals"]["mode-completeness"], "blocked")

    def test_the_resolving_modes_have_real_blocks(self):
        globals_css = read("app/globals.css")
        self.assertIn(":root {", globals_css)
        self.assertIn(".dark {", globals_css)


class TestLeakDecoys(unittest.TestCase):
    def test_excluded_directories_hold_values_that_would_read_as_leaks(self):
        """Excluding them only proves something if there is something to miss."""
        self.assertIn("#2563eb", read("node_modules/pkg/theme.css"))
        self.assertIn("#2563eb", read("dist/bundle.css"))

    def test_the_generated_file_is_marked_generated(self):
        self.assertIn("sourceMappingURL", read("dist/bundle.css"))

    def test_the_near_miss_is_one_step_from_the_real_token(self):
        self.assertIn("#2563ec", read("components/badge.tsx"))
        self.assertIn("#2563eb", read("app/globals.css"))

    def test_the_repeated_literal_spans_two_files(self):
        self.assertIn("8px", read("components/button.tsx"))
        self.assertIn("8px", read("components/card.tsx"))


if __name__ == "__main__":
    unittest.main()
