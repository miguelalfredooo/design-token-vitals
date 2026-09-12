"""Tests for token-source discovery and projection collapse."""
import os
import json
import sys
import subprocess
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import discover_tokens  # noqa: E402
import discover_environment  # noqa: E402


def make_repo(files):
    """Write {relpath: content} into a temp dir and return the root."""
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        full = os.path.join(root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
    return root


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
        self.assertEqual(identity["brand_colors"]["state"], "not-visible")
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
        self.assertEqual(identity["brand_colors"]["state"], "not-visible")

    def test_service_prefixed_brand_token_needs_product_context(self):
        concepts = [{
            "id": "facebook-brand-primary", "family": "color",
            "values": ["#0866ff"], "sites": ["styles/colors.scss:1"],
            "identity_contexts": [],
        }]
        identity = discover_tokens.identity_summary(concepts)
        self.assertEqual(identity["brand_colors"]["state"], "not-visible")

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
                self.assertEqual(identity["brand_colors"]["state"], "not-visible")

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
                self.assertEqual(identity["brand_colors"]["state"], "not-visible")

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
        self.assertEqual(brand["state"], "not-visible")
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
                self.assertEqual(identity["brand_colors"]["state"], "not-visible")

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
        self.assertEqual(identity["typography"]["state"], "not-visible")
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
        self.assertEqual(identity["typography"]["state"], "not-visible")
        self.assertEqual(identity["brand_colors"]["state"], "not-visible")

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
            "not-visible",
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
            "not-visible",
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
            "token_source_discovery": "not-visible",
        }
        discovery["capability_ladder"] = {
            "steps": [{"capability": "token_source_discovery", "state": "not-visible"}],
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
        discovery["capabilities"] = {"token_source_discovery": "not-visible"}
        discovery["capability_ladder"] = {
            "steps": [{"capability": "token_source_discovery", "state": "not-visible"}],
        }
        path = os.path.join(root, "discovery.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(discovery, handle)
        result = discover_tokens.discover(root, discovery)

        discover_tokens.update_discovery(path, result)

        with open(path, encoding="utf-8") as handle:
            updated = json.load(handle)
        self.assertEqual(updated["capabilities"]["token_source_discovery"],
                         "not-visible")
        self.assertEqual(updated["capability_ladder"]["steps"][0]["evidence"], [])


class TestFontFamilyFromAJsTokenArray(unittest.TestCase):
    """A JS token layer declares fontFamily as a list, not a string.

    Tailwind's `fontFamily` takes a stack — `['"DM Sans"', 'ui-sans-serif',
    'system-ui', 'sans-serif']` — and that is the literal source text a JS
    token file carries. concrete_font_family read it as one CSS value, the
    leading bracket failed the name pattern, and identity.typography came
    back `not-visible` on a design system whose typeface IS a token.
    """

    def test_a_bracketed_stack_resolves_to_its_first_real_family(self):
        self.assertEqual(
            discover_tokens.concrete_font_family(
                "['\"DM Sans\"', 'ui-sans-serif', 'system-ui', 'sans-serif']"),
            "DM Sans")

    def test_a_double_quoted_stack_resolves_the_same_way(self):
        self.assertEqual(
            discover_tokens.concrete_font_family(
                '["Plus Jakarta Sans", "system-ui", "sans-serif"]'),
            "Plus Jakarta Sans")

    def test_a_stack_that_leads_with_a_generic_is_still_rejected(self):
        self.assertIsNone(
            discover_tokens.concrete_font_family("['system-ui', 'sans-serif']"))

    def test_an_unresolved_stack_is_still_rejected(self):
        self.assertIsNone(
            discover_tokens.concrete_font_family("[var(--font-display), 'serif']"))

    def test_a_plain_css_stack_is_unchanged(self):
        self.assertEqual(
            discover_tokens.concrete_font_family('"DM Sans", ui-sans-serif'),
            "DM Sans")


if __name__ == "__main__":
    unittest.main()


class TestCamelCaseFontFamily(unittest.TestCase):
    """A JS token layer spells the concept `fontFamily`, and it must count.

    The selector tested `"font-family" in name` against `normalize()`, which
    lowercases but does not split camelCase — so `typography.fontFamily.sans`
    normalizes to `typography.fontfamily.sans` and never matched. A real
    audit therefore reported a product's typeface as the one in a legacy
    JSON export, while the family the application actually loads sat in a
    reachable, already-inventoried token module, extracted and ignored.
    """

    def concept(self, token_id, value, site):
        """Shaped exactly as discover() stores one, or this cannot bite.

        The id is normalize()d — lowercased, so `fontFamily` arrives as
        `fontfamily` with the word boundary already gone. A fixture that
        passes the raw spelling as the id tests a shape the pipeline never
        produces, and stays green against the bug.
        """
        return {
            "id": discover_tokens.normalize(token_id), "names": [token_id],
            "family": "typography", "values": [value],
            "sites": [site], "identity_contexts": [],
            "definitions": [{
                "value": value, "site": site,
                "representation": "js-theme-object",
            }],
        }

    def test_a_camelcase_font_family_token_is_seen(self):
        identity = discover_tokens.identity_summary([self.concept(
            "typography.fontFamily.sans",
            "['\"Plus Jakarta Sans\"', 'ui-sans-serif']",
            "src/tokens/typography.js:70")])["typography"]
        self.assertEqual(identity["state"], "verified")
        self.assertEqual(identity["family"], "Plus Jakarta Sans")

    def test_two_equally_strong_families_block_rather_than_pick(self):
        """Both are shown; neither is chosen, and no substitute is rendered."""
        identity = discover_tokens.identity_summary([
            self.concept("typography.fontFamily.sans",
                         "['\"Plus Jakarta Sans\"', 'ui-sans-serif']",
                         "src/tokens/typography.js:70"),
            self.concept("semantic.typography.font-family.brand", "DM Sans",
                         "src/tokens/production.tokens.json:1570"),
        ])["typography"]
        self.assertEqual(identity["state"], "not-visible")
        self.assertIsNone(identity["family"])
        self.assertEqual(identity["specimen"]["state"], "not-visible")
        self.assertEqual(
            sorted(item["family"] for item in identity["candidates"]),
            ["DM Sans", "Plus Jakarta Sans"])

    def test_the_named_priorities_still_win_through_the_camel_spelling(self):
        identity = discover_tokens.identity_summary([
            self.concept("baseFontFamily", "Iosevka", "src/theme.js:3"),
            self.concept("heading-font-family", "Georgia", "src/theme.js:4"),
        ])["typography"]
        self.assertEqual(identity["family"], "Iosevka")


class TestTokenSourceSiblings(unittest.TestCase):
    """A token module beside a confirmed one is admitted on that evidence.

    Admission was decided by filename. In a real `src/tokens/` directory
    that admitted colors.js, spacing.js and typography.js and rejected
    interaction.js, effects.js, componentGeometry.js, composition.js and
    visualSystemProfiles.js — six reachable modules, imported by the same
    application, holding the opacity, radius, aspect-ratio, z-index and
    blur values the run then reported as zero of. A directory that already
    holds a confirmed canonical source is evidence; a filename is a guess.
    """

    def repo(self):
        return make_repo({
            "package.json": '{"name":"app","devDependencies":{"vite":"^5"}}',
            "vite.config.js": "export default {}",
            "index.html": '<script type="module" src="/src/main.js"></script>',
            "src/main.js": 'import "./globals.css";\nimport "./tokens/index.js";',
            "src/globals.css": ":root{--color-brand:#6b5bf0}",
            "src/tokens/index.js": (
                'export { colors } from "./colors.js";\n'
                'export { opacity } from "./interaction.js";\n'
                'export { geometry } from "./geometry.js";\n'
            ),
            "src/tokens/colors.js": (
                "export const colors = {\n"
                "  brand: '#6b5bf0',\n"
                "}\n"
            ),
            "src/tokens/interaction.js": (
                "export const opacity = {\n"
                "  disabled: '0.42',\n"
                "}\n"
            ),
            "src/tokens/geometry.js": (
                "export const geometry = {\n"
                "  card: '3 / 2',\n"
                "  scrim: '12px',\n"
                "}\n"
            ),
            "src/components/Card/Card.jsx": "export const Card = () => null\n",
        })

    def result(self):
        root = self.repo()
        discovery = discover_environment.discover(root, ["src/**"])
        return discover_tokens.discover(root, discovery)

    def test_a_sibling_of_a_confirmed_source_is_itself_a_source(self):
        paths = {item["path"] for item in self.result()["sources"]
                 if item["role"] in ("canonical", "alias")}
        self.assertIn("src/tokens/interaction.js", paths)
        self.assertIn("src/tokens/geometry.js", paths)

    def test_the_admission_says_what_evidence_admitted_it(self):
        source = next(item for item in self.result()["sources"]
                      if item["path"] == "src/tokens/interaction.js")
        self.assertEqual(source["admitted_by"],
                         "sibling of a confirmed canonical source")

    def test_a_component_module_is_not_admitted_by_a_distant_source(self):
        paths = {item["path"] for item in self.result()["sources"]}
        self.assertNotIn("src/components/Card/Card.jsx", paths)

    def test_the_concepts_those_modules_hold_are_counted(self):
        counts = self.result()["family_counts"]
        self.assertGreaterEqual(counts["opacity"], 1)


class TestFamilyStates(unittest.TestCase):
    """Zero is a claim. A family with no source behind it has not earned it.

    SKILL.md's own rule: a family the run could not resolve is never
    reported as 0, because 0 states that the project has none — and "a
    family found only in an unverified source is `not-visible`, because
    reachability decides here the same as everywhere else." The counts map
    emitted 0 for every family alike, so `opacity: 0` read identically
    whether the run had proved there were none or had never looked.
    """

    TOKENS = (":root{--color-brand:#6b5bf0;--color-text:#111;--spacing-2:8px;"
              "--spacing-4:16px;--radius-md:6px;--border-width:1px}")

    def states(self, files, entry='import "./globals.css";'):
        root = make_repo({
            "package.json": '{"name":"app","devDependencies":{"vite":"^5"}}',
            "vite.config.js": "export default {}",
            "index.html": '<script type="module" src="/src/main.js"></script>',
            "src/main.js": entry,
            **files,
        })
        discovery = discover_environment.discover(root, ["src/**"])
        return discover_tokens.discover(root, discovery)["family_states"]

    def test_a_measured_family_carries_its_count(self):
        states = self.states({
            "src/globals.css": self.TOKENS[:-1] + ";--motion-fast:120ms}",
        })
        self.assertEqual(states["motion"], {"state": "counted", "count": 1})

    def held_out(self):
        """globals.css is canonical; the component sheet is held out."""
        return self.states(
            {
                "src/globals.css": self.TOKENS,
                "src/components/Card/card.css": ".c{--motion-fast:120ms}",
            },
            entry='import "./globals.css";\nimport "./components/Card/card.css";')

    def test_a_family_found_only_in_a_held_out_source_is_unmeasured(self):
        """Held out for reachability, so its count is not this run's to give."""
        states = self.held_out()
        self.assertEqual(states["motion"]["state"], "not-visible")
        self.assertNotIn("count", states["motion"])

    def test_a_family_found_nowhere_at_all_is_absent(self):
        states = self.states({"src/globals.css": self.TOKENS})
        self.assertEqual(states["motion"], {"state": "none-used", "count": 0})

    def test_no_family_is_ever_a_bare_zero_without_a_state(self):
        for family, state in self.held_out().items():
            if state["state"] == "not-visible":
                self.assertNotIn("count", state, family)

    def test_every_taxonomy_family_has_a_state(self):
        states = self.states({"src/globals.css": self.TOKENS})
        self.assertEqual(set(states), set(discover_tokens.FAMILIES))
        for family, state in states.items():
            self.assertIn(state["state"], ("counted", "not-visible", "none-used"),
                          family)


class TestUnreadableValues(unittest.TestCase):
    """A declaration whose value the reader cannot resolve is not an absence.

    `backdropBlur: spacing[2]` is a real blur token. The conservative JS
    reader takes literals only, so the line is skipped and the family lands
    at zero — and zero says the project has none, which is the one claim
    this run has not earned. A name the run SAW but could not resolve makes
    its family unmeasured, never absent.
    """

    def states(self, module):
        root = make_repo({
            "package.json": '{"name":"app","devDependencies":{"vite":"^5"}}',
            "vite.config.js": "export default {}",
            "index.html": '<script type="module" src="/src/main.js"></script>',
            "src/main.js": 'import "./globals.css";\nimport "./tokens/theme.js";',
            "src/globals.css": (
                ":root{--color-brand:#6b5bf0;--color-text:#111;--spacing-2:8px;"
                "--spacing-4:16px;--radius-md:6px;--border-width:1px}"),
            "src/tokens/theme.js": module,
        })
        discovery = discover_environment.discover(root, ["src/**"])
        return discover_tokens.discover(root, discovery)["family_states"]

    def test_a_referenced_value_leaves_its_family_unmeasured(self):
        states = self.states(
            "export const theme = {\n"
            "  brand: '#6b5bf0',\n"
            "  backdropBlur: spacing[2],\n"
            "}\n")
        self.assertEqual(states["blur"]["state"], "not-visible")
        self.assertNotIn("count", states["blur"])

    def test_a_resolvable_value_still_counts_normally(self):
        states = self.states(
            "export const theme = {\n"
            "  brand: '#6b5bf0',\n"
            "  backdropBlur: '12px',\n"
            "}\n")
        self.assertEqual(states["blur"], {"state": "counted", "count": 1})

    def test_a_family_named_nowhere_is_still_absent(self):
        states = self.states(
            "export const theme = {\n"
            "  brand: '#6b5bf0',\n"
            "  backdropBlur: spacing[2],\n"
            "}\n")
        self.assertEqual(states["density"], {"state": "none-used", "count": 0})


class TestTier(unittest.TestCase):
    """Tier-integrity cannot be graded off a field nothing sets.

    A real run produced 749 concepts and every one of them carried no tier
    at all, so the vital that asks whether primitives, semantic aliases and
    projections stay in their layers had nothing to read. Each concept now
    carries the tier its own evidence supports, and says which evidence —
    and a link the run could not trace stays `untraced` rather than being
    guessed into a layer.
    """

    def tiers(self, files):
        root = make_repo({
            "package.json": '{"name":"app","devDependencies":{"vite":"^5"}}',
            "vite.config.js": "export default {}",
            "index.html": '<script type="module" src="/src/main.js"></script>',
            "src/main.js": 'import "./globals.css";',
            **files,
        })
        discovery = discover_environment.discover(root, ["src/**"])
        result = discover_tokens.discover(root, discovery)
        return ({item["id"]: item for item in result["concepts"]},
                result["lineage"])

    def test_a_concrete_value_with_no_reference_is_primitive(self):
        concepts, _ = self.tiers({"src/globals.css": (
            ":root{--blue-500:#6b5bf0;--color-text:#111;--spacing-2:8px;"
            "--spacing-4:16px;--radius-md:6px;--border-width:1px}")})
        self.assertEqual(concepts["blue-500"]["tier"], "primitive")
        self.assertIn("concrete value", concepts["blue-500"]["tier_evidence"])

    def test_a_reference_to_a_known_token_is_a_traced_semantic_alias(self):
        concepts, lineage = self.tiers({"src/globals.css": (
            ":root{--blue-500:#6b5bf0;--color-action:var(--blue-500);"
            "--color-text:#111;--spacing-2:8px;--spacing-4:16px;"
            "--radius-md:6px}")})
        self.assertEqual(concepts["color-action"]["tier"], "semantic")
        self.assertEqual(concepts["color-action"]["alias_of"], "blue-500")
        self.assertTrue(concepts["color-action"]["alias_resolved"])
        self.assertEqual(lineage["resolved_alias_edges"], 1)
        self.assertEqual(lineage["untraced_alias_edges"], 0)

    def test_a_reference_to_nothing_this_run_found_stays_untraced(self):
        concepts, lineage = self.tiers({"src/globals.css": (
            ":root{--color-action:var(--from-elsewhere);--color-text:#111;"
            "--spacing-2:8px;--spacing-4:16px;--radius-md:6px;"
            "--border-width:1px}")})
        self.assertFalse(concepts["color-action"]["alias_resolved"])
        self.assertEqual(lineage["untraced_alias_edges"], 1)

    def test_an_explicit_namespace_outranks_the_value_shape(self):
        """`semantic.*` holding a concrete value is a declaration, not a leak."""
        concepts, _ = self.tiers({"src/globals.css": (
            ":root{--semantic-color-action:#6b5bf0;--color-text:#111;"
            "--spacing-2:8px;--spacing-4:16px;--radius-md:6px;"
            "--border-width:1px}")})
        self.assertEqual(concepts["semantic-color-action"]["tier"], "semantic")
        self.assertIn("token name",
                      concepts["semantic-color-action"]["tier_evidence"])

    def test_every_concept_carries_a_tier(self):
        concepts, lineage = self.tiers({"src/globals.css": (
            ":root{--blue-500:#6b5bf0;--color-action:var(--blue-500);"
            "--color-text:#111;--spacing-2:8px;--spacing-4:16px;"
            "--radius-md:6px}")})
        for key, item in concepts.items():
            self.assertIn(item["tier"],
                          ("primitive", "semantic", "component", "untraced"), key)
            self.assertTrue(item["tier_evidence"], key)
        self.assertEqual(sum(lineage["tiers"].values()), len(concepts))


class TestConflictingDefinitions(unittest.TestCase):
    """A token defined twice does not get a tier picked from one of them.

    87 concepts in one real repository carried more than one value —
    `--button-outline-border` is `var(--color-border)` in a stylesheet and
    two different values in two visual-system profiles. The tier walk read
    whichever definition it reached last, so 56 concepts were filed into a
    layer on the strength of a third of their own evidence.
    """

    def concept(self, definitions, alias_of=None):
        return {
            "id": "x", "family": "color", "names": ["x"],
            "values": [d["value"] for d in definitions],
            "sites": [d["site"] for d in definitions],
            "alias_of": alias_of, "definitions": definitions,
        }

    def tier(self, definitions, alias_of=None, known=()):
        return discover_tokens.tier_for(
            self.concept(definitions, alias_of), set(known))

    def test_definitions_that_disagree_on_shape_leave_the_tier_untraced(self):
        tier, why = self.tier([
            {"value": "#e9e9ea", "site": "a.js:1"},
            {"value": "var(--color-text)", "site": "a.js:2"},
        ], alias_of="color-text", known=["color-text"])
        self.assertEqual(tier, "untraced")
        self.assertIn("2 definitions", why)
        self.assertIn("a.js:1", why)

    def test_definitions_that_agree_on_shape_still_get_their_tier(self):
        tier, _ = self.tier([
            {"value": "#fff", "site": "a.css:1"},
            {"value": "#eee", "site": "b.css:1"},
        ])
        self.assertEqual(tier, "primitive")

    def test_one_definition_is_unchanged(self):
        tier, why = self.tier([{"value": "#fff", "site": "a.css:1"}])
        self.assertEqual(tier, "primitive")
        self.assertIn("concrete value", why)

    def test_a_declared_namespace_still_outranks_a_disagreement(self):
        """An explicit `semantic.*` name is a decision, not an accident."""
        concept = self.concept([
            {"value": "#e9e9ea", "site": "a.js:1"},
            {"value": "var(--x)", "site": "a.js:2"},
        ])
        concept["names"] = ["semantic.color.action"]
        tier, why = discover_tokens.tier_for(concept, set())
        self.assertEqual(tier, "semantic")
        self.assertIn("token name", why)


class TestConflictReport(unittest.TestCase):
    """Defined twice is a finding, and the run already had the evidence."""

    def conflicts(self, globals_css, profiles_js):
        root = make_repo({
            "package.json": '{"name":"app","devDependencies":{"vite":"^5"}}',
            "vite.config.js": "export default {}",
            "index.html": '<script type="module" src="/src/main.js"></script>',
            "src/main.js": 'import "./globals.css";\nimport "./tokens.js";',
            "src/globals.css": globals_css,
            "src/tokens.js": profiles_js,
        })
        discovery = discover_environment.discover(root, ["src/**"])
        return discover_tokens.discover(root, discovery)["conflicts"]

    BASE = (":root{--color-brand:#6b5bf0;--color-text:#111;--spacing-2:8px;"
            "--spacing-4:16px;--radius-md:6px;--border-width:1px;")

    def test_a_token_defined_twice_with_different_values_is_reported(self):
        conflicts = self.conflicts(
            self.BASE + "--button-border:var(--color-border)}",
            "export const tokens = Object.freeze({\n"
            "  '--button-border': '#e9e9ea',\n})\n")
        entry = next(item for item in conflicts
                     if item["token"] == "button-border")
        self.assertEqual(len(entry["definitions"]), 2)
        self.assertEqual(entry["kind"], "literal beside alias")

    def test_a_token_defined_once_is_not_a_conflict(self):
        conflicts = self.conflicts(self.BASE + "}",
                                   "export const tokens = Object.freeze({})\n")
        self.assertEqual([item["token"] for item in conflicts], [])

    def test_the_kind_says_which_of_the_three_it_is(self):
        conflicts = self.conflicts(
            self.BASE + "--a:var(--color-text);--b:#111}",
            "export const tokens = Object.freeze({\n"
            "  '--a': 'var(--color-brand)',\n"
            "  '--b': '#222',\n})\n")
        kinds = {item["token"]: item["kind"] for item in conflicts}
        self.assertEqual(kinds["a"], "two aliases")
        self.assertEqual(kinds["b"], "two literals")
