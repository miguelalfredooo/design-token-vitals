"""Derive and render the report's framework-aware unification strategy."""
import html
import json


STANDARDS = [
    {
        "id": "dtcg-2025.10",
        "name": "Design Tokens Format Module 2025.10",
        "url": "https://www.designtokens.org/tr/2025.10/format/",
        "role": (
            "Typed, tool-independent token interchange, aliases, groups, and "
            "deprecation metadata. Stable Community Group report intended for "
            "implementation; not a W3C Recommendation."
        ),
    },
    {
        "id": "css-custom-properties-1",
        "name": "CSS Custom Properties for Cascading Variables Level 1",
        "url": "https://www.w3.org/TR/css-variables-1/",
        "role": (
            "Runtime web projection for decisions that participate in the "
            "cascade or change by theme."
        ),
    },
    {
        "id": "wcag-2.2",
        "name": "WCAG 2.2",
        "url": "https://www.w3.org/TR/WCAG22/",
        "role": (
            "Accessibility acceptance baseline for resolved color, focus, "
            "target, text-spacing, and motion outcomes; token presence alone "
            "does not prove conformance."
        ),
    },
    {
        "id": "semver-2.0.0",
        "name": "Semantic Versioning 2.0.0",
        "url": "https://semver.org/",
        "role": (
            "Versioning and deprecation policy after the public token or "
            "component contract is declared."
        ),
    },
]

PHASE_IDS = [
    "prove-boundary",
    "freeze-identity",
    "canonical-source",
    "prove-modes",
    "migrate-by-impact",
    "enforce-and-expand",
]

CONSTRAINT_IDS = [
    "framework-ownership",
    "delivery-topology",
    "behavior-contracts",
    "runtime-modes",
    "governance-transition",
]

ACTIONABLE_UNRESOLVED_REASONS = {
    "missing local source",
    "unsupported resolver",
    "dynamic runtime import",
    "ambiguous profile rewrite",
}


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))


def _confirmed_token_definition_sources(report):
    discovered = list(
        report.get("discovery", {}).get("token_sources", []) or []
    )
    if discovered:
        return _unique(
            item.get("path")
            for item in discovered
            if isinstance(item, dict)
            and (item.get("classification") or item.get("role"))
            in {"canonical", "alias"}
        )
    return _unique(report.get("stack", {}).get("token_sources", []) or [])


def _identity_state(report, name):
    identity = report.get("inventory", {}).get("identity", {}) or {}
    return (identity.get(name, {}) or {}).get("state") or "unmeasured"


def derive(report):
    discovery = report.get("discovery", {}) or {}
    run = report.get("run", {}) or {}
    stack = report.get("stack", {}) or {}
    usage = report.get("component_usage", {}) or {}
    modes = list(report.get("declared", {}).get("modes", []) or [])
    profiles = list(discovery.get("environment", []) or [])
    adapters = list(stack.get("adapters", []) or [])
    roots = list(discovery.get("roots", []) or [])
    owned_roots = [item for item in roots if item.get("ownership") == "owned"]
    token_sources = _confirmed_token_definition_sources(report)
    unresolved = [
        item
        for item in discovery.get("import_graph", {}).get("unresolved", []) or []
        if item.get("reason") in ACTIONABLE_UNRESOLVED_REASONS
    ]
    capabilities = dict(discovery.get("capabilities", {}) or {})
    resolved_pairs = list(
        discovery.get("mode_resolution", {}).get("resolved_pairs", []) or []
    )
    component_state = usage.get("state") or "unmeasured"
    component_count = usage.get("total_components_with_token_usage")
    component_count = component_count if isinstance(component_count, int) else None
    top_components = usage.get("top_20", []) or []
    top_component = top_components[0].get("name") if top_components else None
    concepts = run.get("token_count")
    if not isinstance(concepts, int):
        inventory_concepts = report.get("inventory", {}).get("concepts", [])
        concepts = len(inventory_concepts) if isinstance(inventory_concepts, list) else None

    boundary_verified = capabilities.get("production_roots") == "verified"
    component_measured = component_state == "measured"
    model = (
        "token-led-hybrid"
        if boundary_verified and component_measured
        else "token-first-foundation"
    )
    confidence = (
        "evidence-derived"
        if capabilities.get("detection") == "verified" and boundary_verified
        else "bounded-by-discovery"
    )
    if model == "token-led-hybrid":
        headline = "Unify decisions everywhere; unify components where ownership is proven."
    else:
        headline = "Establish the token contract before consolidating components."

    concept_text = str(concepts) if concepts is not None else "an unmeasured number of"
    component_text = (
        "%d components with confirmed token usage" % component_count
        if component_count is not None
        else "component adoption that remains %s" % component_state
    )
    rationale = (
        "This run found %s canonical concepts across %d confirmed token-definition "
        "sources, "
        "%s, %d active framework profiles, and %d styling or framework adapters. "
        "A repository-wide component replacement would cross framework behavior "
        "and upgrade boundaries that this token audit does not measure. Use one "
        "semantic token contract across them, preserve framework-specific delivery "
        "adapters, and reserve shared component implementation for owned surfaces."
        % (
            concept_text,
            len(token_sources),
            component_text,
            len(profiles),
            len(adapters),
        )
    )

    capability_work = [
        name for name, state in capabilities.items() if state != "verified"
    ]
    typography_state = _identity_state(report, "typography")
    brand_state = _identity_state(report, "brand_colors")
    mode_block = discovery.get("mode_resolution", {}).get("blocked_reason")
    enforcement = report.get("vitals", {}).get("enforcement", {}) or {}
    leakage_tiers = (
        report.get("vitals", {}).get("leakage", {}).get("tiers", {}) or {}
    )

    architecture = [
        {
            "id": "canonical-contract",
            "title": "One canonical contract",
            "description": (
                "Author one typed token graph for %s concepts; generate every other "
                "representation instead of maintaining parallel sources." % concept_text
            ),
        },
        {
            "id": "semantic-layer",
            "title": "Semantic decisions",
            "description": (
                "Map primitives to product intent such as text, surface, action, "
                "focus, and status. Require components to consume semantics by default."
            ),
        },
        {
            "id": "delivery-adapters",
            "title": "Generated delivery adapters",
            "description": (
                "Project the contract through %s. Keep framework translation separate "
                "from the design decisions it carries."
                % (", ".join(adapters) if adapters else "the evidenced runtime stack")
            ),
        },
        {
            "id": "owned-components",
            "title": "Shared components for owned surfaces",
            "description": (
                "Build versioned components for new and product-owned surfaces; let "
                "existing framework components adopt the same semantic contract without "
                "requiring shared markup."
            ),
        },
        {
            "id": "governance-proof",
            "title": "Governance and proof",
            "description": (
                "Version public contracts, deprecate before removal, validate every "
                "declared mode and production bundle, and reject regressions in CI."
            ),
        },
    ]

    constraints = [
        {
            "id": CONSTRAINT_IDS[0],
            "title": "Framework and ownership boundaries",
            "evidence": (
                "%d active framework profiles; %d of %d production roots are "
                "proven owned." % (len(profiles), len(owned_roots), len(roots))
            ),
            "implication": (
                "A global component replacement can turn upstream upgrades into "
                "long-lived fork maintenance. Preserve framework-owned behavior and "
                "markup until a component-contract assessment proves a safe boundary."
            ),
        },
        {
            "id": CONSTRAINT_IDS[1],
            "title": "Multiple delivery mechanisms",
            "evidence": (
                "%d confirmed token-definition sources feed %d styling or framework "
                "adapters." % (len(token_sources), len(adapters))
            ),
            "implication": (
                "Unify the decisions in one typed graph, then generate compatible "
                "projections. Requiring every framework to share one runtime format "
                "would couple design governance to implementation history."
            ),
        },
        {
            "id": CONSTRAINT_IDS[2],
            "title": "Behavioral contracts exceed styling",
            "evidence": (
                "%s; behavior, public APIs, localization, state, analytics, "
                "authorization, and interaction accessibility remain outside this audit."
                % component_text
            ),
            "implication": (
                "Token adoption can align visual decisions without proving that shared "
                "component code is interchangeable. Assess those contracts separately "
                "before consolidation."
            ),
        },
        {
            "id": CONSTRAINT_IDS[3],
            "title": "Runtime modes need compiled proof",
            "evidence": (
                "%d modes are declared and %d bundle-by-mode pairs are resolved."
                % (len(modes), len(resolved_pairs))
            ),
            "implication": (
                "Source declarations prove intent, while compiled or runtime values "
                "prove delivery. Keep mode claims blocked until every production pair "
                "has evidence."
            ),
        },
        {
            "id": CONSTRAINT_IDS[4],
            "title": "Migration requires governance",
            "evidence": (
                "Enforcement is graded %s and %d capabilities remain blocked or "
                "unmeasured."
                % (enforcement.get("grade") or "unmeasured", len(capability_work))
            ),
            "implication": (
                "A token package alone will not stop new drift. Pair migration with "
                "ownership, versioning, deprecation, CI gates, and measurable exit "
                "criteria."
            ),
        },
    ]

    phases = [
        {
            "id": PHASE_IDS[0],
            "phase": 0,
            "title": "Prove the boundary",
            "objective": (
                "Resolve production reachability, ownership, and the evidence gaps that "
                "would make later adoption claims unreliable."
            ),
            "evidence": (
                "%d unresolved imports; %s capabilities still blocked or unmeasured."
                % (len(unresolved), len(capability_work))
            ),
            "exit_criteria": (
                "Every actionable import is resolved or explicitly exempted, production "
                "roots are proven, and remaining unknowns are named as unmeasured."
            ),
        },
        {
            "id": PHASE_IDS[1],
            "phase": 1,
            "title": "Freeze identity and semantics",
            "objective": (
                "Confirm brand identity, then define primitive, semantic, and optional "
                "component tiers with ownership and mode policies."
            ),
            "evidence": (
                "Typography identity is %s; brand color identity is %s."
                % (typography_state, brand_state)
            ),
            "exit_criteria": (
                "Every governed token has a type, description, owner, semantic role, "
                "and declared mode behavior."
            ),
        },
        {
            "id": PHASE_IDS[2],
            "phase": 2,
            "title": "Choose one source and generate adapters",
            "objective": (
                "Make one token graph authoritative and generate runtime, legacy, and "
                "framework-specific projections."
            ),
            "evidence": (
                "%s concepts currently span %d token-bearing sources and %d adapters."
                % (concept_text, len(token_sources), len(adapters))
            ),
            "exit_criteria": (
                "No projection is independently authored, aliases resolve without "
                "cycles, and primitive-to-consumer lineage is traceable."
            ),
        },
        {
            "id": PHASE_IDS[3],
            "phase": 3,
            "title": "Prove modes and bundles",
            "objective": (
                "Compile or resolve every declared mode across each production bundle "
                "and verify the resulting values, not only their source declarations."
            ),
            "evidence": (
                "%d declared modes; %d resolved bundle-by-mode pairs.%s"
                % (
                    len(modes),
                    len(resolved_pairs),
                    " %s" % mode_block if mode_block else "",
                )
            ),
            "exit_criteria": (
                "The coverage matrix contains no unexplained blocked cell and every "
                "declared mode has compiled or runtime evidence."
            ),
        },
        {
            "id": PHASE_IDS[4],
            "phase": 4,
            "title": "Migrate by impact",
            "objective": (
                "Pilot the semantic contract on the highest-usage owned component or "
                "production surface; replace only decisions whose semantic role is proven."
            ),
            "evidence": (
                "%s%s"
                % (
                    "%d measured components use tokens" % component_count
                    if component_count is not None
                    else "Component adoption is %s" % component_state,
                    "; start with %s." % top_component if top_component else ".",
                )
            ),
            "exit_criteria": (
                "The pilot passes visual, accessibility, mode, and regression checks "
                "without changing component behavior or public APIs."
            ),
        },
        {
            "id": PHASE_IDS[5],
            "phase": 5,
            "title": "Enforce and expand",
            "objective": (
                "Prevent new drift, publish deprecation rules, and expand shared "
                "components only where ownership and component contracts are proven."
            ),
            "evidence": (
                "Enforcement is graded %s; leakage baseline: %s."
                % (
                    enforcement.get("grade") or "unmeasured",
                    ", ".join(
                        "%s %s"
                        % (name, "unmeasured" if value is None else value)
                        for name, value in leakage_tiers.items()
                    ) or "unmeasured",
                )
            ),
            "exit_criteria": (
                "CI rejects invalid aliases, missing modes, inaccessible resolved pairs, "
                "unapproved literals, and public removals without deprecation."
            ),
        },
    ]

    guardrails = [
        "Keep one hand-authored source of truth; generate every projection.",
        "Consume semantic tokens by default and document every primitive exception.",
        "Treat framework adapters as translation boundaries, not parallel design systems.",
        "Prove every declared mode in compiled or runtime output before claiming coverage.",
        "Never infer that token consistency proves component behavior or accessibility.",
        "Version public contracts and deprecate before removing or renaming them.",
    ]
    success_metrics = [
        {
            "id": "source-consolidation",
            "measure": "Confirmed token-definition source files",
            "baseline": str(len(token_sources)),
            "target": (
                "one canonical authoring graph; every remaining source generated "
                "or mapped"
            ),
        },
        {
            "id": "mode-proof",
            "measure": "Resolved bundle-by-mode pairs",
            "baseline": str(len(resolved_pairs)),
            "target": "every declared mode across every production bundle",
        },
        {
            "id": "component-adoption",
            "measure": "Measured components using the contract",
            "baseline": str(component_count) if component_count is not None else component_state,
            "target": "all selected pilot components use semantic tokens",
        },
        {
            "id": "verified-leakage",
            "measure": "Semantically verified redundant literals",
            "baseline": (
                "unmeasured"
                if leakage_tiers.get("redundant") is None
                else str(leakage_tiers.get("redundant"))
            ),
            "target": "zero, with a CI rule preventing recurrence",
        },
        {
            "id": "identity-integrity",
            "measure": "Typography and brand identity",
            "baseline": "%s / %s" % (typography_state, brand_state),
            "target": "verified, visible, mode-safe, and backed by source evidence",
        },
    ]

    return {
        "schema_version": 1,
        "model": model,
        "confidence": confidence,
        "headline": headline,
        "rationale": rationale,
        "evidence": {
            "profiles": profiles,
            "adapters": adapters,
            "production_roots": len(roots),
            "owned_roots": len(owned_roots),
            "confirmed_token_definition_sources": len(token_sources),
            "canonical_concepts": concepts,
            "component_usage_state": component_state,
            "components_with_token_usage": component_count,
            "declared_modes": modes,
            "resolved_mode_pairs": len(resolved_pairs),
            "unresolved_imports": len(unresolved),
            "capabilities": capabilities,
        },
        "target_architecture": architecture,
        "integration_constraints": constraints,
        "standards": STANDARDS,
        "rollout": phases,
        "guardrails": guardrails,
        "success_metrics": success_metrics,
        "component_replacement_limit": (
            "This audit does not measure behavior, public APIs, localization, state, "
            "analytics, authorization, or interaction accessibility. Complete a separate "
            "component-contract assessment before proposing repository-wide replacement."
        ),
    }


def _esc(value):
    return html.escape(str(value), quote=True)


def _json_attr(value):
    return _esc(json.dumps(value, separators=(",", ":"), sort_keys=True))


def render(strategy):
    evidence = strategy["evidence"]
    architecture = "".join(
        '<div class="panel" data-strategy-layer="%s"><h3>%d. %s</h3>'
        '<p class="p-soft">%s</p></div>'
        % (
            _esc(item["id"]),
            index,
            _esc(item["title"]),
            _esc(item["description"]),
        )
        for index, item in enumerate(strategy["target_architecture"], 1)
    )
    constraints = "".join(
        '<div class="panel" data-strategy-constraint="%s"><h3>%s</h3>'
        '<p class="p-mute"><b>Evidence now:</b> %s</p>'
        '<p class="p-soft"><b>Implication:</b> %s</p></div>'
        % (
            _esc(item["id"]),
            _esc(item["title"]),
            _esc(item["evidence"]),
            _esc(item["implication"]),
        )
        for item in strategy["integration_constraints"]
    )
    phases = "".join(
        '<div class="panel" data-rollout-phase="%s" data-rollout-order="%d">'
        '<h3>Phase %d · %s</h3><p class="p-soft">%s</p>'
        '<p class="p-mute"><b>Evidence now:</b> %s</p>'
        '<p class="p-mute"><b>Exit when:</b> %s</p></div>'
        % (
            _esc(item["id"]),
            item["phase"],
            item["phase"],
            _esc(item["title"]),
            _esc(item["objective"]),
            _esc(item["evidence"]),
            _esc(item["exit_criteria"]),
        )
        for item in strategy["rollout"]
    )
    standards = "".join(
        '<tr data-strategy-standard="%s"><td><a href="%s">%s</a></td><td>%s</td></tr>'
        % (_esc(item["id"]), _esc(item["url"]), _esc(item["name"]), _esc(item["role"]))
        for item in strategy["standards"]
    )
    metrics = "".join(
        '<tr data-strategy-metric="%s"><td>%s</td><td>%s</td><td>%s</td></tr>'
        % (
            _esc(item["id"]),
            _esc(item["measure"]),
            _esc(item["baseline"]),
            _esc(item["target"]),
        )
        for item in strategy["success_metrics"]
    )
    guardrails = "".join("<li>%s</li>" % _esc(item) for item in strategy["guardrails"])
    profiles = "".join('<span class="chip">%s</span>' % _esc(item) for item in evidence["profiles"])
    adapters = "".join('<span class="chip">%s</span>' % _esc(item) for item in evidence["adapters"])
    concept_count = evidence["canonical_concepts"]
    component_count = evidence["components_with_token_usage"]
    return (
        '<div data-report-region="adoption-strategy" data-adoption-strategy-json="%s">'
        '<div class="stage-line"><code>%s</code> — %s</div>'
        '<p class="p-soft">%s</p>'
        '<div class="grid2 stack-16"><div class="panel"><h3>Why this model</h3>'
        '<dl class="meta"><dt>profiles</dt><dd><span class="chips">%s</span></dd>'
        '<dt>adapters</dt><dd><span class="chips">%s</span></dd>'
        '<dt>production roots</dt><dd>%d total · %d owned</dd>'
        '<dt>token inventory</dt><dd>%s concepts · %d sources</dd>'
        '<dt>component adoption</dt><dd>%s · %s</dd>'
        '<dt>modes</dt><dd>%d declared · %d resolved bundle pairs</dd>'
        '<dt>unresolved imports</dt><dd>%d</dd></dl></div>'
        '<div class="panel"><h3>Guardrails</h3><ul>%s</ul>'
        '<div class="note"><b>Component boundary:</b> %s</div></div></div>'
        '<h3 class="stack-26">Why component-first unification is risky</h3>'
        '<div class="grid2 stack-16">%s</div>'
        '<h3 class="stack-26">Target architecture</h3><div class="grid2 stack-16">%s</div>'
        '<h3 class="stack-26">Rollout plan</h3><div class="grid2 stack-16">%s</div>'
        '<h3 class="stack-26">Standards baseline</h3>'
        '<div class="tbl-scroll stack-16"><table><thead><tr><th>Reference</th><th>How to use it</th>'
        '</tr></thead><tbody>%s</tbody></table></div>'
        '<h3 class="stack-26">Success measures</h3>'
        '<div class="tbl-scroll stack-16"><table><thead><tr><th>Measure</th><th>Baseline</th>'
        '<th>Target</th></tr></thead><tbody>%s</tbody></table></div></div>'
        % (
            _json_attr(strategy),
            _esc(strategy["model"]),
            _esc(strategy["headline"]),
            _esc(strategy["rationale"]),
            profiles or '<span class="state" data-m="unmeasured">unmeasured</span>',
            adapters or '<span class="state" data-m="unmeasured">unmeasured</span>',
            evidence["production_roots"],
            evidence["owned_roots"],
            _esc(concept_count if concept_count is not None else "unmeasured"),
            evidence["confirmed_token_definition_sources"],
            _esc(component_count if component_count is not None else "unmeasured"),
            _esc(evidence["component_usage_state"]),
            len(evidence["declared_modes"]),
            evidence["resolved_mode_pairs"],
            evidence["unresolved_imports"],
            guardrails,
            _esc(strategy["component_replacement_limit"]),
            constraints,
            architecture,
            phases,
            standards,
            metrics,
        )
    )
