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

    def test_commented_imports_do_not_enter_reachability(self):
        root = make_repo({
            "src/main.js": (
                '// import "./line-dead.css";\n'
                '/* import("./block-dead.css"); */\n'
                'import "./live.css";\n'
            ),
            "src/line-dead.css": ":root { --dead-line: red; }",
            "src/block-dead.css": ":root { --dead-block: red; }",
            "src/live.css": (
                '/* @import "./css-dead.css"; */\n'
                ":root { --live: red; }"
            ),
            "src/css-dead.css": ":root { --dead-css: red; }",
        })
        graph = import_graph.build(root, ["src/main.js"])
        self.assertIn("src/live.css", graph["reachable"])
        self.assertNotIn("src/line-dead.css", graph["reachable"])
        self.assertNotIn("src/block-dead.css", graph["reachable"])
        self.assertNotIn("src/css-dead.css", graph["reachable"])

    def test_export_text_cannot_consume_a_later_quoted_sentence(self):
        records = import_graph.import_records_in(
            "src/helpers.js",
            "export function registerUnbound() {}\n"
            "const message = `export helper from 'discourse/helpers/${name}.js'`;\n",
        )
        self.assertEqual(records, [])

    def test_multiline_literal_import_is_not_also_dynamic(self):
        records = import_graph.import_records_in(
            "src/editor.js", 'const editor = import(\n  "./editor.js"\n);')
        self.assertEqual(records, [{"spec": "./editor.js", "kind": "import"}])

    def test_dynamic_import_examples_inside_strings_are_ignored(self):
        records = import_graph.import_records_in(
            "src/example.js",
            "const quoted = 'import(\"./fake.css\")';\n"
            "const template = `require('./also-fake.css')`;\n",
        )
        self.assertEqual(records, [])

    def test_static_export_example_inside_multiline_template_is_ignored(self):
        records = import_graph.import_records_in(
            "src/example.js",
            "const docs = `\nexport { x } from \"./fake.js\";\n`;\n",
        )
        self.assertEqual(records, [])

    def test_js_graph_follows_component_before_css_module(self):
        root = make_repo({
            "src/main.tsx": 'import { Button } from "./Button";',
            "src/Button.tsx": 'import "./Button.module.css"; export const Button = 1;',
            "src/Button.module.css": ".button { color: var(--brand); }",
        })
        g = import_graph.build(root, ["src/main.tsx"])
        self.assertIn("src/Button.tsx", g["reachable"])
        self.assertIn("src/Button.module.css", g["reachable"])

    def test_html_entry_reaches_root_relative_script_and_css(self):
        root = make_repo({
            "index.html": '<link rel="stylesheet" href="/src/base.css"><script type="module" src="/src/main.ts"></script>',
            "src/main.ts": 'import "./feature.css";',
            "src/base.css": ":root { --base: red; }",
            "src/feature.css": ".x { color: var(--base); }",
        })
        g = import_graph.build(root, ["index.html"])
        self.assertIn("src/main.ts", g["reachable"])
        self.assertIn("src/base.css", g["reachable"])
        self.assertIn("src/feature.css", g["reachable"])

    def test_html_ignores_non_style_link_assets(self):
        root = make_repo({
            "index.html": (
                '<link rel="icon" href="/favicon.ico">'
                '<link rel="preload" as="font" href="/font.woff2">'
            ),
        })
        g = import_graph.build(root, ["index.html"])
        self.assertEqual(g["unresolved"], [])

    def test_angular_style_urls_follows_every_array_entry(self):
        root = make_repo({
            "src/card.ts": (
                "@Component({ styleUrls: ['./base.css', './theme.scss'] })"
            ),
            "src/base.css": ".card {}",
            "src/theme.scss": "$gap: 1rem;",
        })
        g = import_graph.build(root, ["src/card.ts"])
        self.assertIn("src/base.css", g["reachable"])
        self.assertIn("src/theme.scss", g["reachable"])

    def test_tsconfig_alias_is_resolved(self):
        root = make_repo({
            "tsconfig.json": '{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}',
            "src/main.ts": 'import "@/theme.css";',
            "src/theme.css": ":root { --brand: red; }",
        })
        g = import_graph.build(root, ["src/main.ts"])
        self.assertIn("src/theme.css", g["reachable"])
        self.assertEqual(g["unresolved"], [])

    def test_aliases_are_scoped_to_each_embedded_application(self):
        root = make_repo({
            "apps/a/app/layout.tsx": 'import "@/theme.css";',
            "apps/a/src/theme.css": ":root { --a: red; }",
            "apps/b/app/layout.tsx": 'import "@/theme.css";',
            "apps/b/src/theme.css": ":root { --b: blue; }",
        })
        graph = import_graph.build(
            root,
            ["apps/a/app/layout.tsx", "apps/b/app/layout.tsx"],
            alias_contexts={
                "apps/a": {"@/*": "apps/a/src/*"},
                "apps/b": {"@/*": "apps/b/src/*"},
            },
        )
        self.assertIn("apps/a/src/theme.css", graph["reachable"])
        self.assertIn("apps/b/src/theme.css", graph["reachable"])
        self.assertEqual(graph["unresolved"], [])

    def test_jsonc_alias_with_comments_and_trailing_commas_is_resolved(self):
        root = make_repo({
            "jsconfig.json": (
                '{\n  // application aliases\n  "compilerOptions": {\n'
                '    "baseUrl": ".",\n    "paths": {\n'
                '      "discourse/*": ["app/*"],\n    },\n  },\n}\n'
            ),
            "src/main.ts": 'import "discourse/theme.css";',
            "app/theme.css": ":root { --brand: red; }",
        })
        graph = import_graph.build(root, ["src/main.ts"])
        self.assertIn("app/theme.css", graph["reachable"])
        self.assertEqual(graph["unresolved"], [])

    def test_wildcard_alias_does_not_capture_bare_workspace_package(self):
        root = make_repo({
            "pnpm-workspace.yaml": "packages:\n  - 'packages/*'\n",
            "jsconfig.json": (
                '{"compilerOptions":{"paths":'
                '{"truth-helpers/*":["packages/truth-helpers/addon/*"]}}}'
            ),
            "src/main.js": 'import "truth-helpers";',
            "packages/truth-helpers/package.json": '{"name":"truth-helpers"}',
            "packages/truth-helpers/src/index.js": "export {};",
        })
        graph = import_graph.build(root, ["src/main.js"])
        self.assertIn("packages/truth-helpers/src/index.js", graph["reachable"])

    def test_js_alias_does_not_redirect_sass_import(self):
        root = make_repo({
            "jsconfig.json": (
                '{"compilerOptions":{"paths":'
                '{"admin/*":["app/assets/javascripts/admin/*"]}}}'
            ),
            "app/assets/stylesheets/application.scss": '@import "admin/base";',
            "app/assets/stylesheets/admin/_base.scss": "$space: 4px;",
        })
        graph = import_graph.build(
            root, ["app/assets/stylesheets/application.scss"])
        self.assertIn("app/assets/stylesheets/admin/_base.scss",
                      graph["reachable"])

    def test_profile_rewrite_resolves_dynamic_framework_namespace(self):
        root = make_repo({
            "src/main.js": (
                'import "discourse/plugins/acme/discourse/components/card";'
            ),
            "plugins/acme/assets/javascripts/discourse/components/card.js": (
                "export {};"
            ),
        })
        graph = import_graph.build(root, ["src/main.js"], rewrites=[{
            "regex": r"^discourse/plugins/(?P<plugin>[^/]+)/(?P<rest>.+)$",
            "replacement": "plugins/{plugin}/assets/javascripts/{rest}",
        }])
        self.assertIn(
            "plugins/acme/assets/javascripts/discourse/components/card.js",
            graph["reachable"],
        )

    def test_conflicting_profile_rewrites_block_resolution(self):
        root = make_repo({
            "src/main.js": 'import "virtual";',
            "src/a.js": "export {};", "src/b.js": "export {};",
        })
        graph = import_graph.build(root, ["src/main.js"], rewrites=[
            {"regex": "^virtual$", "replacement": "src/a.js", "profile": "a"},
            {"regex": "^virtual$", "replacement": "src/b.js", "profile": "b"},
        ])
        self.assertNotIn("src/a.js", graph["reachable"])
        self.assertNotIn("src/b.js", graph["reachable"])
        self.assertEqual(
            graph["unresolved"][0]["reason"], "ambiguous profile rewrite")

    def test_dynamic_expression_is_classified(self):
        root = make_repo({"src/main.ts": "const page = import(`./${name}.css`);"})
        g = import_graph.build(root, ["src/main.ts"])
        self.assertEqual(g["unresolved"][0]["reason"], "dynamic runtime import")

    def test_sprockets_require_tree_reaches_styles(self):
        root = make_repo({
            "app/assets/stylesheets/application.css": "/*\n *= require_tree ./components\n */",
            "app/assets/stylesheets/components/card.css": ".card {}",
        })
        g = import_graph.build(root, ["app/assets/stylesheets/application.css"])
        self.assertIn("app/assets/stylesheets/components/card.css", g["reachable"])

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

    def test_nested_vendor_source_can_be_reached(self):
        root = make_repo({
            "app/globals.scss": '@import "assets/stylesheets/vendor/normalize";',
            "app/assets/stylesheets/vendor/_normalize.scss": "html { line-height: 1; }",
            "vendor/gem/theme.scss": "$external: true;",
        })
        g = import_graph.build(root, ["app/globals.scss"])
        self.assertIn("app/assets/stylesheets/vendor/_normalize.scss", g["reachable"])
        self.assertNotIn("vendor/gem/theme.scss", g["orphans"])

    def test_orphans_exclude_tests_and_respect_owned_patterns(self):
        root = make_repo({
            "app/globals.css": ":root { --live: 1; }",
            "app/owned-stray.css": ":root { --owned: 1; }",
            "plugins/upstream/stray.css": ":root { --upstream: 1; }",
            "spec/fixtures/stray.css": ":root { --fixture: 1; }",
        })
        g = import_graph.build(
            root, ["app/globals.css"], orphan_patterns=["app/**"]
        )
        self.assertEqual(g["orphans"], ["app/owned-stray.css"])

    def test_missing_entry_point_is_reported(self):
        root = make_repo({"app/globals.css": ":root{--a:1px}"})
        g = import_graph.build(root, ["app/nope.css"])
        self.assertEqual(g["reachable"], {})
        self.assertEqual(g["unresolved"][0]["reason"], "entry point does not exist")

    def test_explicit_empty_entries_do_not_auto_detect(self):
        root = make_repo({"app/globals.css": ":root{--a:1px}"})
        g = import_graph.build(root, [])
        self.assertEqual(g["roots"], [])
        self.assertEqual(g["reachable"], {})

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


class TestWorkspaceLinks(unittest.TestCase):
    """A monorepo imports its own packages by name, and the file lives under src/."""

    def make_workspace(self):
        return make_repo({
            "pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
            "packages/shadcn/package.json": '{"name": "shadcn"}',
            "packages/shadcn/src/tailwind.css": ":root{--a:1px}",
            # a scoped package lives at packages/tokens; the scope is in its name
            "packages/tokens/package.json": '{"name": "@org/tokens"}',
            "packages/tokens/src/index.css": ":root{--b:1px}",
            "apps/web/app/globals.css": '@import "shadcn/tailwind.css";\n@import "@org/tokens";',
        })

    def test_workspace_packages_are_discovered_from_pnpm_workspace(self):
        root = self.make_workspace()
        pk = import_graph.workspace_packages(root)
        self.assertEqual(pk.get("shadcn"), "packages/shadcn")
        self.assertEqual(pk.get("@org/tokens"), "packages/tokens")

    def test_bare_package_spec_resolves_into_src(self):
        root = self.make_workspace()
        g = import_graph.build(root, ["apps/web/app/globals.css"])
        self.assertIn("packages/shadcn/src/tailwind.css", g["reachable"])

    def test_scoped_package_spec_resolves_into_src_index(self):
        root = self.make_workspace()
        g = import_graph.build(root, ["apps/web/app/globals.css"])
        self.assertIn("packages/tokens/src/index.css", g["reachable"])

    def test_workspace_file_is_no_longer_an_orphan(self):
        root = self.make_workspace()
        g = import_graph.build(root, ["apps/web/app/globals.css"])
        self.assertNotIn("packages/shadcn/src/tailwind.css", g["orphans"])
        self.assertEqual(g["unresolved"], [])

    def test_package_json_workspaces_field_also_counts(self):
        root = make_repo({
            "package.json": '{"workspaces": ["libs/*"]}',
            "libs/theme/package.json": '{"name": "theme"}',
            "libs/theme/theme.css": ":root{--a:1px}",
            "src/index.css": '@import "theme/theme.css";',
        })
        g = import_graph.build(root, ["src/index.css"])
        self.assertIn("libs/theme/theme.css", g["reachable"])

    def test_split_package_spec(self):
        self.assertEqual(import_graph.split_package_spec("shadcn/tailwind.css"), ("shadcn", "tailwind.css"))
        self.assertEqual(import_graph.split_package_spec("@org/pkg/a/b.css"), ("@org/pkg", "a/b.css"))
        self.assertEqual(import_graph.split_package_spec("@org/pkg"), ("@org/pkg", ""))
        self.assertEqual(import_graph.split_package_spec("plain"), ("plain", ""))

    def test_a_package_that_is_not_in_the_workspace_stays_unresolved(self):
        """node_modules packages must not be guessed at."""
        root = make_repo({
            "pnpm-workspace.yaml": 'packages:\n  - "packages/*"\n',
            "src/index.css": '@import "tailwindcss";',
        })
        g = import_graph.build(root, ["src/index.css"])
        self.assertEqual([u["spec"] for u in g["unresolved"]], ["tailwindcss"])


if __name__ == "__main__":
    unittest.main()
