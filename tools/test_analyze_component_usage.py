"""Tests for framework-neutral component-to-token usage analysis."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analyze_component_usage  # noqa: E402


class TestComponentUsage(unittest.TestCase):
    def repo(self, files, concepts=None, sources=None, owned=None, reachable_paths=None,
             component_roots=None):
        root = tempfile.mkdtemp()
        reachable = {}
        for path, contents in files.items():
            full = os.path.join(root, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(contents)
            if reachable_paths is None or path in reachable_paths:
                reachable[path] = {"via": ["app/main.scss"]}
        discovery = {
            "owned_import_graph": {"reachable": reachable},
            "ownership": {"owned_patterns": owned or []},
            "component_roots": component_roots or [],
        }
        tokens = {
            "concepts": concepts or [
                {"id": "brand-primary", "family": "color"},
                {"id": "space-sm", "family": "spacing"},
            ],
            "sources": sources or [],
        }
        return root, discovery, tokens

    def test_counts_css_and_scss_references_with_locations(self):
        root, discovery, tokens = self.repo({
            "app/assets/stylesheets/components/card.scss": (
                ".card { color: var(--brand-primary); gap: $space-sm; "
                "border-color: var(--brand-primary); }"
            ),
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        card = result["top_20"][0]
        self.assertEqual(card["references"], 3)
        self.assertEqual(card["distinct_tokens"], 2)
        self.assertEqual(card["families"], {"color": 2, "spacing": 1})
        self.assertEqual(card["roadmap_band"], "assess-first")
        self.assertEqual(card["share_of_ranked_references"], 100.0)
        self.assertEqual(result["roadmap"]["ranked_references"], 3)
        syntax_by_token = {item["id"]: item["syntaxes"] for item in card["tokens"]}
        self.assertEqual(syntax_by_token["brand-primary"], ["css-custom-property"])
        self.assertEqual(syntax_by_token["space-sm"], ["scss-variable"])
        self.assertIn("app/assets/stylesheets/components/card.scss:1",
                      card["tokens"][0]["locations"])

    def test_declaration_left_hand_side_is_not_a_usage(self):
        root, discovery, tokens = self.repo({
            "app/assets/stylesheets/components/card.scss": (
                "$space-sm: 8px;\n.card { gap: $space-sm; }"
            ),
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["top_20"][0]["references"], 1)

    def test_commented_references_are_not_usage_and_lines_stay_exact(self):
        root, discovery, tokens = self.repo({
            "app/assets/stylesheets/components/card.scss": (
                "// color: var(--brand-primary);\n"
                "/* gap: $space-sm;\n border: var(--brand-primary); */\n"
                ".card { color: var(--brand-primary); }\n"
                "<!-- gap: $space-sm; -->"
            ),
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        card = result["top_20"][0]
        self.assertEqual(card["references"], 1)
        self.assertEqual(card["tokens"][0]["locations"], [
            "app/assets/stylesheets/components/card.scss:4",
        ])

    def test_canonical_sources_are_excluded_from_consumers(self):
        path = "app/assets/stylesheets/tokens.scss"
        root, discovery, tokens = self.repo(
            {path: ":root { --brand-primary: red; } .x { color: var(--brand-primary); }"},
            sources=[{"path": path, "role": "canonical"}],
        )
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["total_components_with_token_usage"], 0)

    def test_device_variants_group_into_one_component(self):
        root, discovery, tokens = self.repo({
            "plugins/demo/assets/stylesheets/common/card.scss": ".x { color: var(--brand-primary); }",
            "plugins/demo/assets/stylesheets/mobile/card.scss": ".x { gap: $space-sm; }",
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["total_usage_units"], 1)
        self.assertEqual(result["fallback_surfaces"], 1)
        self.assertEqual(len(result["top_20"][0]["paths"]), 2)

    def test_unreachable_co_named_source_does_not_promote_or_enter_usage(self):
        root, discovery, tokens = self.repo({
            "src/Button.tsx": (
                "export function Button() { return 'var(--brand-primary)'; }"
            ),
            "src/Button.module.css": ".button { color: var(--brand-primary); }",
        }, reachable_paths={"src/Button.module.css"})
        result = analyze_component_usage.analyze(root, discovery, tokens)
        button = result["top_20"][0]
        self.assertNotEqual(button["kind"], "component")
        self.assertEqual(button["references"], 1)
        self.assertEqual(button["paths"], ["src/Button.module.css"])

    def test_independently_proven_co_named_source_and_style_form_one_component(self):
        root, discovery, tokens = self.repo({
            "src/Button.tsx": "export function Button() {}",
            "src/Button.module.css": ".button { color: var(--brand-primary); }",
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        button = result["top_20"][0]
        self.assertEqual(button["kind"], "component")
        self.assertEqual(button["confidence"], "co-named-source")
        self.assertEqual(button["paths"], ["src/Button.module.css", "src/Button.tsx"])

    def test_generic_reachable_source_is_a_surface_not_a_component(self):
        root, discovery, tokens = self.repo({
            "app/routes/home.ts": "export const color = 'var(--brand-primary)';",
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["top_20"][0]["kind"], "surface")
        self.assertEqual(result["shown_components"], 0)
        self.assertEqual(result["fallback_surfaces"], 1)

    def test_owned_but_unreachable_files_do_not_enter_analysis(self):
        root, discovery, tokens = self.repo({
            "app/assets/stylesheets/components/live.scss": (
                ".live { color: var(--brand-primary); }"
            ),
            "app/assets/stylesheets/components/dead.scss": (
                ".dead { color: var(--brand-primary); color: var(--brand-primary); }"
            ),
        }, owned=["app/**"], reachable_paths={
            "app/assets/stylesheets/components/live.scss",
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["total_components_with_token_usage"], 1)
        self.assertEqual(
            result["top_20"][0]["confidence"], "path-inferred"
        )
        self.assertTrue(result["top_20"][0]["name"].endswith("/ live"))

    def test_adapter_proven_component_root_is_scanned(self):
        root, discovery, tokens = self.repo({
            "ui/components/card.scss": ".card { color: var(--brand-primary); }",
        }, reachable_paths=set(), component_roots=[{
            "path": "ui/components", "confidence": "framework-registered",
            "ownership": "owned",
        }])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["total_components_with_token_usage"], 1)
        self.assertEqual(
            result["top_20"][0]["confidence"], "framework-registered"
        )

    def test_import_graph_component_root_preserves_its_confidence(self):
        root, discovery, tokens = self.repo({
            "ui/card.ts": "export const card = 'var(--brand-primary)';",
        }, reachable_paths=set(), component_roots=[{
            "path": "ui", "confidence": "import-graph verified",
            "ownership": "owned",
        }])

        result = analyze_component_usage.analyze(root, discovery, tokens)

        self.assertEqual(
            result["top_20"][0]["confidence"], "import-graph verified"
        )

    def test_component_root_without_owned_evidence_is_not_scanned(self):
        root, discovery, tokens = self.repo({
            "ui/components/card.scss": ".card { color: var(--brand-primary); }",
        }, reachable_paths=set(), component_roots=[{
            "path": "ui/components", "confidence": "framework-registered",
            "ownership": "unknown",
        }])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["total_components_with_token_usage"], 0)

    def test_runtime_verified_component_root_is_scanned(self):
        root, discovery, tokens = self.repo({
            "ui/components/card.scss": ".card { color: var(--brand-primary); }",
        }, reachable_paths=set(), component_roots=[{
            "path": "ui/components", "confidence": "runtime verified",
            "ownership": "owned",
        }])
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["total_components_with_token_usage"], 1)
        self.assertEqual(
            result["top_20"][0]["confidence"], "runtime verified"
        )

    def test_ranking_is_reference_count_then_diversity_then_key(self):
        root, discovery, tokens = self.repo({
            "app/assets/stylesheets/components/a.scss": ".a { color: var(--brand-primary); }",
            "app/assets/stylesheets/components/b.scss": (
                ".b { color: var(--brand-primary); border: var(--brand-primary); }"
            ),
        })
        result = analyze_component_usage.analyze(root, discovery, tokens, limit=1)
        self.assertTrue(result["top_20"][0]["name"].endswith("/ b"))
        self.assertEqual(result["shown"], 1)
        self.assertEqual(result["not_shown"], 1)

    def test_identified_components_rank_before_fallback_surfaces(self):
        root, discovery, tokens = self.repo({
            "app/assets/stylesheets/page.scss": (
                ".page { color: var(--brand-primary); border: var(--brand-primary); }"
            ),
            "app/assets/stylesheets/components/card.scss": (
                ".card { color: var(--brand-primary); }"
            ),
        })
        result = analyze_component_usage.analyze(root, discovery, tokens, limit=1)
        self.assertEqual(result["top_20"][0]["kind"], "component")
        self.assertEqual(result["shown_components"], 1)
        self.assertEqual(result["fallback_surfaces"], 0)

    def test_unknown_identifiers_are_ignored(self):
        root, discovery, tokens = self.repo({
            "app/assets/stylesheets/components/card.scss": ".x { color: var(--not-a-token); }",
        })
        result = analyze_component_usage.analyze(root, discovery, tokens)
        self.assertEqual(result["total_components_with_token_usage"], 0)

    def test_roadmap_bands_follow_cumulative_confirmed_usage(self):
        rows = [
            {"id": "a", "rank": 1, "references": 50},
            {"id": "b", "rank": 2, "references": 30},
            {"id": "c", "rank": 3, "references": 20},
        ]

        roadmap = analyze_component_usage.build_roadmap(rows)

        self.assertEqual(
            [item["roadmap_band"] for item in rows],
            ["assess-first", "plan-next", "focused-follow-up"],
        )
        self.assertEqual(
            [item["share_of_ranked_references"] for item in rows],
            [50.0, 30.0, 20.0],
        )
        self.assertEqual(
            [item["component_ids"] for item in roadmap["bands"]],
            [["a"], ["b"], ["c"]],
        )

    def test_roadmap_uses_exact_thresholds_before_rounding_for_display(self):
        rows = [
            {"id": "a", "rank": 1, "references": 2000},
            {"id": "b", "rank": 2, "references": 1},
        ]

        roadmap = analyze_component_usage.build_roadmap(rows)

        self.assertEqual(
            [item["roadmap_band"] for item in rows],
            ["assess-first", "focused-follow-up"],
        )
        self.assertEqual(roadmap["ranked_references"], 2001)


if __name__ == "__main__":
    unittest.main()
