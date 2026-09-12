"""Tests for resolving Tailwind utility classes back to canonical tokens."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tailwind_adapter  # noqa: E402

EXCERPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fixtures", "tailwind", "theme-4.2.1-excerpt.css",
)


class TestThemeMap(unittest.TestCase):
    def test_multi_word_namespaces_survive_the_split(self):
        # Splitting on the first dash buckets --drop-shadow-md under "drop"
        # and --font-weight-bold under "font". Both are wrong, and both are
        # silent: the key still parses and still resolves to something.
        theme = tailwind_adapter.parse_theme(
            "@theme {\n"
            "  --drop-shadow-md: 0 3px 3px #0003;\n"
            "  --font-weight-bold: 700;\n"
            "  --font-sans: Geist, sans-serif;\n"
            "}\n"
        )
        self.assertEqual(sorted(theme), ["drop-shadow", "font", "font-weight"])
        self.assertEqual(list(theme["drop-shadow"]), ["md"])
        self.assertEqual(list(theme["font-weight"]), ["bold"])
        self.assertEqual(list(theme["font"]), ["sans"])

    def test_a_derived_root_is_its_own_key(self):
        theme = tailwind_adapter.parse_theme("@theme {\n  --spacing: 0.25rem;\n}\n")
        self.assertEqual(theme["spacing"], {"": "0.25rem"})

    def test_project_theme_wins_over_the_default_theme(self):
        merged = tailwind_adapter.theme_map(
            "@theme {\n  --color-red-500: #ff0000;\n}\n",
            "@theme default {\n  --color-red-500: #ef4444;\n  --color-blue-500: #3b82f6;\n}\n",
        )
        self.assertEqual(merged["color"]["red-500"], "#ff0000")
        self.assertEqual(merged["color"]["blue-500"], "#3b82f6")

    def test_coverage_separates_not_covered_from_not_a_utility_namespace(self):
        # Collapsing these two would make the report permanently and falsely
        # incomplete: --breakpoint-* can never be covered, because it
        # generates variants rather than classes.
        theme = tailwind_adapter.parse_theme(
            "@theme {\n"
            "  --color-brand: #123456;\n"
            "  --breakpoint-md: 48rem;\n"
            "  --wibble-thing: 2px;\n"
            "}\n"
        )
        coverage = tailwind_adapter.namespace_coverage(theme)
        self.assertIn("color", coverage["covered"])
        self.assertIn("breakpoint", coverage["non_utility"])
        self.assertNotIn("breakpoint", coverage["uncovered"])
        self.assertIn("wibble", coverage["uncovered"])

    def test_the_table_accounts_for_every_namespace_in_a_real_default_theme(self):
        # Two directions on purpose. Containment alone catches an invented
        # namespace but not a deleted one, and a deleted one is the bug that
        # already shipped here once.
        with open(EXCERPT, encoding="utf-8") as handle:
            real = tailwind_adapter.parse_theme(handle.read())
        named = set()
        for namespaces in tailwind_adapter.UTILITY_PREFIXES.values():
            named.update(namespaces)
        expected = (set(real)
                    - set(tailwind_adapter.NON_UTILITY_NAMESPACES)
                    - tailwind_adapter.TABLE_GAPS)
        self.assertEqual(named, expected)

    def test_no_two_prefixes_resolve_the_same_key_to_the_same_concept(self):
        # Variety, not presence: a table whose entries all collapsed onto one
        # namespace would satisfy every other test in this class.
        concepts = {
            prefix: tailwind_adapter.concept_id(namespaces[0], "x")
            for prefix, namespaces in tailwind_adapter.UTILITY_PREFIXES.items()
        }
        self.assertGreater(len(set(concepts.values())), 1)

    def test_a_namespace_the_table_never_heard_of_is_declared_not_dropped(self):
        # Silently dropping it would make an unknown namespace indistinguishable
        # from one that was never declared.
        theme = tailwind_adapter.parse_theme(
            "@theme {\n  --wibble-thing: 2px;\n}\n")
        self.assertEqual(theme["wibble"], {"thing": "2px"})


class TestResolve(unittest.TestCase):
    def theme(self):
        return tailwind_adapter.theme_map(
            "@theme {\n"
            "  --color-muted: #eee;\n"
            "  --color-brand: #123456;\n"
            "  --text-brand: 2rem;\n"
            "  --spacing: 0.25rem;\n"
            "  --spacing-lg: 2rem;\n"
            "  --radius-md: 6px;\n"
            "}\n"
        )

    def test_variants_modifiers_and_important_all_peel_to_the_same_base(self):
        theme = self.theme()
        spellings = [
            "bg-muted", "dark:bg-muted", "dark:hover:bg-muted", "md:bg-muted",
            "group-hover:bg-muted", "bg-muted/50", "!bg-muted", "bg-muted!",
            "supports-[display:grid]:bg-muted",
        ]
        results = {s: tailwind_adapter.resolve(s, theme) for s in spellings}
        for spelling, result in results.items():
            self.assertEqual(result.concept, "color-muted", spelling)

    def test_an_ambiguous_prefix_resolves_to_nothing_and_names_both(self):
        # text- draws from --color-* and --text-*. Guessing here attributes a
        # reference to the wrong family, which is worse than not counting it,
        # because it looks like a measurement.
        result = tailwind_adapter.resolve("text-brand", self.theme())
        self.assertEqual(result.state, "ambiguous")
        self.assertIsNone(result.concept)
        self.assertEqual(result.candidates, ("color-brand", "text-brand"))
        self.assertNotEqual(result.concept, result.candidates[0])

    def test_a_derived_step_and_a_named_step_land_differently(self):
        # Variety, not presence: both resolve, and they must not be the same
        # kind of thing, or a derived step would inflate named adoption.
        theme = self.theme()
        derived = tailwind_adapter.resolve("p-4", theme)
        named = tailwind_adapter.resolve("p-lg", theme)
        self.assertEqual(derived.concept, "spacing")
        self.assertTrue(derived.derived)
        self.assertEqual(named.concept, "spacing-lg")
        self.assertFalse(named.derived)
        self.assertNotEqual(derived.concept, named.concept)

    def test_a_key_the_theme_never_declared_resolves_to_nothing(self):
        result = tailwind_adapter.resolve("bg-nonexistent", self.theme())
        self.assertEqual(result.state, "unresolved")
        self.assertIsNone(result.concept)

    def test_an_unknown_prefix_resolves_to_nothing(self):
        result = tailwind_adapter.resolve("scroll-mt-md", self.theme())
        self.assertEqual(result.state, "unresolved")

    def test_no_two_distinct_classes_collapse_onto_one_concept(self):
        theme = self.theme()
        classes = ["bg-muted", "bg-brand", "rounded-md", "p-lg"]
        concepts = [tailwind_adapter.resolve(c, theme).concept for c in classes]
        self.assertEqual(len(set(concepts)), len(classes))

    def test_a_negative_utility_names_the_same_token_as_its_positive(self):
        # -mt-4 and mt-4 spend the same spacing token; the sign changes the
        # value, never which token was referenced.
        theme = self.theme()
        negative = tailwind_adapter.resolve("-mt-4", theme)
        positive = tailwind_adapter.resolve("mt-4", theme)
        self.assertEqual(negative.concept, positive.concept)
        self.assertEqual(negative.concept, "spacing")
        self.assertTrue(negative.derived)
        self.assertEqual(tailwind_adapter.peel("-mt-4"), ("mt-4", True))
        self.assertEqual(tailwind_adapter.peel("mt-4"), ("mt-4", False))
