"""Tests for token-source discovery and projection collapse."""
import os
import json
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover_tokens  # noqa: E402


class TestTokenDiscovery(unittest.TestCase):
    def repo(self, files):
        root = tempfile.mkdtemp()
        reachable = {}
        for path, text in files.items():
            full = os.path.join(root, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write(text)
            reachable[path] = {"via": ["app/main.scss"]}
        return root, {"owned_import_graph": {"reachable": reachable}}

    def test_scss_and_css_projection_count_once(self):
        root, discovery = self.repo({
            "styles/definitions.scss": "$spacing-sm: 8px;\n:root { --spacing-sm: #{$spacing-sm}; }",
        })
        result = discover_tokens.discover(root, discovery, ["styles/definitions.scss"])
        self.assertEqual(result["concept_count"], 1)
        self.assertEqual(result["concepts"][0]["representations"],
                         ["css-custom-property", "scss-variable"])
        self.assertIn("#{$spacing-sm}", result["concepts"][0]["values"])

    def test_small_component_override_is_not_canonical(self):
        root, discovery = self.repo({
            "styles/components/card.scss": ".card { --card-gap: 4px; }",
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 0)
        self.assertEqual(result["candidate_or_local_override_sources"][0]["role"],
                         "consumer-override")

    def test_source_like_filename_does_not_promote_one_local_override(self):
        root, discovery = self.repo({
            "src/pages/checkout-layout.scss": (
                ".checkout { --dialog-offset: 4px; }"
            ),
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 0)
        self.assertEqual(
            result["candidate_or_local_override_sources"][0]["role"],
            "candidate",
        )

    def test_source_named_root_font_declarations_are_canonical(self):
        root, discovery = self.repo({
            "styles/typography.scss": (
                ':root { --font-family: "DM Sans", sans-serif; '
                '--heading-font-family: "DM Sans", sans-serif; }'
            ),
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 2)
        self.assertEqual(result["sources"][0]["role"], "canonical")

    def test_source_named_nested_root_declarations_are_canonical(self):
        root, discovery = self.repo({
            "styles/mobile-variables.scss": (
                ":root {\n  --mobile-gap: 8px;\n"
                "  &.compact-mobile-ui { --mobile-gap: 4px; }\n}\n"
            ),
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 1)
        self.assertEqual(result["sources"][0]["role"], "canonical")

    def test_commented_root_example_does_not_promote_source(self):
        root, discovery = self.repo({
            "styles/variables.scss": (
                "$component-only: 4px;\n"
                "/* :root { --documented-only: red; } */\n"
            ),
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 0)
        self.assertEqual(result["sources"][0]["role"], "candidate")

    def test_typography_and_motion_are_classified(self):
        root, discovery = self.repo({
            "styles/tokens.scss": "$font-size-sm: 14px;\n$motion-duration-fast: 120ms;",
        })
        result = discover_tokens.discover(root, discovery, ["styles/tokens.scss"])
        self.assertEqual(result["family_counts"]["typography"], 1)
        self.assertEqual(result["family_counts"]["motion"], 1)

    def test_identity_uses_explicit_brand_section_without_inference(self):
        root, discovery = self.repo({
            "package.json": json.dumps({"name": "@acme/design-system"}),
            "styles/colors.scss": (
                "// Acme Brand Colors\n"
                "$acme-primary: #123456;\n"
                "$acme-accent: #abcdef;\n"
                "// Application colors\n"
                "$primary: #111111;\n"
            ),
        })
        result = discover_tokens.discover(
            root, discovery, ["styles/colors.scss"])
        colors = result["identity"]["brand_colors"]
        self.assertEqual(colors["state"], "verified")
        self.assertEqual(
            [item["token"] for item in colors["colors"]],
            ["acme-accent", "acme-primary"],
        )
        self.assertTrue(all(
            item["confidence"] == "explicit-brand-source-section"
            for item in colors["colors"]
        ))

    def test_identity_reads_multiline_brand_section_heading(self):
        root, discovery = self.repo({
            "package.json": json.dumps({"name": "@acme/design-system"}),
            "styles/colors.scss": (
                "/*\n"
                " * Acme Brand Colors\n"
                " */\n"
                "$acme-primary: #123456;\n"
            ),
        })
        result = discover_tokens.discover(
            root, discovery, ["styles/colors.scss"])
        self.assertEqual(
            [item["token"] for item in
             result["identity"]["brand_colors"]["colors"]],
            ["acme-primary"],
        )

    def test_identity_does_not_guess_brand_from_primary_alone(self):
        concepts = [{
            "id": "primary", "family": "color", "values": ["#123456"],
            "sites": ["styles/colors.scss:1"], "identity_contexts": [],
        }]
        identity = discover_tokens.identity_summary(concepts)
        self.assertEqual(identity["brand_colors"]["state"], "blocked")
        self.assertEqual(identity["brand_colors"]["colors"], [])

    def test_generic_brand_section_does_not_promote_service_colors(self):
        concepts = [{
            "id": "facebook", "family": "color", "values": ["#0866ff"],
            "sites": ["styles/colors.scss:2"],
            "identity_contexts": [{
                "kind": "brand", "label": "Brand color variables",
                "path": "styles/colors.scss", "line": 1,
            }],
        }]
        identity = discover_tokens.identity_summary(concepts)
        self.assertEqual(identity["brand_colors"]["state"], "blocked")

    def test_service_prefixed_brand_token_needs_product_context(self):
        concepts = [{
            "id": "facebook-brand-primary", "family": "color",
            "values": ["#0866ff"], "sites": ["styles/colors.scss:1"],
            "identity_contexts": [],
        }]
        identity = discover_tokens.identity_summary(concepts)
        self.assertEqual(identity["brand_colors"]["state"], "blocked")

    def test_third_party_brand_heading_does_not_promote_service_color(self):
        for label in ("Facebook Brand Colors", "Visual Identity"):
            with self.subTest(label=label):
                concepts = [{
                    "id": "facebook-brand-primary", "family": "color",
                    "values": ["#0866ff"], "sites": ["styles/colors.scss:2"],
                    "identity_contexts": [{
                        "kind": "brand", "label": label,
                        "path": "styles/colors.scss", "line": 1,
                    }],
                }]
                identity = discover_tokens.identity_summary(concepts)
                self.assertEqual(identity["brand_colors"]["state"], "blocked")

    def test_audited_product_namespace_can_use_its_own_service_name(self):
        concepts = [{
            "id": "github-brand-primary", "family": "color",
            "values": ["#24292f"], "sites": ["styles/colors.scss:1"],
            "definitions": [{
                "value": "#24292f", "site": "styles/colors.scss:1",
                "representation": "scss-variable",
            }],
        }]
        identity = discover_tokens.identity_summary(
            concepts, subject_namespaces=[{
                "namespace": "github",
                "evidence": ["git remote owner: github"],
            }])
        self.assertEqual(identity["brand_colors"]["state"], "verified")
        self.assertEqual(
            identity["brand_colors"]["subject_namespaces"][0]["namespace"],
            "github",
        )

    def test_integration_package_does_not_make_service_the_product(self):
        root, _ = self.repo({
            "package.json": json.dumps({"name": "@acme/github-integration"}),
        })
        namespaces = {
            item["namespace"] for item in
            discover_tokens.subject_namespace_evidence(root)
        }
        self.assertIn("acme", namespaces)
        self.assertNotIn("github", namespaces)

    def test_repeated_third_party_plugins_do_not_make_service_the_product(self):
        root, _ = self.repo({
            "plugins/google-analytics/plugin.rb": "",
            "plugins/google-oauth/plugin.rb": "",
            "plugins/google-maps/plugin.rb": "",
        })
        namespaces = {
            item["namespace"] for item in
            discover_tokens.subject_namespace_evidence(root)
        }
        self.assertNotIn("google", namespaces)

    def test_service_repo_name_needs_matching_owner_evidence(self):
        parent = tempfile.mkdtemp()
        root = os.path.join(parent, "github")
        os.makedirs(root)
        subprocess.run(
            ["git", "init", "-q", root], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(
            ["git", "-C", root, "remote", "add", "origin",
             "https://github.com/acme/github.git"], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        namespaces = {
            item["namespace"] for item in
            discover_tokens.subject_namespace_evidence(root)
        }
        self.assertIn("acme", namespaces)
        self.assertNotIn("github", namespaces)

    def test_unresolved_functional_brand_color_is_not_concrete(self):
        for value in (
                "rgb(var(--brand-rgb))",
                "oklch(from var(--base) l c h)",
                "rgb($red, 0, 0)", "#12345", "#1234567", "rgb(foo)",
                "hsl(brand)", "oklch(red green blue)", "rgb(1,,2,3)",
                "rgb(1, 2 3)", "rgb(1 / 2 3)",
                "hsl(10deg 20% 30% 40%)",
                "color(display-p3 1 0 0 0.5)"):
            with self.subTest(value=value):
                concepts = [{
                    "id": "brand-primary", "family": "color",
                    "values": [value], "sites": ["styles/colors.scss:1"],
                    "identity_contexts": [],
                }]
                identity = discover_tokens.identity_summary(concepts)
                self.assertEqual(identity["brand_colors"]["state"], "blocked")

    def test_brand_context_and_value_evidence_stay_paired(self):
        concepts = [{
            "id": "acme-primary", "family": "color",
            "values": ["#111111", "#abcdef"],
            "sites": ["third-party.scss:1", "brand.scss:2"],
            "definitions": [
                {
                    "value": "#111111", "site": "third-party.scss:1",
                    "representation": "scss-variable",
                    "identity_context": None,
                },
                {
                    "value": "#abcdef", "site": "brand.scss:2",
                    "representation": "scss-variable",
                    "identity_context": {
                        "kind": "brand", "label": "Acme Brand Colors",
                        "path": "brand.scss", "line": 1,
                    },
                },
            ],
        }]
        colors = discover_tokens.identity_summary(
            concepts, subject_namespaces=[{
                "namespace": "acme", "evidence": ["scoped package owner"],
            }])[
            "brand_colors"]["colors"]
        self.assertEqual(colors[0]["value"], "#abcdef")
        self.assertNotIn("third-party.scss:1", colors[0]["evidence"])

    def test_conflicting_brand_values_are_not_published_as_one_color(self):
        concepts = [{
            "id": "brand-primary", "family": "color",
            "values": ["#111111", "#abcdef"],
            "sites": ["a.scss:1", "b.scss:1"],
            "definitions": [
                {"value": "#111111", "site": "a.scss:1",
                 "representation": "scss-variable"},
                {"value": "#abcdef", "site": "b.scss:1",
                 "representation": "scss-variable"},
            ],
        }]
        brand = discover_tokens.identity_summary(concepts)["brand_colors"]
        self.assertEqual(brand["state"], "blocked")
        self.assertEqual(brand["colors"], [])
        self.assertEqual(brand["conflicts"][0]["token"], "brand-primary")

    def test_foreign_brand_namespace_is_not_product_identity(self):
        for token in (
                "stripe-brand-primary", "brand-stripe-primary",
                "color-brand-mailchimp", "brand-notion"):
            with self.subTest(token=token):
                concepts = [{
                    "id": token, "family": "color",
                    "values": ["#123456"], "sites": ["colors.scss:1"],
                    "definitions": [{
                        "value": "#123456", "site": "colors.scss:1",
                        "representation": "scss-variable",
                    }],
                }]
                identity = discover_tokens.identity_summary(
                    concepts, subject_namespaces=[{
                        "namespace": "acme", "evidence": ["remote owner"],
                    }])
                self.assertEqual(identity["brand_colors"]["state"], "blocked")

    def test_identity_blocks_equal_priority_font_conflicts(self):
        concepts = [{
            "id": "font-family", "family": "typography",
            "values": ["Inter, sans-serif", "DM Sans, sans-serif"],
            "sites": ["a.css:1", "b.css:1"],
            "definitions": [
                {"value": "Inter, sans-serif", "site": "a.css:1",
                 "representation": "css-custom-property"},
                {"value": "DM Sans, sans-serif", "site": "b.css:1",
                 "representation": "css-custom-property"},
            ],
        }]
        identity = discover_tokens.identity_summary(concepts)
        self.assertEqual(identity["typography"]["state"], "blocked")
        self.assertEqual(
            {item["family"] for item in identity["typography"]["candidates"]},
            {"Inter", "DM Sans"},
        )

    def test_identity_cannot_verify_from_unpaired_aggregates(self):
        concepts = [{
            "id": "font-family", "family": "typography",
            "values": ["DM Sans, sans-serif"], "sites": ["type.css:1"],
            "representations": ["css-custom-property"],
        }, {
            "id": "brand-primary", "family": "color",
            "values": ["#123456"], "sites": ["colors.css:1"],
            "representations": ["css-custom-property"],
        }]
        identity = discover_tokens.identity_summary(concepts)
        self.assertEqual(identity["typography"]["state"], "blocked")
        self.assertEqual(identity["brand_colors"]["state"], "blocked")

    def test_font_identity_uses_the_first_stack_item_only(self):
        cases = {
            'Acme Sans, "Helvetica Neue", sans-serif': "Acme Sans",
            'Arial, "DM Sans", sans-serif': "Arial",
            '"DM Sans", system-ui, sans-serif': "DM Sans",
            'system-ui, "DM Sans", sans-serif': None,
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(
                    discover_tokens.concrete_font_family(value), expected)

    def test_identity_verifies_a_reachable_font_face_asset(self):
        root, discovery = self.repo({
            "styles/typography.scss": (
                '@font-face { font-family: "Acme Sans"; '
                'src: url("/fonts/acme.woff2") format("woff2"); }\n'
                ':root { --font-family: "Acme Sans", sans-serif; }\n'
            ),
        })
        asset = os.path.join(root, "public/fonts/acme.woff2")
        os.makedirs(os.path.dirname(asset), exist_ok=True)
        with open(asset, "wb") as handle:
            handle.write(b"wOF2verified-font")
        result = discover_tokens.discover(
            root, discovery, ["styles/typography.scss"])
        specimen = result["identity"]["typography"]["specimen"]
        self.assertEqual(specimen["state"], "verified")
        self.assertEqual(specimen["asset"]["path"], "public/fonts/acme.woff2")

    def test_non_font_asset_cannot_verify_a_specimen(self):
        root, discovery = self.repo({
            "styles/typography.scss": (
                '@font-face { font-family: "Acme Sans"; '
                'src: url("/fonts/acme.svg"); }\n'
                ':root { --font-family: "Acme Sans", sans-serif; }\n'
            ),
            "public/fonts/acme.svg": "<svg></svg>",
        })
        result = discover_tokens.discover(
            root, discovery, ["styles/typography.scss"])
        self.assertEqual(
            result["identity"]["typography"]["specimen"]["state"],
            "blocked",
        )

    def test_commented_font_face_cannot_verify_a_specimen(self):
        root, discovery = self.repo({
            "styles/typography.scss": (
                '/* @font-face { font-family: "Acme Sans"; '
                'src: url("/fonts/acme.woff2") format("woff2"); } */\n'
                ':root { --font-family: "Acme Sans", sans-serif; }\n'
            ),
        })
        asset = os.path.join(root, "public/fonts/acme.woff2")
        os.makedirs(os.path.dirname(asset), exist_ok=True)
        with open(asset, "wb") as handle:
            handle.write(b"wOF2inactive-font")
        result = discover_tokens.discover(
            root, discovery, ["styles/typography.scss"])
        self.assertEqual(
            result["identity"]["typography"]["specimen"]["state"],
            "blocked",
        )

    def test_family_matching_uses_token_boundaries_and_taxonomy_terms(self):
        cases = {
            "scheme-type": "unclassified",
            "d-nav-underline-height": "sizing",
            "composer-internal-padding": "spacing",
            "d-wrap-margin-h": "spacing",
            "d-input-text-color--disabled": "color",
            "d-nav-bg-color--hover": "color",
            "state-layer-hover": "state",
            "icon-brand-primary": "color",
            "icon-size-medium": "icon",
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(discover_tokens.family_for(name, "var(--x)"),
                                 expected)

    def test_nested_sass_map_entries_become_layer_concepts(self):
        root, discovery = self.repo({
            "styles/variables.scss": '$z-layers: (\n  "modal": (\n    "dialog": 1700,\n  ),\n  "base": 1,\n);',
        })
        result = discover_tokens.discover(root, discovery)
        ids = {item["id"] for item in result["concepts"]}
        self.assertIn("z-layers.modal.dialog", ids)
        self.assertIn("z-layers.base", ids)
        self.assertEqual(result["family_counts"]["layer"], 2)

    def test_dtcg_and_style_dictionary_json_are_discovered(self):
        root, discovery = self.repo({
            "tokens/design-tokens.json": json.dumps({
                "color": {"brand": {"$type": "color", "$value": "#123456"}},
                "spacing": {"sm": {"type": "dimension", "value": "8px"}},
            }),
        })
        result = discover_tokens.discover(
            root, discovery, ["tokens/design-tokens.json"])
        concepts = {item["id"]: item for item in result["concepts"]}
        self.assertIn("color.brand", concepts)
        self.assertIn("spacing.sm", concepts)
        self.assertEqual(concepts["color.brand"]["representations"], ["dtcg-json"])

    def test_conservative_js_theme_object_is_discovered(self):
        root, discovery = self.repo({
            "src/theme.ts": (
                "export const tokens = {\n"
                "  color: {\n"
                "    brand: \"#123456\",\n"
                "  },\n"
                "  spacingSm: \"8px\",\n"
                "};\n"
            ),
        })
        result = discover_tokens.discover(root, discovery, ["src/theme.ts"])
        ids = {item["id"] for item in result["concepts"]}
        self.assertIn("tokens.color.brand", ids)
        self.assertIn("tokens.spacingsm", ids)

    def test_arbitrary_javascript_objects_are_not_tokens(self):
        root, discovery = self.repo({
            "src/user.ts": "export const user = {\n  name: \"Ada\",\n};",
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 0)

    def test_typographer_replacement_table_is_not_a_token_source(self):
        root, discovery = self.repo({
            "src/features/custom-typographer-replacements.js": (
                "const SCOPED_ABBR = {\n"
                "  pa: '¶',\n"
                "  tm: '™',\n"
                "};\n"
            ),
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 0)
        self.assertEqual(result["sources"], [])

    def test_embedded_component_style_is_an_override_not_canonical(self):
        root, discovery = self.repo({
            "src/components/Card.vue": (
                "<style>.card { --card-gap: 8px; }</style>"
            ),
        })
        result = discover_tokens.discover(root, discovery)
        self.assertEqual(result["concept_count"], 0)
        self.assertEqual(result["candidate_or_local_override_sources"][0]["role"],
                         "consumer-override")

    def test_bem_modifier_selector_is_not_a_custom_property(self):
        root, discovery = self.repo({
            "styles/tokens.scss": (
                ".score {\n"
                "  &--acme:not(:last-child) { margin-bottom: 1em; }\n"
                "  --score-gap: 8px;\n"
                "}\n"
            ),
        })
        result = discover_tokens.discover(
            root, discovery, ["styles/tokens.scss"])
        ids = {item["id"] for item in result["concepts"]}
        self.assertEqual(ids, {"score-gap"})

    def test_multiline_custom_property_keeps_value_and_alias(self):
        root, discovery = self.repo({
            "styles/tokens.scss": (
                ":root {\n"
                "  --highlight: var(\n"
                "    --primary-medium\n"
                "  );\n"
                "}\n"
            ),
        })
        result = discover_tokens.discover(
            root, discovery, ["styles/tokens.scss"])
        token = result["concepts"][0]
        self.assertEqual(token["id"], "highlight")
        self.assertEqual(token["alias_of"], "primary-medium")
        self.assertIn("--primary-medium", token["values"][0])

    def test_update_discovery_advances_the_capability_ladder(self):
        root, discovery = self.repo({
            "styles/tokens.scss": "$spacing-sm: 8px;",
        })
        discovery["capabilities"] = {
            "production_roots": "verified",
            "import_resolution": "verified",
            "token_source_discovery": "unmeasured",
        }
        discovery["capability_ladder"] = {
            "steps": [{"capability": "token_source_discovery", "state": "unmeasured"}],
        }
        path = os.path.join(root, "discovery.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(discovery, handle)
        result = discover_tokens.discover(
            root, discovery, ["styles/tokens.scss"])
        discover_tokens.update_discovery(path, result)
        with open(path, encoding="utf-8") as handle:
            updated = json.load(handle)
        self.assertEqual(updated["capabilities"]["token_source_discovery"],
                         "verified")
        self.assertEqual(updated["capability_ladder"]["steps"][0]["state"],
                         "verified")

    def test_update_discovery_blocks_when_only_candidate_sources_exist(self):
        root, discovery = self.repo({
            "styles/card.scss": ":root { --one: 1; --two: 2; }",
        })
        discovery["capabilities"] = {"token_source_discovery": "unmeasured"}
        discovery["capability_ladder"] = {
            "steps": [{"capability": "token_source_discovery", "state": "unmeasured"}],
        }
        path = os.path.join(root, "discovery.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(discovery, handle)
        result = discover_tokens.discover(root, discovery)

        discover_tokens.update_discovery(path, result)

        with open(path, encoding="utf-8") as handle:
            updated = json.load(handle)
        self.assertEqual(updated["capabilities"]["token_source_discovery"],
                         "blocked")
        self.assertEqual(updated["capability_ladder"]["steps"][0]["evidence"], [])


if __name__ == "__main__":
    unittest.main()
