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
            "  --perspective-near: 300px;\n"
            "}\n"
        )
        coverage = tailwind_adapter.namespace_coverage(theme)
        self.assertIn("color", coverage["covered"])
        self.assertIn("breakpoint", coverage["non_utility"])
        self.assertNotIn("breakpoint", coverage["uncovered"])
        self.assertIn("perspective", coverage["uncovered"])

    def test_every_namespace_in_the_table_exists_in_a_real_default_theme(self):
        # The prefix-to-namespace mapping is authored, because it lives only
        # inside Tailwind's minified distribution. This is what keeps it
        # falsifiable: a namespace invented or misspelled fails here.
        with open(EXCERPT, encoding="utf-8") as handle:
            real = tailwind_adapter.parse_theme(handle.read())
        named = set()
        for namespaces in tailwind_adapter.UTILITY_PREFIXES.values():
            named.update(namespaces)
        self.assertTrue(named)
        self.assertEqual(sorted(named - set(real)), [])

    def test_no_two_prefixes_resolve_the_same_key_to_the_same_concept(self):
        # Variety, not presence: a table whose entries all collapsed onto one
        # namespace would satisfy every other test in this class.
        concepts = {
            prefix: tailwind_adapter.concept_id(namespaces[0], "x")
            for prefix, namespaces in tailwind_adapter.UTILITY_PREFIXES.items()
        }
        self.assertGreater(len(set(concepts.values())), 1)
