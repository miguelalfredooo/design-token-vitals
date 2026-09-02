# Worked example: shadcn-ui/ui

A real run of `design-token-vitals` against a public repository, so every
finding here is independently checkable.

- **Subject:** https://github.com/shadcn-ui/ui
- **Commit:** `63c1308` (`63c1308d112b6b1205d86244a156cca1abef5087`) — the
  same commit the original run of this example graded, so the two runs can
  be compared on methodology rather than on a moving target.
- **Run date:** 2026-09-02, against the framework-aware-discovery wave (the
  skill's tools changed substantially between the two runs — see below).
- **Adapter detected:** `tailwind` + `css-vars` — Tailwind v4's `@theme
  inline` block (`apps/v4/app/globals.css:44`) sits directly on top of a
  `:root` block (line 99), so both adapters ran and their findings were
  merged, as `references/adapters/tailwind.md` directs.
- **Rendering tier:** `full` (40 tokens, under the 150-token threshold)
- **Skill version:** `0.1.0+e6e427e`

## Why this run looks different from the last one

The original example predates `docs/superpowers/specs/2026-09-01-framework-aware-discovery.md`.
Its Stage 1 matched one filename heuristic (a `.css` file with 20+ `--`
declarations in one `:root`) and stopped. This run's Stage 1 is the new
required discovery pipeline — `discover_environment.py`, `discover_tokens.py`,
`analyze_component_usage.py`, `audit_literal_colors.py` — which discovers
*every* candidate source, proves reachability from an owned production entry
point, and classifies each one before anything is graded. Pointed at this
same repository, it found something the old heuristic structurally could not
have seen.

## The scope decision this run had to make

`discover_tokens.py`, run with no further scoping, reported **1,185
canonical concepts** — not because the tool is wrong, but because it is
deliberately maximal: it inventories everything reachable from an owned
entry point and leaves the "is this actually your design-token system"
judgment to the reader. Tracing the count down: **2,152 of those
declarations come from three files that are gallery/reference *content*, not
the site's own applied token system**:

- `apps/v4/registry/_legacy-base-colors.ts` (1,113 decls) and
  `apps/v4/registry/_legacy-colors.ts` (1,200 decls) — a full Tailwind/Radix
  color-shade reference catalog feeding the `/colors` documentation page.
- `apps/v4/registry/themes.ts` (840 decls) — roughly ten selectable
  *alternate* theme presets, each redeclaring the same ~40 semantic names
  with different values, feeding the theme-preview gallery pages.
- `apps/v4/app/legacy-themes.css` (439 decls) — compiled CSS output of
  legacy theme previews, same family.

These are real and reachable — a stricter reading of "discover every
candidate, prove it ships" would inventory them as canonical sources just
like `globals.css`. This run excluded them instead, on the same reasoning
the original run used to exclude the CLI's test fixtures and starter
templates: they are content the docs site *displays about* design systems,
not content that *is* the docs site's design system. The project's own
applied token layer is still `apps/v4/app/globals.css`'s `:root` / `.dark` /
`@theme inline` blocks — the same file the original run graded. Full
reasoning, and three further scope calls this run made, are in
`report.json`'s `decisions` array and rendered in the report's own
**Decisions** section.

## Two tool limitations this run found and corrected by hand

1. **`@theme inline` alias-doubling.** Tailwind v4's own idiom is to
   redeclare every semantic color under a `--color-` prefix so utility
   classes generate (`--primary` in `:root`, `--color-primary: var(--primary)`
   in `@theme inline`). The projection-collapse rule in the discovery design
   spec explicitly covers SCSS-to-CSS-custom-property compilation, but not
   yet this CSS-var-to-CSS-var pattern — so a raw run of `discover_tokens.py`
   counts 93 concepts in `globals.css` alone, roughly double-counting the
   real system. This run collapsed those projections by hand before
   reporting `run.token_count`.
2. **JS-object-shape false positives.** The conservative JS/TS theme-object
   extractor picked up 20 "canonical" concepts outside `globals.css` — but
   inspecting them, they're OpenGraph image pixel dimensions, a favicon file
   path, PWA `theme-color` meta values, and internal property names inside a
   custom font-loader's metadata records. None is a name a component author
   would type in place of a value. The extractor currently has no shape
   heuristic to tell a real token map from an arbitrary data object.

Neither is a finding about shadcn-ui/ui — both are logged as decisions so a
maintainer of this skill can find them without re-deriving this run.

## The eight vitals

| Vital | Grade | One line |
|---|---|---|
| Tier integrity | Attention | 10 of 485 files (2.1%) in `registry/new-york-v4` use a raw Tailwind palette color where a token already covers the case — all ten are `examples/*` files intentionally demoing arbitrary colors, not core chrome. |
| Leakage | **Pass** | Zero redundant and zero exact-value-candidate findings across 13 scanned consumer stylesheets — the mechanical grade `references/vitals.md` specifies. Two real `uncovered` findings still exist (see below) and near-miss stayed unmeasured; they don't move this grade, but they are not hidden either. |
| Coverage | Attention | 9 of 11 categories resolve to a real token (project or Tailwind v4 4.3.0's own default). z-index and opacity do not — Tailwind v4 ships no default scale for either. |
| Mode completeness | Pass | Zero gaps across every color-family token between `:root` (globals.css:99) and `.dark` (globals.css:143). `--radius` is deliberately excluded as geometry, same call the original run made. |
| Naming coherence | Pass | One grammar throughout the 40 canonical tokens: a kebab-case role name, optionally paired with `-foreground`. |
| Single source of truth | **Pass** | Within the declared scope, every one of the 40 canonical tokens has exactly one definition site. This changed from the original run's `attention` because the catalog-file scope decision above moved the chart-palette duplication it found out of the graded system. |
| Orphans | Pass | All 40 canonical tokens (plus the aliases built on them) trace to real usage, found by combining a Tailwind-utility-class search with a direct `var()`/pseudo-selector search — four names looked orphaned under the first search alone and were not. |
| Enforcement | Blocked | No lint rule or CI gate in the repository reads the token layer. |

Full evidence — every `file:line`, every decision, the fix-first action, and
the component-usage ranking — is in [`report.json`](./report.json) and
rendered in [`report.html`](./report.html).

**The two real, actionable findings**, not automatable (both `uncovered`, so
neither has a canonical replacement to swap in — a person decides these, not
a script):

- `#000000` × 24 in `packages/shadcn/src/tailwind.css` — the CLI's own
  shipped starter file, copied verbatim into every project `shadcn init`
  scaffolds.
- `#378ADD` × 3, one literal shared across
  `registry/new-york-v4/examples/{aria,base,radix}/shimmer-color.tsx:7` — a
  Tailwind bracket-arbitrary class (`shimmer-color-[#378ADD]`) the generic
  leakage scanner does not check at all (it scans CSS files, not `.tsx`
  bracket-arbitrary syntax); found by an agent grep against
  `references/adapters/tailwind.md`'s guidance, not by an automated tool.

**Also found and left unreviewed, honestly:** 214 further Tailwind
bracket-arbitrary `px`/`rem` literals across `registry/new-york-v4` — a real
count from a real grep, not individually checked against the near-miss
threshold in `references/leakage.md`. Reported as an open item rather than
graded either way.

## Scope

Unchanged from the original run: `apps/v4` (the real Next.js application,
its `registry/new-york-v4` component source, and the `app/globals.css` token
layer), excluding `packages/shadcn/test/fixtures/**` and `templates/**` as
CLI test scaffolding, not this repository's own consuming code.

## What this says, and what it does not

This describes commit `63c1308` and nothing else. shadcn-ui/ui is under
active development; a later commit can move any of these grades in either
direction. Nothing here is a statement about the project's overall quality
— it is eight specific, evidenced checks against one snapshot of one
directory tree, run through a pipeline that is itself still evolving (see
the two tool limitations above).

A reader can re-run this and check every number:

```bash
git clone --filter=blob:none https://github.com/shadcn-ui/ui.git && cd ui && git checkout 63c1308
```

Then follow `SKILL.md` by hand against `apps/v4` in the cloned tree, the
same way this run did.
