# Generic

The fallback adapter. It runs when nothing in `references/discovery.md`'s
signal table matches, so an unknown framework degrades to evidence-based
discovery rather than to a guess.

An adapter says **where to look** for entry points, imports, token
conventions and mode behavior. No adapter names a token file.

## Detection

This adapter applies when no other one does. Record
`stack.confidence: inferred`, and say in the report that the framework was
unrecognized and what you searched instead.

## Where to look for entry points

With no framework convention to rely on, rank candidates by evidence:

1. A stylesheet imported by an application entry module — `src/main.*`,
   `src/index.*`, a root layout, an `App.*`.
2. A stylesheet referenced from a served HTML template by `<link rel>`.
3. A stylesheet with inbound imports and no outbound ones, at the top of
   its own import tree.
4. The stylesheet with the most inbound imports across the tree.

Run `tools/import_graph.py` with no `--entry` to get its conventional
detection first, then add roots you find by the list above. State which
rule found each root.

## Token conventions to search

Everything in job two of `references/discovery.md`, with no filename
assumption:

- `--*` declarations in any selector, and `@property` registrations
- `$` and `@` preprocessor variables, Sass maps, and `@each` generators
- JS and TS objects whose keys read as token names, and whose values are
  colors, dimensions, durations or font stacks
- JSON with DTCG `$value` and `$type` keys, Style Dictionary structure, or
  Tokens Studio exports

Search for every family in `references/token-taxonomy.md` by its common
names. A family found nowhere is `absent` when the project declares nothing
for it, and `unmeasured` when something blocked the search.

## What a leak looks like

A raw color, dimension, duration, shadow or font value in an owned,
reachable consumer file, where a reachable token already carries that
value. Classify through the cascade in `references/leakage.md`.

## How modes are expressed

Unknown, until you find the mechanism. Look for a second declaration block
under a class, a `data-*` attribute, or a media query; a theme provider in
JS; or a build step that emits one file per scheme.

Where you find no mechanism, `mode-completeness` is `not_applicable` with a
note saying no mode mechanism was found. Where you find a mechanism but no
resolved output for every declared scheme, it is `blocked` — see job six of
`references/discovery.md`.

## Idiomatic enforcement

With no framework convention, look for whatever the repository already
runs: stylelint, ESLint, a custom CI script, a pre-commit hook. Grade
`enforcement` on whether any of them reads the token layer, rather than on
whether a particular tool is present.
