"""Behavior tests for universal environment discovery."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover_environment  # noqa: E402
import discover_tokens  # noqa: E402


def make_repo(files):
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    return root


class TestDiscovery(unittest.TestCase):
    def test_discourse_is_layered_and_reads_plugin_registration(self):
        root = make_repo({
            "Gemfile": "gem 'rails'",
            "app/assets/stylesheets/common.scss": '@import "color_definitions";',
            "app/assets/stylesheets/color_definitions.scss": "$x: schemeType();",
            "app/assets/stylesheets/common/foundation/variables.scss": "// injected into every theme CSS file\n$z-layers: (\"base\": 1);",
            "app/assets/stylesheets/admin.scss": "body {}",
            "plugins/acme/plugin.rb": 'register_asset "stylesheets/common.scss"\n',
            "plugins/acme/assets/stylesheets/common.scss": "body {}",
        })
        result = discover_environment.discover(
            root, ["app/assets/stylesheets/**", "plugins/acme"])
        self.assertEqual(result["environment"], ["discourse", "rails-sprockets"])
        plugin = next(r for r in result["roots"] if r["path"].startswith("plugins/acme"))
        self.assertEqual(plugin["confidence"], "framework-registered")
        self.assertEqual(plugin["ownership"], "owned")
        self.assertIn(":1", plugin["detected_by"])
        self.assertIn(plugin["path"], result["owned_import_graph"]["reachable"])
        self.assertTrue(any(r["root_type"] == "theme" for r in result["roots"]))
        self.assertTrue(any(r["root_type"] == "admin" for r in result["roots"]))
        self.assertIn("app/assets/stylesheets/common/foundation/variables.scss",
                      result["owned_import_graph"]["reachable"])

    def test_commented_discourse_registration_is_not_a_root(self):
        root = make_repo({
            "app/assets/stylesheets/common.scss": "body {}",
            "app/assets/stylesheets/color_definitions.scss": "$x: schemeType();",
            "plugins/acme/plugin.rb": (
                '# register_asset "stylesheets/retired.scss"\n'
                'register_asset "stylesheets/current.scss"\n'
            ),
            "plugins/acme/assets/stylesheets/retired.scss": "body {}",
            "plugins/acme/assets/stylesheets/current.scss": "body {}",
        })
        result = discover_environment.discover(root, ["plugins/acme"])
        paths = {item["path"] for item in result["roots"]}
        self.assertIn("plugins/acme/assets/stylesheets/current.scss", paths)
        self.assertNotIn("plugins/acme/assets/stylesheets/retired.scss", paths)

    def test_missing_registered_root_blocks_production_completeness(self):
        root = make_repo({
            "app/assets/stylesheets/common.scss": "body {}",
            "app/assets/stylesheets/color_definitions.scss": "$x: schemeType();",
            "plugins/acme/plugin.rb": 'register_asset "stylesheets/missing.scss"\n',
        })
        result = discover_environment.discover(root, ["plugins/acme"])
        self.assertEqual(result["capabilities"]["production_roots"], "blocked")
        self.assertEqual(
            result["missing_registered_roots"][0]["path"],
            "plugins/acme/assets/stylesheets/missing.scss",
        )
        step = next(
            item for item in result["capability_ladder"]["steps"]
            if item["capability"] == "production_roots"
        )
        self.assertIn("missing from disk", step["limitation"])

    def test_reachable_composed_route_is_not_retained_as_supplemental(self):
        root = make_repo({
            "app/assets/stylesheets/common.scss": "body {}",
            "app/assets/stylesheets/color_definitions.scss": "$x: schemeType();",
            "plugins/.keep": "",
            "app/assets/javascripts/discourse/.ember-cli": "{}",
            "app/assets/javascripts/discourse/app/app.js": (
                'import "./routes/discourse";\n'
            ),
            "app/assets/javascripts/discourse/app/routes/discourse.js": (
                "export default class DiscourseRoute {}\n"
            ),
        })
        result = discover_environment.discover(root)
        route = "app/assets/javascripts/discourse/app/routes/discourse.js"
        self.assertIn(route, result["import_graph"]["reachable"])
        self.assertNotIn(route, {
            item["path"] for item in result["surface_roots"]
        })
        self.assertIn(
            "app/assets/javascripts/discourse",
            {item["path"] for item in
             result["profile_composition"]["application_candidates"]},
        )

    def test_next_and_monorepo_are_simultaneous_layers(self):
        root = make_repo({
            "next.config.mjs": "export default {}",
            "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
            "app/globals.css": ":root { --x: 1px; }",
        })
        result = discover_environment.discover(root)
        self.assertEqual(result["environment"], ["nextjs", "monorepo"])
        self.assertEqual(result["profile_composition"]["order"],
                         ["nextjs", "monorepo"])
        self.assertEqual(
            [step["capability"] for step in result["capability_ladder"]["steps"]],
            result["capability_ladder"]["order"],
        )

    def test_storybook_stays_out_of_product_roots(self):
        root = make_repo({
            ".storybook/preview.ts": 'import "./preview.css";',
            ".storybook/preview.css": ":root { --story: red; }",
        })
        result = discover_environment.discover(root)
        self.assertEqual(result["environment"], ["storybook"])
        self.assertEqual(result["roots"], [])
        self.assertTrue(result["surface_roots"])
        self.assertEqual(result["capabilities"]["production_roots"], "blocked")

    def test_monorepo_with_multiple_apps_requires_selection(self):
        root = make_repo({
            "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
            "apps/web/package.json": '{"name":"web"}',
            "apps/web/next.config.mjs": "export default {};",
            "apps/web/app/layout.tsx": 'import "./globals.css";',
            "apps/web/app/globals.css": ":root { --web: red; }",
            "apps/admin/package.json": '{"name":"admin"}',
            "apps/admin/vite.config.ts": "export default {};",
            "apps/admin/index.html": '<script type="module" src="/src/main.ts"></script>',
            "apps/admin/src/main.ts": 'import "./main.css";',
            "apps/admin/src/main.css": ":root { --admin: blue; }",
        })
        blocked = discover_environment.discover(root)
        self.assertEqual(
            blocked["profile_composition"]["application_selection"]["state"],
            "blocked",
        )
        self.assertEqual(blocked["capabilities"]["production_roots"], "blocked")
        self.assertEqual(blocked["capabilities"]["import_resolution"], "blocked")
        self.assertEqual(blocked["import_graph"]["reachable"], {})

        selected = discover_environment.discover(root, app_root="apps/web")
        self.assertEqual(selected["environment"], ["nextjs", "monorepo"])
        self.assertEqual(
            selected["profile_composition"]["application_selection"]["selected"],
            "apps/web",
        )
        self.assertIn("apps/web/app/globals.css",
                      selected["owned_import_graph"]["reachable"])

    def test_selected_application_cannot_escape_repository(self):
        root = make_repo({"pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n"})
        with self.assertRaisesRegex(ValueError, "escapes repository"):
            discover_environment.discover(root, app_root="../sibling")

    def test_shared_workspace_packages_are_not_application_candidates(self):
        root = make_repo({
            "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n  - 'packages/*'\n",
            "apps/web/package.json": '{"name":"web"}',
            "apps/web/next.config.mjs": "export default {};",
            "apps/web/app/layout.tsx": 'import "./globals.css";',
            "apps/web/app/globals.css": ":root { --web: red; }",
            "packages/utils/package.json": '{"name":"utils"}',
            "packages/utils/src/index.ts": "export const value = 1;",
        })
        result = discover_environment.discover(root)
        composition = result["profile_composition"]
        self.assertEqual(composition["application_selection"]["state"],
                         "auto-selected")
        self.assertEqual(composition["application_selection"]["selected"],
                         "apps/web")
        self.assertEqual([item["path"] for item in
                          composition["application_candidates"]], ["apps/web"])

    def test_root_build_config_without_registered_entry_does_not_bypass_app_selection(self):
        root = make_repo({
            "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
            "vite.config.ts": "export default {};",
            "apps/a/package.json": '{"name":"a"}',
            "apps/a/next.config.mjs": "export default {};",
            "apps/a/tsconfig.json": (
                '{"compilerOptions":{"paths":{"@/*":["src/*"]}}}'
            ),
            "apps/a/app/layout.tsx": (
                'import "@/theme.css"; export default function Layout() {}'
            ),
            "apps/a/src/theme.css": ":root { --a: red; }",
            "apps/b/package.json": '{"name":"b"}',
            "apps/b/next.config.mjs": "export default {};",
            "apps/b/tsconfig.json": (
                '{"compilerOptions":{"paths":{"@/*":["src/*"]}}}'
            ),
            "apps/b/app/layout.tsx": (
                'import "@/theme.css"; export default function Layout() {}'
            ),
            "apps/b/src/theme.css": ":root { --b: blue; }",
        })
        result = discover_environment.discover(root)
        self.assertEqual(
            result["profile_composition"]["application_selection"]["state"],
            "blocked",
        )

    def test_static_next_stylesheet_is_not_its_own_reachability_proof(self):
        root = make_repo({
            "next.config.mjs": "export default {};",
            "app/layout.tsx": "export default function Layout() {}",
            "app/globals.css": ":root { --unused: red; }",
        })
        result = discover_environment.discover(root)
        self.assertNotIn("app/globals.css", result["import_graph"]["reachable"])
        self.assertIn("app/globals.css",
                      {item["path"] for item in result["root_candidates"]})

    def test_static_vite_entry_requires_html_import(self):
        root = make_repo({
            "vite.config.ts": "export default {};",
            "index.html": "<main></main>",
            "src/main.ts": 'import "./main.css";',
            "src/main.css": ":root { --unused: red; }",
        })
        result = discover_environment.discover(root)
        self.assertNotIn("src/main.ts", result["import_graph"]["reachable"])
        self.assertIn("src/main.ts",
                      {item["path"] for item in result["root_candidates"]})

    def test_embedded_framework_layer_composes_with_root_framework(self):
        root = make_repo({
            "Gemfile": "gem 'rails'",
            "pnpm-workspace.yaml": (
                "packages:\n  - 'app/assets/javascripts/*'\n"
            ),
            "app/assets/stylesheets/common.scss": "body {}",
            "app/assets/stylesheets/color_definitions.scss": "$x: schemeType();",
            "plugins/placeholder/plugin.rb": "# plugin",
            "app/assets/javascripts/discourse/package.json": '{"name":"discourse"}',
            "app/assets/javascripts/discourse/ember-cli-build.js": "module.exports = {};",
            "app/assets/javascripts/discourse/app/app.js": "export default class App {}",
            "app/assets/javascripts/discourse/app/styles/app.scss": "body {}",
        })
        result = discover_environment.discover(root)
        self.assertIn("discourse", result["environment"])
        self.assertIn("ember", result["environment"])
        self.assertEqual(
            [item["path"] for item in
             result["profile_composition"]["embedded_applications"]],
            ["app/assets/javascripts/discourse"],
        )

    def test_nuxt_configured_styles_are_registered_roots(self):
        root = make_repo({
            "nuxt.config.ts": (
                "export default defineNuxtConfig({ "
                "css: ['~/assets/css/main.css', './assets/css/theme.scss'] })"
            ),
            "app.vue": "<template><main /></template>",
            "assets/css/main.css": ":root { --brand: red; }",
            "assets/css/theme.scss": "$space: 4px;",
        })
        result = discover_environment.discover(root)
        roots = {item["path"]: item for item in result["roots"]}
        self.assertEqual(
            roots["assets/css/main.css"]["confidence"],
            "framework-registered",
        )
        self.assertIn("assets/css/theme.scss", roots)

    def test_angular_reads_every_registered_style_entry(self):
        root = make_repo({
            "angular.json": json.dumps({"projects": {"web": {"architect": {
                "build": {"options": {
                    "main": "src/main.ts",
                    "styles": ["src/base.css", {"input": "src/theme.scss"}],
                }},
                "test": {"options": {"styles": ["src/test-only.css"]}},
            }}}}),
            "src/main.ts": "export {};",
            "src/base.css": ":root { --brand: red; }",
            "src/theme.scss": "$space: 4px;",
            "src/test-only.css": ":root { --test-only: red; }",
        })
        result = discover_environment.discover(root)
        paths = {item["path"] for item in result["roots"]}
        self.assertTrue({"src/main.ts", "src/base.css", "src/theme.scss"} <= paths)
        self.assertNotIn("src/test-only.css", paths)

    def test_ember_cli_build_import_is_a_registered_style_root(self):
        root = make_repo({
            "ember-cli-build.js": (
                "module.exports = function(defaults) { const app = {}; "
                "app.import('app/styles/brand.css'); return app; };"
            ),
            "app/app.js": "export default class App {}",
            "app/styles/brand.css": ":root { --brand: red; }",
        })
        result = discover_environment.discover(root)
        imported = next(
            item for item in result["roots"]
            if item["path"] == "app/styles/brand.css"
        )
        self.assertEqual(imported["confidence"], "framework-registered")
        self.assertIn("app.import", imported["evidence"])

    def test_astro_remix_and_react_scripts_have_reachable_framework_roots(self):
        cases = [
            ({
                "astro.config.mjs": "export default {};",
                "src/pages/index.astro": "<style>:root{--x:red}</style>",
            }, "astro", "src/pages/index.astro"),
            ({
                "vite.config.ts": "export default {};",
                "package.json": '{"dependencies":{"@remix-run/react":"1"},'
                                '"devDependencies":{"@remix-run/dev":"1"}}',
                "app/root.tsx": "export default function Root() {}",
            }, "remix", "app/root.tsx"),
            ({
                "package.json": '{"dependencies":{"react-scripts":"5"}}',
                "src/index.tsx": "export {};",
            }, "react-scripts", "src/index.tsx"),
        ]
        for files, profile, root_path in cases:
            with self.subTest(profile=profile):
                result = discover_environment.discover(make_repo(files))
                self.assertIn(profile, result["environment"])
                self.assertIn(root_path, result["import_graph"]["reachable"])

    def test_custom_profile_can_supply_a_declarative_extractor(self):
        root = make_repo({
            "widget.config.js": "export default { styles: ['src/theme.css'] };",
            "src/theme.css": ":root { --brand: red; }",
        })
        profile_path = os.path.join(root, "profiles.json")
        profile = {
            "profiles": [{
                "id": "widget", "kind": "framework", "priority": 95,
                "adapter": "references/environment-adapters.md",
                "detection": {
                    "claim": "Widget app", "confidence": "framework-registered",
                    "required": [{"type": "path_any",
                                  "patterns": ["widget.config.js"]}],
                    "supporting": [], "minimum_supporting": 0,
                },
                "extractors": [{
                    "type": "config_array_roots",
                    "files": ["widget.config.js"], "key": "styles",
                    "confidence": "framework-registered", "ownership": "owned",
                    "evidence": "Widget style registration",
                }],
                "roots": [], "component_roots": [], "surface_roots": [],
                "guidance": {
                    "production_roots": "Read registered entries.",
                    "import_resolution": "Follow imports.",
                    "token_source_discovery": "Inspect themes.",
                    "ownership": "Separate dependencies.",
                    "mode_resolution": "Resolve schemes.",
                    "runtime_verification": "Inspect output.",
                },
            }],
        }
        with open(profile_path, "w", encoding="utf-8") as handle:
            json.dump(profile, handle)
        result = discover_environment.discover(
            root, profile_files=[profile_path])
        self.assertEqual(result["environment"], ["widget"])
        self.assertIn("src/theme.css", result["import_graph"]["reachable"])

    def test_extractor_only_workspace_app_is_auto_selected(self):
        root = make_repo({
            "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
            "apps/widget/package.json": '{"name":"widget"}',
            "apps/widget/widget.config.js": (
                "export default { styles: ['src/theme.css'] };"
            ),
            "apps/widget/src/theme.css": ":root { --brand: red; }",
        })
        profile_path = os.path.join(root, "profiles.json")
        profile = {
            "profiles": [{
                "id": "widget", "kind": "framework", "priority": 95,
                "adapter": "references/environment-adapters.md",
                "detection": {
                    "claim": "Widget app", "confidence": "framework-registered",
                    "required": [{"type": "path_any",
                                  "patterns": ["widget.config.js"]}],
                    "supporting": [], "minimum_supporting": 0,
                },
                "extractors": [{
                    "type": "config_array_roots", "files": ["widget.config.js"],
                    "key": "styles", "confidence": "framework-registered",
                    "ownership": "owned", "evidence": "Widget style: {spec}",
                }],
                "roots": [], "component_roots": [], "surface_roots": [],
                "guidance": {
                    "production_roots": "Read registered entries.",
                    "import_resolution": "Follow imports.",
                    "token_source_discovery": "Inspect themes.",
                    "ownership": "Separate dependencies.",
                    "mode_resolution": "Resolve schemes.",
                    "runtime_verification": "Inspect output.",
                },
            }],
        }
        with open(profile_path, "w", encoding="utf-8") as handle:
            json.dump(profile, handle)
        result = discover_environment.discover(
            root, profile_files=[profile_path])
        self.assertEqual(
            result["profile_composition"]["application_selection"]["selected"],
            "apps/widget",
        )
        self.assertIn("apps/widget/src/theme.css",
                      result["import_graph"]["reachable"])

    def test_repeated_embedded_framework_keeps_every_application_context(self):
        root = make_repo({
            "shell.config.js": "export default {};",
            "shell.html": "<main></main>",
            "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
            "apps/a/package.json": '{"name":"a"}',
            "apps/a/next.config.mjs": "export default {};",
            "apps/a/tsconfig.json": '{"compilerOptions":{"paths":{"@/*":["src/*"]}}}',
            "apps/a/app/layout.tsx": (
                'import "@/theme.css"; export default function Layout() {}'
            ),
            "apps/a/src/theme.css": ":root { --a: red; }",
            "apps/b/package.json": '{"name":"b"}',
            "apps/b/next.config.mjs": "export default {};",
            "apps/b/tsconfig.json": '{"compilerOptions":{"paths":{"@/*":["src/*"]}}}',
            "apps/b/app/layout.tsx": (
                'import "@/theme.css"; export default function Layout() {}'
            ),
            "apps/b/src/theme.css": ":root { --b: blue; }",
        })
        profile_path = os.path.join(root, "profiles.json")
        with open(profile_path, "w", encoding="utf-8") as handle:
            json.dump({"profiles": [{
                "id": "shell", "kind": "framework", "priority": 99,
                "adapter": "references/environment-adapters.md",
                "detection": {
                    "claim": "Shell app", "confidence": "framework-registered",
                    "required": [{"type": "path_any",
                                  "patterns": ["shell.config.js"]}],
                    "supporting": [], "minimum_supporting": 0,
                },
                "embedded_applications": ["apps/*"],
                "roots": [{
                    "patterns": ["shell.html"], "root_type": "common",
                    "confidence": "framework-registered", "ownership": "owned",
                    "evidence": "Shell entry",
                }],
                "component_roots": [], "surface_roots": [],
                "guidance": {
                    "production_roots": "Read shell and embedded entries.",
                    "import_resolution": "Follow imports.",
                    "token_source_discovery": "Inspect themes.",
                    "ownership": "Separate dependencies.",
                    "mode_resolution": "Resolve schemes.",
                    "runtime_verification": "Inspect output.",
                },
            }]}, handle)
        result = discover_environment.discover(
            root, profile_files=[profile_path])
        paths = {item["path"] for item in result["roots"]}
        self.assertIn("apps/a/app/layout.tsx", paths)
        self.assertIn("apps/b/app/layout.tsx", paths)
        self.assertIn("apps/a/src/theme.css", result["import_graph"]["reachable"])
        self.assertIn("apps/b/src/theme.css", result["import_graph"]["reachable"])
        next_profile = next(
            item for item in result["profile_composition"]["active"]
            if item["id"] == "nextjs"
        )
        self.assertEqual(next_profile["contexts"], ["apps/a", "apps/b"])

    def test_capability_contributions_resolve_conflicts_conservatively(self):
        root = make_repo({"app.html": "<main></main>"})
        profile_path = os.path.join(root, "profiles.json")
        guidance = {
            "production_roots": "Read entries.",
            "import_resolution": "Follow imports.",
            "token_source_discovery": "Inspect themes.",
            "ownership": "Separate dependencies.",
            "mode_resolution": "Resolve schemes.",
            "runtime_verification": "Inspect output.",
        }
        profiles = []
        for profile_id, state in (("optimistic", "verified"),
                                  ("cautious", "blocked"),
                                  ("unknown", "unmeasured")):
            profiles.append({
                "id": profile_id, "kind": "framework",
                "priority": 90 if state == "verified" else 80,
                "adapter": "references/environment-adapters.md",
                "detection": {
                    "claim": profile_id, "confidence": "framework-registered",
                    "required": [{"type": "path_any", "patterns": ["app.html"]}],
                    "supporting": [], "minimum_supporting": 0,
                },
                "capability_contributions": {"mode_resolution": {
                    "state": state, "evidence": [profile_id],
                    "limitation": (None if state == "verified" else
                                   "Compiled output is missing."),
                    "next_step": "Inspect output.",
                }},
                "roots": [{
                    "patterns": ["app.html"], "root_type": "common",
                    "confidence": "framework-registered", "ownership": "owned",
                    "evidence": "Application entry",
                }],
                "component_roots": [], "surface_roots": [],
                "guidance": guidance,
            })
        with open(profile_path, "w", encoding="utf-8") as handle:
            json.dump({"profiles": profiles}, handle)
        result = discover_environment.discover(root, profile_files=[profile_path])
        self.assertEqual(result["capabilities"]["mode_resolution"], "blocked")
        self.assertEqual(len(result["profile_composition"]["conflicts"]), 1)
        self.assertEqual(
            result["profile_composition"]["conflicts"][0]["states"],
            ["blocked", "unmeasured", "verified"],
        )
        self.assertEqual(
            result["profile_composition"]["conflicts"][0]["resolution"],
            "most conservative state",
        )

    def test_conflicting_profile_rewrites_block_and_surface_conflict(self):
        root = make_repo({
            "app.html": '<script src="virtual"></script>',
            "src/a.js": "export {};", "src/b.js": "export {};",
        })
        profile_path = os.path.join(root, "profiles.json")
        guidance = {
            "production_roots": "Read entries.",
            "import_resolution": "Follow imports.",
            "token_source_discovery": "Inspect themes.",
            "ownership": "Separate dependencies.",
            "mode_resolution": "Resolve schemes.",
            "runtime_verification": "Inspect output.",
        }
        profiles = []
        for profile_id, destination in (("a", "src/a.js"), ("b", "src/b.js")):
            profiles.append({
                "id": profile_id, "kind": "framework", "priority": 90,
                "adapter": "references/environment-adapters.md",
                "detection": {
                    "claim": profile_id, "confidence": "framework-registered",
                    "required": [{"type": "path_any", "patterns": ["app.html"]}],
                    "supporting": [], "minimum_supporting": 0,
                },
                "import_rewrites": [{
                    "regex": "^virtual$", "replacement": destination,
                }],
                "roots": [{
                    "patterns": ["app.html"], "root_type": "common",
                    "confidence": "framework-registered", "ownership": "owned",
                    "evidence": "Application entry",
                }],
                "component_roots": [], "surface_roots": [],
                "guidance": guidance,
            })
        with open(profile_path, "w", encoding="utf-8") as handle:
            json.dump({"profiles": profiles}, handle)
        result = discover_environment.discover(root, profile_files=[profile_path])
        self.assertEqual(result["capabilities"]["import_resolution"], "blocked")
        conflict = next(
            item for item in result["profile_composition"]["conflicts"]
            if item["capability"] == "import_resolution"
        )
        self.assertEqual(conflict["profiles"], ["a", "b"])
        self.assertIn("ambiguous profile rewrite", conflict["resolution"])

    def test_explicit_owned_scope_excludes_unmatched_framework_roots(self):
        root = make_repo({
            "next.config.mjs": "export default {};",
            "app/layout.tsx": "export default function Layout() {}",
        })
        result = discover_environment.discover(
            root, ["packages/design-system/**"]
        )
        layout = next(item for item in result["roots"]
                      if item["path"] == "app/layout.tsx")
        self.assertEqual(layout["ownership"], "unknown")
        self.assertEqual(result["owned_import_graph"]["reachable"], {})

    def test_owned_graph_seeds_from_conventional_roots_the_graph_proved(self):
        """A framework entry outside the owned scope must not empty the owned graph.

        The registered Vite entry is index.html, at the repository root and so
        outside `src/**`. The owned roots — main.jsx and globals.css — are found
        by convention and only earn `import-graph verified` once the full graph
        has been walked. Seeding the owned graph from the pre-promotion list left
        it with no roots at all, and every tool that reads
        `owned_import_graph.reachable` then measured nothing, silently.
        """
        root = make_repo({
            "package.json": '{"devDependencies": {"vite": "^5.0.0"}}',
            "vite.config.js": "export default {};",
            "index.html": '<script type="module" src="/src/main.jsx"></script>',
            "src/main.jsx": 'import "./globals.css";',
            "src/globals.css": (
                ":root {\n"
                "  --color-brand: #6b65ff;\n"
                "  --color-surface: #ffffff;\n"
                "  --color-text: #242526;\n"
                "  --space-2: 8px;\n"
                "  --radius-md: 12px;\n"
                "}\n"
            ),
        })
        result = discover_environment.discover(root, ["src/**"])
        entry = next(item for item in result["roots"]
                     if item["path"] == "index.html")
        self.assertEqual(entry["ownership"], "unknown")
        self.assertNotEqual(result["owned_import_graph"]["roots"], [])
        self.assertIn("src/globals.css",
                      result["owned_import_graph"]["reachable"])
        self.assertNotIn("index.html",
                         result["owned_import_graph"]["reachable"])
        # The harm was downstream and silent, so assert it there too.
        tokens = discover_tokens.discover(root, result)
        self.assertEqual([item["path"] for item in tokens["sources"]],
                         ["src/globals.css"])
        self.assertEqual(tokens["concept_count"], 5)

    def test_composed_profiles_are_retained_on_a_shared_root(self):
        root = make_repo({
            "next.config.mjs": "export default {};",
            "app/layout.tsx": 'import "./globals.css";',
            "app/globals.css": ":root { --x: 1px; }",
        })
        result = discover_environment.discover(root)
        global_root = next(item for item in result["roots"]
                           if item["path"] == "app/globals.css")
        self.assertEqual(set(global_root["profiles"]), {"nextjs", "convention"})

    def test_unknown_framework_reports_blocked_fallback(self):
        root = make_repo({"styles/main.css": ":root { --x: 1px; }"})
        result = discover_environment.discover(root)
        self.assertEqual(result["environment"], ["unknown"])
        self.assertEqual(result["capabilities"]["production_roots"], "blocked")


if __name__ == "__main__":
    unittest.main()
