"""Tests for the declarative, composable framework-profile registry."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import framework_profiles  # noqa: E402


def make_repo(files):
    root = tempfile.mkdtemp()
    for rel, content in files.items():
        path = os.path.join(root, rel)
        if content is None:
            os.makedirs(path, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
    return root


class TestRegistry(unittest.TestCase):
    def custom_profile(self):
        return {
            "id": "widget", "kind": "framework", "priority": 95,
            "adapter": "references/environment-adapters.md",
            "detection": {
                "claim": "Widget application",
                "confidence": "static candidate",
                "required": [{"type": "path_any", "patterns": ["widget.config.js"]}],
                "supporting": [], "minimum_supporting": 0,
            },
            "roots": [], "component_roots": [], "surface_roots": [],
            "guidance": {
                "production_roots": "Read widget entries.",
                "import_resolution": "Follow widget imports.",
                "token_source_discovery": "Inspect widget themes.",
                "ownership": "Separate dependencies.",
                "mode_resolution": "Resolve every scheme.",
                "runtime_verification": "Inspect built output.",
            },
        }

    def test_builtin_registry_has_one_universal_capability_order(self):
        registry = framework_profiles.load_registry()
        self.assertEqual(registry["capability_order"], framework_profiles.CAPABILITIES)
        ids = [item["id"] for item in registry["profiles"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("discourse", ids)
        self.assertIn("nextjs", ids)
        self.assertIn("sveltekit", ids)
        self.assertIn("angular", ids)

    def test_sveltekit_and_vite_compose(self):
        root = make_repo({
            "svelte.config.js": "export default {};",
            "vite.config.ts": "export default {};",
            "src/routes/+layout.svelte": '<script>import "../app.css";</script>',
            "src/app.css": ":root { --brand: red; }",
        })
        active, _ = framework_profiles.match_profiles(
            root, framework_profiles.load_registry())
        self.assertEqual([item["id"] for item in active], ["sveltekit", "vite"])

    def test_custom_profile_file_extends_without_replacing_builtins(self):
        root = make_repo({"widget.config.js": "export default {};"})
        profile_path = os.path.join(root, "profiles.json")
        custom = {"profiles": [self.custom_profile()]}
        with open(profile_path, "w", encoding="utf-8") as handle:
            json.dump(custom, handle)
        registry = framework_profiles.load_registry([profile_path])
        active, _ = framework_profiles.match_profiles(root, registry)
        self.assertEqual([item["id"] for item in active], ["widget"])
        self.assertIn("nextjs", {item["id"] for item in registry["profiles"]})
        self.assertEqual(
            [item["path"] for item in registry["_sources"]],
            ["assets/framework-profiles.json", os.path.abspath(profile_path)],
        )
        self.assertTrue(all(len(item["sha256"]) == 64
                            for item in registry["_sources"]))

    def test_capability_contribution_requires_evidence(self):
        profile = self.custom_profile()
        profile["capability_contributions"] = {
            "import_resolution": {
                "state": "verified", "evidence": [],
                "next_step": "Continue token discovery.",
            },
        }
        registry = {
            "schema_version": 1,
            "capability_order": framework_profiles.CAPABILITIES,
            "profiles": [profile],
        }
        with self.assertRaisesRegex(ValueError, "requires string evidence"):
            framework_profiles.validate_registry(registry)

    def test_import_rewrite_placeholders_must_match_named_groups(self):
        profile = self.custom_profile()
        profile["import_rewrites"] = [{
            "regex": r"^virtual/(?P<name>.+)$",
            "replacement": "src/{missing}",
        }]
        registry = {
            "schema_version": 1,
            "capability_order": framework_profiles.CAPABILITIES,
            "profiles": [profile],
        }
        with self.assertRaisesRegex(ValueError, "unknown groups: missing"):
            framework_profiles.validate_registry(registry)

    def test_regex_extractor_formatters_must_match_named_groups(self):
        profile = self.custom_profile()
        profile["extractors"] = [{
            "type": "regex_roots", "files": ["widget.config.js"],
            "regex": r"root=(?P<spec>[^\s]+)",
            "path_template": "{not_a_group}",
            "evidence": "registered {also_missing}",
        }]
        registry = {
            "schema_version": 1,
            "capability_order": framework_profiles.CAPABILITIES,
            "profiles": [profile],
        }
        with self.assertRaisesRegex(ValueError, "references unknown groups"):
            framework_profiles.validate_registry(registry)

    def test_unknown_forced_profile_is_rejected(self):
        root = make_repo({"index.html": ""})
        with self.assertRaisesRegex(ValueError, "unknown framework profile"):
            framework_profiles.match_profiles(
                root, framework_profiles.load_registry(), ["invented"])


if __name__ == "__main__":
    unittest.main()
