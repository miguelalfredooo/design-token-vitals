# The fixture repository

A small codebase with a known token layer, and `expected.json` recording
what a correct run must find. Every number in that file is derivable from
these files by hand.

The skill ships 344 tests for its tools and, before this, none for itself.
Every rule in `references/` was prose that nothing verified. This is where a
change to those rules gets checked rather than reasoned about.

## Using it

```bash
python3 tools/import_graph.py fixtures/repo --entry app/layout.tsx
```

Then run the skill against `fixtures/repo` and compare against
`expected.json`.

**When a run disagrees with `expected.json`, check by hand.** The run may be
wrong, and so may the expectation — this file was written by reading the
fixture, and reading can be wrong too. What must never happen is editing the
expectation to match a run, which turns the test into a mirror.

## What each file exists to prove

| File | Proves |
|---|---|
| `next.config.mjs`, `package.json`, `pnpm-lock.yaml` | Framework detection from manifest, build config and lockfile |
| `app/layout.tsx` | The entry point. Reachability starts here |
| `app/globals.css` | Canonical primitives, reachable at depth 1 |
| `app/theme.css` | The semantic layer. Alias classification, and lineage from primitive to role |
| `app/components.css` | A consumer: uses tokens, defines none |
| `app/orphan-tokens.css` | **Three real token declarations no entry point reaches.** A run that inventories these has skipped reachability |
| `styles/main.scss`, `styles/_primitives.scss` | **A projection pair.** Two SCSS variables emit two custom properties. Four declarations, two concepts. A run reporting 23 tokens has skipped deduplication |
| `app/globals.css`, the `@theme` block | **A framework with a derived scale.** `--spacing: 0.25rem` is one token at a theme root; the steps Tailwind generates from it are not. `package.json` and the lockfile pin tailwindcss 4.3.0, so the framework-default check has something to read |
| `app/components.css`, `.panel` | **A scoped property.** `--panel-gap` is declared inside a component rule. Local state, never a token, whichever file holds it |
| `components/button.tsx` | Two redundant leaks: a color and a dimension a token already holds |
| `components/card.tsx` | A second file for `8px`, so blast radius is 2 files rather than 1. Also `20px`, which only the derived scale covers |
| `components/badge.tsx` | A near-miss: `#2563ec`, one hex step from `#2563eb` |
| `components/chart.tsx` | Two uncovered values: no layer token and no opacity token exists |
| `theme.config.json` | Declares `high-contrast`, which nothing resolves. `mode-completeness` must be `blocked` |
| `pnpm-workspace.yaml`, `packages/ui/` | **A workspace package imported by name.** `globals.css` imports `ui/theme.css`; the file is `packages/ui/src/theme.css`. A graph that cannot read the workspace reports it as unresolved and the file as an orphan. It defines no tokens, so the count stays at 20 |
| `app/components.css`, last rule | **A string value holding markup.** `content: "<b onmouseover=alert(1)>new</b>"`. A run that renders it unescaped has shipped an injection; `validate_run.py` rule 9 catches it |
| `dist/bundle.css` | Generated output carrying a sourceMappingURL. Holds `#2563eb`; must never be reported |
| `node_modules/pkg/theme.css` | A dependency holding `#2563eb` and `8px`; must never be reported |

## The traps, in one list

A run that gets all of these right has followed the stages rather than
pattern-matched its way to a plausible report:

1. **21 tokens, not 22 and not 23.** The projection pair is one concept
   per name (23 counts both sides). `--panel-gap` sits inside `.panel`, a
   component rule, so it is scoped state and never a token, whichever file
   holds it (22 counted by file).
2. **`app/orphan-tokens.css` is `unverified`.** It looks exactly like a
   token source and nothing imports it.
3. **`--unused-legacy-accent` is the only orphan token.** Every other token
   is referenced from `app/components.css`.
4. **`mode-completeness` is `blocked`.** Light and dark resolve;
   `high-contrast` is declared and resolves nowhere.
5. **Fourteen families are `absent`, not `0`.** The fixture declares tokens
   for five families only.
6. **`dist/` and `node_modules/` contribute nothing.** Both hold literals
   that would otherwise read as leaks.
7. **`20px` is `uncovered`, never `redundant`.** Only Tailwind's derived
   scale covers it — `--spacing` times five — and a derived scale is one
   token with no named step to swap to. This is the question two runs
   split on.

## What this fixture does not cover

Recorded so nobody mistakes a passing run here for full coverage:

- **A resolving mode set.** Every mode path here ends in `blocked`. A second
  fixture is needed where all declared modes resolve and
  `mode-completeness` grades normally.
- **Scale.** Twenty tokens sits in the `full` rendering tier, so the
  `collapsed` and `family-only` forms and the density rules go untested.
- **A monorepo.** Scope derivation with more than one plausible app is
  unexercised.
