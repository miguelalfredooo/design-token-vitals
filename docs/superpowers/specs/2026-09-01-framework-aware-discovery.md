# Framework-aware token discovery — design

**Date:** 2026-09-01
**Status:** implemented — framework-aware discovery, environment adapters, component-usage and literal-color analysis wave (2026-09-01)
**Supersedes:** the "one file, 20 declarations" detection rule in
`references/adapters/css-vars.md` and `references/adapters/scss.md`, and
Stage 1 as written in `references/discovery.md`

---

## The problem

The skill decides what a codebase's tokens are by matching a filename and a
declaration count. `css-vars.md` says a `.css` file becomes your token
source once it holds 20 or more `--` declarations in a single `:root`, and
notes that "most repositories keep these in one file." `scss.md` says the
same for `$` variables and `_?(tokens|variables|theme)`.

That works on a repository shaped like the example it was written against,
and it fails in three ways everywhere else:

- **It picks one file and stops.** A system whose color lives in
  `_colors.scss`, whose type scale lives in a JS theme object, and whose
  spacing comes from a Style Dictionary JSON gets graded on whichever one
  matched first.
- **It cannot tell a definition from a projection.** A SCSS variable and
  the custom property it compiles into are one token concept counted twice.
- **It never asks whether the file ships.** A token file nothing imports
  grades exactly the same as the one every page loads.

Two blind runs against shadcn-ui/ui on 2026-09-01 agreed on all eight
grades and disagreed on `files_scanned` (3,686 against 3,400) and
`family_count` (13 against 24), because both are derived in prose from a
scope each run reasoned out separately. The grades survived. The
measurements underneath them did not.

## The principle

**Discover sources from evidence, and prove they ship before grading them.**

A token source earns its place in the inventory by being reachable from an
entry point this project owns and ships. Everything else is a candidate,
and a candidate gets reported as a candidate.

## What changes

### 1. A required discovery stage, before any counting

Framework detection, candidate discovery, reachability, and classification
all happen before inventory or grading. The stage records what it detected,
what proved it, and its confidence, in both the HTML report and the JSON.

### 2. Discover every candidate source, never one filename

Search for all of these, and record each hit with its path and what
matched:

- CSS custom-property declarations and `@property` registrations
- SCSS, Sass, and Less variables, maps, mixins, and `@forward` exports
- JavaScript and TypeScript token objects and theme configuration
- JSON token files: DTCG, Style Dictionary, Tokens Studio exports
- every foundational family in `references/token-taxonomy.md`

### 3. Build an import graph from owned production entry points

Find the roots the framework actually registers — build entry points,
asset-registration calls, stylesheet bundle roots — and traverse imports
from each. Cover the common, desktop, mobile, theme, plugin, component and
route-specific bundles a framework registers separately.

A candidate becomes an **active source** when it is reachable from an owned
production entry point. Otherwise it is reported as unverified or orphaned
source material, and it is never silently inventoried as if it shipped.

Templates, routes and page registrations are supplemental evidence only,
for conditional, route-specific, component-specific or lazily loaded
styles. Template discovery alone never proves production inclusion.

### 4. Classify every source

Five classes, recorded per source:

| Class | Meaning |
|---|---|
| `canonical` | The definition. The value originates here |
| `alias` | A semantic or projected restatement of a canonical token |
| `consumer` | Uses tokens rather than defining them |
| `generated` | Build output; the source that produced it is what to grade |
| `unverified` | A candidate with no path to an owned entry point |

### 5. Deduplicate projections into one token concept

A SCSS variable and the custom property it emits are one concept. Collapse
them, keep every source location, and record the alias relationship. The
token count counts concepts; the source list keeps every site.

### 6. Scope leakage to owned, reachable consumer styles

Exclude vendor, generated, test, framework-default and third-party code
unless the user asks for them. State the exact scope and the file count it
resolves to.

### 7. Gate mode completeness on resolved output

Discover every registered theme scheme and token override root. Grade
`mode-completeness` only where compiled or resolved output exists for every
audited scheme. Otherwise `blocked`, naming the missing artifact. A source
declaration never implies a pass.

### 8. Measured and unmeasured are different states

A category the run could not measure renders as unmeasured, with what is
missing. Rendering it as zero, or as a pass, tells the reader the opposite
of the truth. The import-graph evidence and the source classification go
into both the HTML and the JSON.

### 9. Adapters describe where to look, and there is a fallback

An adapter defines entry points, import conventions, token conventions and
mode behavior for a framework. It never hard-codes a token filename. A
generic adapter covers anything unmatched, so an unknown framework degrades
to evidence-based discovery rather than to a guess.

## Foundational token families

`references/token-taxonomy.md` is the canonical list, drawn from what the
major design systems treat as foundations. Discovery searches for every
family in it, and the report says which were measured and which were not.

Color, typography, spacing, sizing, radius, border, elevation, opacity,
layer, motion, breakpoint, grid and layout including columns and gutters,
focus, target size, state, iconography, aspect ratio, blur, and density.

## Validation rules

An audit fails when it:

1. uses one presumed token file with no discovery evidence
2. inventories a source with no path to an owned production import root
3. claims complete mode coverage without resolved output for every scheme
4. reports zero for an unmeasured category
5. omits typography or any foundational family from the taxonomy
6. truncates findings in the HTML while the JSON holds more

These run as an executable gate, `tools/validate_run.py`, against
`report.json`, rather than as prose the agent checks itself against. The
same mechanism that let scope drift between two runs is the reason.

## Decisions taken

- **The import graph and the validation rules are both executable.**
  `tools/import_graph.py` traverses entry points and emits reachability;
  `tools/validate_run.py` exits non-zero on any rule above. The agent still
  judges; scope and reachability stop being re-derived per run.
- **The Discourse adapter is held for a follow-up.** The specifics — plugin
  asset registration, core stylesheet bundle roots, `common.scss`,
  `desktop.scss`, `mobile.scss`, theme color definitions,
  `dark-light-choose()`, `schemeType()` — are recorded here, and the
  adapter gets written against a real checkout rather than from memory.

## Expected consequence

More runs will grade `blocked`, and some categories that read as passing
will read as unmeasured. That is the point: today a category nothing
measured is indistinguishable from a category with nothing wrong.
