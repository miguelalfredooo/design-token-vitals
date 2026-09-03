# Adoption strategy

The report ends with an evidence-derived recommendation for turning the
audit into a durable system. It preserves the eight vital grades and
translates the repository's measured constraints into a target architecture,
rollout gates, and success measures.

## Recommendation models

Choose one of these models from evidence already present in the report:

- `token-led-hybrid` — use one framework-neutral token contract everywhere,
  framework adapters at delivery boundaries, and shared components only on
  surfaces the product owns. Select this when more than one framework
  profile or styling adapter is active, more than one production root ships,
  or the repository already has component adoption to migrate. This is the
  normal recommendation for a mature or extensible application.
- `token-first-foundation` — establish the canonical token contract and
  prove its delivery before recommending component consolidation. Select
  this when component usage is blocked or unmeasured, or when production
  reachability is not yet established.

Never recommend a repository-wide component replacement from a token audit.
The audit does not measure component behavior, public APIs, localization,
state, analytics, authorization, or accessibility interaction contracts. It
may recommend a shared component layer for new and product-owned surfaces,
but a component-first replacement requires a separate component-contract
assessment.

## Target architecture

Keep these layers separate:

1. **Canonical contract.** Author a single typed token graph. Prefer the
   Design Tokens Community Group format when a translation pipeline is
   available. Do not introduce JSON, Sass, CSS, or a design-tool export as a
   second hand-authored source.
2. **Semantic layer.** Map primitives to decisions such as text, surface,
   action, focus, and status. Components consume semantics by default;
   primitive use requires a documented exception.
3. **Delivery adapters.** Generate the formats each environment needs, such
   as CSS custom properties for runtime themes, Sass aliases for legacy
   consumers, and framework-specific theme inputs. Adapters translate; they
   do not own design decisions.
4. **Owned component layer.** Build and version shared components for new or
   product-owned surfaces. Do not distribute copied snippets. Existing
   framework components can adopt the semantic contract without sharing the
   same markup.
5. **Governance and proof.** Version the public contract, deprecate before
   removing, test every declared mode and production bundle, and reject
   regressions in CI.

## Why component-first unification is risky

Render five repository-evidenced constraints before the target architecture:

1. framework and ownership boundaries, including the upstream upgrade surface;
2. multiple delivery mechanisms and the cost of forcing one runtime format;
3. behavioral contracts outside a static token audit, including public APIs,
   localization, state, analytics, authorization, and interaction accessibility;
4. runtime modes that still need compiled or browser proof; and
5. the governance needed to keep migration from creating new drift.

Each constraint carries current evidence and an implication. Keep this model
framework-neutral: profiles and counts come from the report rather than a
hard-coded Discourse, React, Rails, Ember, or other platform narrative.

## Standards baseline

Render these references in every strategy section, with their roles stated
accurately:

- **Design Tokens Format Module 2025.10** — a stable Design Tokens Community
  Group report intended for implementation, but not a W3C Recommendation.
  Use it for typed, tool-independent token interchange, aliases, groups, and
  deprecation metadata. <https://www.designtokens.org/tr/2025.10/format/>
- **CSS Custom Properties for Cascading Variables Level 1** — use as the web
  runtime projection where values must participate in the cascade or change
  by theme. <https://www.w3.org/TR/css-variables-1/>
- **WCAG 2.2** — use as the accessibility acceptance baseline for resolved
  color, focus, target, text-spacing, and motion outcomes. Tokens support
  conformance; token presence alone never proves it.
  <https://www.w3.org/TR/WCAG22/>
- **Semantic Versioning 2.0.0** — use for a published token or component
  contract once its public API is declared. <https://semver.org/>

## Rollout gates

Render six phases. Tailor the evidence and exit criterion to the current run;
do not rename missing evidence as completed work.

0. **Prove the boundary.** Resolve actionable imports, ownership, production
   roots, and runtime gaps. Exit when discovery can identify what ships and
   what remains explicitly unmeasured.
1. **Freeze identity and semantics.** Confirm typography and explicit brand
   color evidence; define primitive, semantic, and optional component tiers.
   Exit when each governed token has a type, description, owner, and mode
   policy.
2. **Choose one source and generate adapters.** Establish one canonical graph
   and generate runtime and legacy projections. Exit when no projection is
   independently authored and lineage is traceable.
3. **Prove modes and bundles.** Compile or resolve every declared mode across
   every production bundle. Exit when the coverage matrix contains no
   unexplained blocked cell.
4. **Migrate by impact.** Start with the highest-usage measured component or
   production surface and replace only semantically verified decisions. Exit
   the pilot when visual, accessibility, and regression checks pass without
   changing behavior.
5. **Enforce and expand.** Add lint and CI checks for new literals, invalid
   aliases, missing modes, inaccessible resolved pairs, and removals without
   deprecation. Expand shared components only where ownership and component
   contracts are proven.

## Required evidence and parity

Store the recommendation under `adoption_strategy` in `report.json` and
duplicate it in the final HTML section. Include:

- model, confidence, headline, and rationale;
- the exact profiles, adapters, roots, confirmed canonical-or-alias token
  definition sources, concepts, component count, modes, unresolved imports,
  and capability states used to choose it;
- five ordered integration constraints with current evidence and implications;
- target architecture layers;
- standards with URLs and roles;
- six ordered rollout phases with exit criteria and repository evidence;
- guardrails and measurable outcomes.

Validation must fail when the strategy is absent, when its evidence drifts
from the report, when phases are missing or reordered, when a standard URL is
changed, or when the HTML omits any of the structured JSON.
