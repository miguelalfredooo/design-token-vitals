#!/usr/bin/env python3
"""A small made-up report: the template's sample content, and a test fixture.

`assets/report-template.html` shows sample findings so a contributor can open
it and see the page. Those samples were drawn by running the real renderers
over this report, so the template cannot show a shape the code no longer
makes. `test_report_shape.py` renders the same report and holds the page to
its rules.

Every name here is one of the tell-tale strings the gate looks for
(`northwind-ds`, `acme-storefront`), so sample content left in a finished
report is caught.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unlock_path  # noqa: E402


def build():
    V = {
     "tier-integrity": {"grade": "watch", "evidence": ["acme-storefront/src/Card.css:14"],
        "note": "Four files reach past the semantic layer to a primitive.",
        "measure": {"form": "threshold", "value": 3.1, "max": 10, "unit": "%", "part": 4, "whole": 128,
                    "noun": "files that use a token", "lines": [{"at": 5, "label": "Fix above"}],
                    "means": "A few files skip the role and use the raw color. Still under the line."}},
     "leakage": {"grade": "not-visible", "evidence": [], "note": "Two hardcoded colors match a token; we can't yet say they mean the same thing.", "tiers": {}},
     "coverage": {"grade": "healthy", "evidence": ["northwind-ds/tokens/color.primitive.json:1"],
        "note": "Every kind of decision has a token of its own.",
        "measure": {"form": "cells", "part": 11, "whole": 11, "noun": "categories", "means": "Nothing falls back to a framework default."}},
     "mode-completeness": {"grade": "not-visible", "evidence": [], "note": "Your themes are built at runtime, so there was no output to read."},
     "naming-coherence": {"grade": "healthy", "evidence": ["northwind-ds/tokens/color.semantic.json:3"], "note": "One naming pattern throughout.",
        "measure": {"form": "cells", "part": 1, "whole": 1, "noun": "naming pattern", "means": "Every name follows the same shape."}},
     "single-source": {"grade": "needs-work", "evidence": ["acme-storefront/src/button.css:40", "acme-storefront/src/button.css:118"],
        "headline": "The button's hover color is set twice, so the first value never ships.",
        "fix": "Keep one declaration and delete the other.", "where": "acme-storefront/src/button.css:118",
        "declarations": [{"location": "acme-storefront/src/button.css:40", "code": "--button-hover: #0F8A83;", "wins": False},
                         {"location": "acme-storefront/src/button.css:118", "code": "--button-hover: #0B7285;", "wins": True}],
        "note": "One token is set twice in the same selector, with different values."},
     "orphans": {"grade": "watch", "evidence": ["northwind-ds/tokens/color.component.json:88"],
        "note": "A handful of tokens are declared and never used.",
        "measure": {"form": "dots", "part": 9, "whole": 240, "noun": "tokens", "means": "Safe to remove once you confirm the list."},
        "candidates": [{"token": "color.semantic.brand.base", "family": "color", "site": "northwind-ds/tokens/color.semantic.json:12"}]},
     "enforcement": {"grade": "healthy", "evidence": ["acme-storefront/.github/workflows/ci.yml:31"], "note": "Two checks read tokens on every pull request.",
        "measure": {"form": "cells", "part": 2, "whole": 2, "noun": "automatic checks", "means": "Both run before a change can merge."}},
    }
    bundles = ["acme-storefront (app/layout.tsx)"]
    fams = ["color", "typography", "spacing", "radius"]
    cells = []
    for m in ("light", "dark"):
        for f in fams:
            cells.append({"bundle": bundles[0], "mode": m, "family": f,
                          "state": "not-visible" if f == "color" else ("counted" if m == "light" else "not-needed"),
                          "evidence": [], "note": "sample"})
    R = {
      "schema_version": 2,
      "provenance": {"adapter_versions": {"dtcg": "0.0.0", "tailwind": "0.0.0"}, "skill_version": "0.0.0"},
      "run": {"token_count": 240, "family_count": 11, "files_scanned": 96, "token_consumer_files": 128,
              "generated_at": "2026-01-01T00:00:00Z", "repo_ref": "7f0c22ab",
              "framework_versions": {"tailwindcss": "4.3.0"},
              "scope": ["src/**/*.{ts,tsx}", "excluded: dist/, node_modules/"]},
      "declared": {"modes": ["light", "dark"]},
      "stage": {"current": "declared", "next": "adopted", "threshold": "Decide what the 2 matching colors are", "already_met": ["tokens live in one place"]},
      "freshness": {"dirty": False, "commits_since": 2},
      "executive_summary": {"highest_impact": {"finding_id": "a91f4c07", "statement": "", "blast_radius": "every primary button in acme-storefront"},
                            "affected": {"owned_files": 96, "components": 31}, "fix_first": {}, "confidence_split": {}},
      "vitals": V,
      "decisions": [
        {"decision": "Counted only tokens whose name says primitive as a skipped layer. Four files use one.", "moved": "Tier integrity stays under the line.",
         "other_reading": "Counting every raw-value token puts 40 files past the line.", "vitals": ["tier-integrity"], "other_grade": "needs-work"},
        {"decision": "Left the docs site out of the run.", "moved": "Every count is smaller.", "other_reading": "Including it was not tried.", "vitals": []},
      ],
      "fix_queue": [], "groups": {},
      "leakage_analysis": {"consumer_files_scanned": 96,
         "exact_value_candidates": [{"id": "a91f4c07", "tier": "exact-value-candidate", "literal": "#0F8A83", "token_candidates": ["color.semantic.brand.base"],
              "locations": ["acme-storefront/src/Card.css:14", "acme-storefront/src/Card.css:22"], "occurrences": 2, "files": 1, "properties": ["background"]}],
         "uncovered_candidates": [{"id": "b17c22de", "tier": "uncovered-candidate", "literal": "#1F2933", "token_candidates": [],
              "locations": ["acme-storefront/src/Nav.css:9"], "occurrences": 1, "files": 1, "properties": ["color"]}]},
      "lineage": [{"token": "color.semantic.brand.base", "tier": "semantic", "complete": True, "consumers": [{"component": "Button"}],
                   "hops": [{}, {}], "root": {"token": "color.primitive.teal.600", "site": "northwind-ds/tokens/color.primitive.json:40"}, "stops_at": None, "note": None}],
      "token_chains": {"summary": {"traced_to_a_primitive": 226, "stops_before_a_primitive": 14},
                       "fully_traceable_families": ["color", "radius"],
                       "blast_radius": [{"token": "color.semantic.brand.base", "tier": "semantic", "component_count": 12, "dependent_tokens": ["a", "b"], "components": ["Button", "Card", "Nav"]},
                                        {"token": "motion.ease.emphasized", "tier": "primitive", "component_count": 5, "dependent_tokens": [], "components": ["Modal", "Toast"]}]},
      "coverage_matrix": {"bundles": bundles, "modes": ["light", "dark"], "families": fams, "cells": cells},
      "rendering": {"tier": "collapsed", "forms": {"color": "swatches", "leaks": "rows"}},
      "discovery": {"repository": {"root": "/work/northwind-ds", "ref": "7f0c22ab"},
          "environment": ["nextjs"],
          "roots": [{"path": "app/layout.tsx", "ownership": "owned"}],
          "owned_import_graph": {"reachable": {str(i): 1 for i in range(1645)}},
          "import_graph": {"reachable": {}, "unresolved": []},
          "ownership": {"owned_patterns": ["src/**"]},
          "capabilities": {},
          "mode_resolution": {"audited_pairs": [{"bundle": bundles[0], "mode": "light"}, {"bundle": bundles[0], "mode": "dark"}],
                              "resolved_pairs": [], "blocked_reason": "Your themes are built at runtime, so there was no compiled output to read."}},
      "inventory": {"candidate_or_local_override_sources": []},
      "component_usage": {"files_scanned": 412},
    }
    caps = {"detection": "verified", "production_roots": "verified", "import_resolution": "not-visible",
            "token_source_discovery": "verified", "ownership": "verified", "mode_resolution": "not-visible", "framework_versions": "verified"}
    R["confidence"] = unlock_path.build(R, caps, None, R["discovery"])
    return R
