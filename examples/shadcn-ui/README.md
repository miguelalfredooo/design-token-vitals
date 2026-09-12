# Worked example: shadcn-ui/ui

A real run of `design-token-vitals` against a public repository, so every
finding here is independently checkable.

- **Subject:** https://github.com/shadcn-ui/ui
- **Commit:** `63c1308` (`63c1308d112b6b1205d86244a156cca1abef5087`)
- **Adapters:** `tailwind` + `css-vars` — Tailwind v4's `@theme inline`
  block (`apps/v4/app/globals.css:44`) sits on top of a `:root` block
  (line 99), so both ran and their findings merged.
- **List size:** `summary` (1,197 concepts, over the 600 threshold)
- **Skill version:** `0.1.0+11dad8f`

> **This run is unaided.** Nothing in `report.json` was hand-scoped,
> hand-collapsed or hand-corrected. Earlier versions of this example were
> curated — projections collapsed by hand, a token count narrowed from 1,197
> to 40 by judgment — which made them a better argument and an unreproducible
> artifact. Everything below comes from the commands in the next section, and
> anybody can run them and get this file.

## Reproducing it

```bash
git clone https://github.com/shadcn-ui/ui.git /tmp/shadcn-audit/repo
git -C /tmp/shadcn-audit/repo checkout 63c1308d112b6b1205d86244a156cca1abef5087
R=/tmp/shadcn-audit/repo; O=/tmp/shadcn-audit/out; mkdir -p $O

python3 tools/discover_environment.py    $R --json $O/discovery.json
python3 tools/discover_tokens.py         $R --discovery $O/discovery.json --update-discovery --json $O/tokens.json
python3 tools/analyze_component_usage.py $R --discovery $O/discovery.json --tokens $O/tokens.json --json $O/components.json
python3 tools/audit_literal_colors.py    $R --discovery $O/discovery.json --tokens $O/tokens.json --json $O/leakage.json
python3 tools/lineage_map.py                --tokens $O/tokens.json --components $O/components.json --json $O/lineage.json
python3 tools/unlock_path.py             $O/report.json --discovery $O/discovery.json --json $O/unlock.json
```

The repository root is `/tmp/shadcn-audit/repo` rather than a home
directory on purpose: the path is recorded in `report.json`, and a published
artifact should not carry somebody's username.

## What the run says

```
3 healthy · 1 to fix in your code · 4 the audit cannot see yet · 0 not needed
```

That split is the point of the report. **Four of the eight checks are
waiting on what this run could see, not on anything wrong with shadcn-ui/ui**,
and one unfollowed dynamic import is most of the reason.

| Check | Rating | One line |
|---|---|---|
| Leakage | **healthy** | 13 owned consumer stylesheets scanned. Zero redundant, zero exact-value candidates, and semantic equivalence measured with none found. One uncovered literal remains. |
| Naming coherence | **healthy** | One grammar per syntax: 679 kebab-case and 500 single-word names in CSS and JSON, and the 6 camelCase names are JS object keys, which cannot hold a hyphen. |
| Orphans | **healthy** | 1 of 69 stylesheets (1.45%) holds declarations no owned entry reaches — `apps/v4/public/r/themes.css`, a generated registry artifact that is served rather than imported. |
| Coverage | watch | 9 of 11 categories resolve to a real token, verified against `tailwindcss@4.3.0` as pinned in `pnpm-lock.yaml`. z-index and opacity do not: Tailwind v4 ships no theme namespace for either. |
| Tier integrity | not-visible | See below — this repository has no distinct primitive layer to skip. |
| Single source | not-visible | See below — 103 multi-valued concepts, and this run cannot tell a variant from a duplicate. |
| Mode completeness | not-visible | Two modes declared with real mechanisms (`@custom-variant dark` at globals.css:41, `.dark` at :143), but no resolved output was inspected for either. |
| Enforcement | not-visible | No rule reads the token layer. `pnpm lint` is ESLint; there is no stylelint config and no token-aware rule. |

The one thing to fix in the codebase: **`#000000` appears 24 times in
`packages/shadcn/src/tailwind.css`** with no matching token. That file is the
CLI's own shipped starter, copied verbatim into every project `shadcn init`
scaffolds.

## Two limitations of the tool that this run exposed

Neither is a finding about shadcn-ui/ui. Both are reasons a check reads
`not-visible` here, and both are honest refusals rather than gaps in the
data.

**1. Tier integrity needs a primitive layer to exist.** `--primary` is a
role name holding a concrete value (`globals.css:107` light, `:150` dark).
Discovery classifies a concrete value with no reference as `primitive`, so
59 of 101 component token references "reach a primitive". That number
measures the *absence of a separate primitive layer*, not components
bypassing a semantic one. Grading it would report a finding the evidence
does not support.

**2. Single source cannot separate a variant from a duplicate.** 103
concepts carry more than one value. 32 are one `:root` value and one `.dark`
value in `globals.css` — a mode pair. 58 more are in `registry/themes.ts`,
which declares roughly ten selectable themes, and 6 in the legacy
base-color registries do the same. Grading duplication here would report a
design intent as a defect. The `conflicts` array in `report.json` lists all
103 with their definition sites, which is what a person needs to tell them
apart.

## Why the token count is 1,197 and not 40

`discover_tokens.py` is deliberately maximal: it inventories everything
reachable from an owned production entry point and leaves the "is this
actually your design-token system" judgment to the reader. A large part of
the count is gallery content — `registry/themes.ts` (roughly ten alternate
theme presets), and the legacy color registries feeding the `/colors`
documentation page. They are real, reachable, and they are content the docs
site *displays about* design systems rather than the system it uses.

Earlier versions of this example made that call by hand and reported 40. This one reports what the run measured and names every source in
`report.json`'s `sources` array, so the reader can make the same call with
the evidence in front of them instead of taking it on trust.

## Validating it yourself

```bash
python3 tools/validate_run.py examples/shadcn-ui/report.json --html examples/shadcn-ui/report.html
```

All nineteen rules hold. Add `--current-skill` and it will fail on the skill
version, because the report is stamped with the commit it was generated
against and `HEAD` has moved since — committing the report is itself a new
commit. That is why CI does not gate this file, and why the version above is
the honest record of what produced it rather than a number kept in sync by
hand.

## Two bugs this regeneration found

Running the whole pipeline end to end against a second repository found two
defects that unit tests had not, both now fixed:

- The `#confidence` section was added to the report template and never
  registered in `REPORT_VIEW_SECTIONS`, so every report carrying it failed
  rule 6. No test rendered a full report and validated it.
- `sync_leakage` hardcoded `redundant: None` whatever the audit reported,
  which silently defeated the "measured, none found" result that exists
  precisely so a clean repository can grade `leakage` at all.

That is the argument for keeping a worked example: it is the only thing in
the repository that exercises the whole shape at once.
