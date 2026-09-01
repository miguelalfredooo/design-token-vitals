"""Tests for import_graph.

Reachability decides what gets inventoried, so a wrong answer here silently
changes what the report claims a codebase's token layer is.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_graph  # noqa: E402


def make_repo(files):
    """Write a dict of {relpath: content} into a temp dir, return the root."""
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    return root


class TestCandidatePaths(unittest.TestCase):
    def test_relative_spec_resolves_beside_the_importer(self):
        got = import_graph.candidate_paths("./legacy.css", "apps/v4/app/globals.css")
        self.assertIn("apps/v4/app/legacy.css", got)

    def test_every_candidate_is_repository_relative(self):
        """An absolute path here resolves against the working directory."""
        got = import_graph.candidate_paths("tokens", "src/app.scss")
        self.assertTrue(all(not p.startswith("/") for p in got), got)

    def test_sass_partial_gets_the_underscore_and_extension(self):
        got = import_graph.candidate_paths("tokens", "app/common.scss")
        self.assertIn("app/_tokens.scss", got)
        self.assertIn("app/tokens.scss", got)

    def test_url_and_data_specs_resolve_to_nothing(self):
        for spec in ("https://x.test/a.css", "//cdn/a.css", "data:text/css,a{}"):
            self.assertEqual(import_graph.candidate_paths(spec, "a.css"), [])

    def test_tilde_prefix_is_stripped(self):
        got = import_graph.candidate_paths("~pkg/theme.css", "src/a.css")
        self.assertTrue(any(p.endswith("pkg/theme.css") for p in got), got)


class TestBuild(unittest.TestCase):
    def test_reaches_a_transitive_import(self):
        root = make_repo({
            "app/globals.css": '@import "./base.css";',
            "app/base.css": '@import "./tokens.css";',
            "app/tokens.css": ":root{--a:1px}",
        })
        g = import_graph.build(root, ["app/globals.css"])
        self.assertEqual(set(g["reachable"]), {"app/globals.css", "app/base.css", "app/tokens.css"})
        self.assertEqual(g["reachable"]["app/tokens.css"]["depth"], 2)

    def test_unimported_stylesheet_is_an_orphan(self):
        root = make_repo({
            "app/globals.css": ":root{--a:1px}",
            "app/stray-tokens.css": ":root{--b:2px}",
        })
        g = import_graph.build(root, ["app/globals.css"])
        self.assertEqual(g["orphans"], ["app/stray-tokens.css"])

    def test_scss_use_and_forward_are_followed(self):
        root = make_repo({
            "app/common.scss": '@use "tokens";\n@forward "mixins";',
            "app/_tokens.scss": "$a: 1px;",
            "app/_mixins.scss": "@mixin m {}",
        })
        g = import_graph.build(root, ["app/common.scss"])
        self.assertIn("app/_tokens.scss", g["reachable"])
        self.assertIn("app/_mixins.scss", g["reachable"])

    def test_js_entry_pulls_in_its_stylesheet(self):
        root = make_repo({
            "src/main.tsx": 'import "./index.css";\nexport const a = 1;',
            "src/index.css": ":root{--a:1px}",
        })
        g = import_graph.build(root, ["src/main.tsx"])
        self.assertIn("src/index.css", g["reachable"])

    def test_external_package_spec_is_reported_unresolved(self):
        root = make_repo({"app/globals.css": '@import "tailwindcss";'})
        g = import_graph.build(root, ["app/globals.css"])
        self.assertEqual([u["spec"] for u in g["unresolved"]], ["tailwindcss"])

    def test_a_cycle_terminates(self):
        root = make_repo({
            "a.css": '@import "./b.css";',
            "b.css": '@import "./a.css";',
        })
        g = import_graph.build(root, ["a.css"])
        self.assertEqual(set(g["reachable"]), {"a.css", "b.css"})

    def test_ignored_directories_stay_out(self):
        root = make_repo({
            "app/globals.css": ":root{--a:1px}",
            "node_modules/pkg/theme.css": ":root{--b:2px}",
        })
        g = import_graph.build(root, ["app/globals.css"])
        self.assertNotIn("node_modules/pkg/theme.css", g["orphans"])

    def test_missing_entry_point_is_reported(self):
        root = make_repo({"app/globals.css": ":root{--a:1px}"})
        g = import_graph.build(root, ["app/nope.css"])
        self.assertEqual(g["reachable"], {})
        self.assertEqual(g["unresolved"][0]["reason"], "entry point does not exist")

    def test_detects_conventional_entry_points(self):
        root = make_repo({"app/globals.css": ":root{--a:1px}"})
        g = import_graph.build(root)
        self.assertEqual([r["path"] for r in g["roots"]], ["app/globals.css"])

    def test_discourse_bundle_roots_are_conventions(self):
        root = make_repo({
            "app/assets/stylesheets/common.scss": '@import "tokens";',
            "app/assets/stylesheets/desktop.scss": "body{}",
            "app/assets/stylesheets/mobile.scss": "body{}",
            "app/assets/stylesheets/_tokens.scss": "$a: 1px;",
        })
        g = import_graph.build(root)
        paths = {r["path"] for r in g["roots"]}
        self.assertEqual(paths, {
            "app/assets/stylesheets/common.scss",
            "app/assets/stylesheets/desktop.scss",
            "app/assets/stylesheets/mobile.scss",
        })
        self.assertIn("app/assets/stylesheets/_tokens.scss", g["reachable"])


if __name__ == "__main__":
    unittest.main()
