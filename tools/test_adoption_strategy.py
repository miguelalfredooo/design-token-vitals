import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adoption_strategy  # noqa: E402
import validate_run  # noqa: E402


def report_fixture(component_state="measured"):
    return {
        "run": {"token_count": 24},
        "stack": {
            "adapters": ["css-vars", "scss"],
            "token_sources": ["tokens.scss", "tokens.css"],
        },
        "declared": {"modes": ["light", "dark"]},
        "discovery": {
            "engine": {"name": "universal-profile-engine"},
            "environment": ["rails-sprockets", "ember"],
            "capabilities": {
                "detection": "verified",
                "production_roots": "verified",
                "import_resolution": "blocked",
                "token_source_discovery": "verified",
                "ownership": "verified",
                "mode_resolution": "blocked",
                "runtime_verification": "unmeasured",
            },
            "roots": [
                {"path": "app.scss", "ownership": "owned"},
                {"path": "admin.scss", "ownership": "unknown"},
            ],
            "import_graph": {
                "unresolved": [
                    {
                        "from": "app.scss",
                        "spec": "theme",
                        "reason": "dynamic runtime import",
                    },
                    {
                        "from": "app.scss",
                        "spec": "ember-source",
                        "reason": "external package",
                    },
                ]
            },
            "mode_resolution": {
                "resolved_pairs": [{"bundle": "app", "mode": "light"}],
                "blocked_reason": "dark output was not supplied.",
            },
        },
        "inventory": {
            "identity": {
                "typography": {"state": "verified"},
                "brand_colors": {"state": "verified"},
            }
        },
        "component_usage": {
            "state": component_state,
            "total_components_with_token_usage": 8 if component_state == "measured" else None,
            "top_20": (
                [{"name": "product / card"}] if component_state == "measured" else []
            ),
        },
        "vitals": {
            "enforcement": {"grade": "blocked"},
            "leakage": {
                "tiers": {
                    "redundant": 3,
                    "exact-value candidate": 4,
                    "near-miss": 1,
                    "uncovered": 2,
                }
            },
        },
    }


class TestDerive(unittest.TestCase):
    def test_recommends_hybrid_from_verified_boundary_and_component_measurement(self):
        strategy = adoption_strategy.derive(report_fixture())

        self.assertEqual(strategy["model"], "token-led-hybrid")
        self.assertEqual(
            strategy["evidence"]["confirmed_token_definition_sources"], 2
        )
        self.assertEqual(strategy["evidence"]["components_with_token_usage"], 8)
        self.assertEqual(strategy["evidence"]["unresolved_imports"], 1)
        self.assertEqual(
            [item["id"] for item in strategy["rollout"]],
            adoption_strategy.PHASE_IDS,
        )
        self.assertIn("product / card", strategy["rollout"][4]["evidence"])

    def test_holds_component_consolidation_when_adoption_is_unmeasured(self):
        strategy = adoption_strategy.derive(report_fixture("unmeasured"))

        self.assertEqual(strategy["model"], "token-first-foundation")
        self.assertIn("unmeasured", strategy["rollout"][4]["evidence"])

    def test_renders_unmeasured_leakage_without_python_none(self):
        report = report_fixture()
        report["vitals"]["leakage"]["tiers"]["redundant"] = None

        strategy = adoption_strategy.derive(report)

        self.assertNotIn("None", strategy["rollout"][5]["evidence"])
        self.assertEqual(strategy["success_metrics"][3]["baseline"], "unmeasured")

    def test_current_discovery_evidence_wins_over_stale_stack_sources(self):
        report = report_fixture()
        report["stack"]["token_sources"].append("stale-candidate.scss")
        report["discovery"]["token_sources"] = [
            {"path": "tokens.scss", "classification": "canonical"},
            {"path": "aliases.scss", "classification": "alias"},
            {"path": "stale-candidate.scss", "classification": "consumer"},
        ]

        strategy = adoption_strategy.derive(report)

        self.assertEqual(
            strategy["evidence"]["confirmed_token_definition_sources"], 2
        )

    def test_renders_every_structured_section(self):
        strategy = adoption_strategy.derive(report_fixture())
        rendered = adoption_strategy.render(strategy)

        self.assertIn('data-adoption-strategy-json="', rendered)
        for phase_id in adoption_strategy.PHASE_IDS:
            self.assertIn('data-rollout-phase="%s"' % phase_id, rendered)
        for constraint_id in adoption_strategy.CONSTRAINT_IDS:
            self.assertIn(
                'data-strategy-constraint="%s"' % constraint_id, rendered
            )
        for standard in adoption_strategy.STANDARDS:
            self.assertIn('href="%s"' % standard["url"], rendered)


class TestStrategyValidation(unittest.TestCase):
    def test_matching_strategy_and_html_pass(self):
        report = report_fixture()
        strategy = adoption_strategy.derive(report)
        report["adoption_strategy"] = strategy
        document = (
            '<html><body><section id="strategy">%s</section><footer></footer></body></html>'
            % adoption_strategy.render(strategy)
        )

        self.assertIsNone(validate_run.rule_17_adoption_strategy(report, document))

    def test_stale_strategy_fails(self):
        report = report_fixture()
        report["adoption_strategy"] = adoption_strategy.derive(report)
        report["adoption_strategy"]["evidence"][
            "confirmed_token_definition_sources"
        ] = 99

        failure = validate_run.rule_17_adoption_strategy(report)

        self.assertEqual(failure.rule, "17-adoption-strategy")
        self.assertIn("does not match", failure.detail[0])

    def test_missing_phase_fails(self):
        report = report_fixture()
        report["adoption_strategy"] = adoption_strategy.derive(report)
        report["adoption_strategy"]["rollout"].pop()

        failure = validate_run.rule_17_adoption_strategy(report)

        self.assertTrue(any("phases" in detail for detail in failure.detail))


class TestStrategyProseCounts(unittest.TestCase):
    """A count of one must read as one.

    This section is written for a stakeholder, and "1 components with
    confirmed token usage" is the sentence a reader stops at. Small repos
    and early runs hit the singular constantly.
    """

    def singular_report(self):
        report = report_fixture()
        report["stack"]["adapters"] = ["css-vars"]
        report["stack"]["token_sources"] = ["tokens.css"]
        report["discovery"]["environment"] = ["vite"]
        report["discovery"]["roots"] = [{"path": "app.css", "ownership": "owned"}]
        report["component_usage"]["total_components_with_token_usage"] = 1
        report["component_usage"]["top_20"] = [{"name": "src / Button"}]
        return report

    def test_no_plural_noun_follows_a_count_of_one(self):
        strategy = adoption_strategy.derive(self.singular_report())
        prose = " ".join(
            [strategy["rationale"], strategy["headline"]]
            + [item["evidence"] for item in strategy["integration_constraints"]]
            + [item["evidence"] for item in strategy["rollout"]]
            + [item["description"] for item in strategy["target_architecture"]]
        )
        for phrase in ("1 components", "1 profiles", "1 adapters", "1 sources",
                       "1 concepts", "1 roots", "1 modes", "1 pairs", "1 imports"):
            self.assertNotIn(phrase, prose, "%r reads as a plural" % phrase)


if __name__ == "__main__":
    unittest.main()
