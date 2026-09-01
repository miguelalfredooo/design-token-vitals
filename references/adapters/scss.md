# SCSS / Less

The adapter for a token layer built from preprocessor variables rather than
runtime CSS.

## Where tokens live

Look for `$variable` declarations, `@use` / `@forward` module members,
`map.get()` lookups against a token map, and `@each` loops that generate
names from a map. Common homes are `_variables.scss`, `_tokens.scss` or a
`tokens/` directory, and a system spread across a dozen partials is just as
common.

## Detection

This adapter applies once the repository declares preprocessor variables at
all. **Which files are token sources is settled by discovery, never by a
filename or a declaration count** — see jobs two through four of
`references/discovery.md`. Collect every file holding variable declarations
as a candidate, follow the `@use` and `@forward` chain with
`tools/import_graph.py`, and keep what is reachable from an owned bundle
root.

Watch for the projection case: a partial that emits `--custom-properties`
from its `$variables` is one token concept with two source sites, and job
five of `references/discovery.md` collapses it. Counting both sides doubles
the system's apparent size.

## What a leak looks like

A raw measurement or color inside a rule, where a variable already in scope
carries that exact value. The variable does not need to live in the same
file — anything reachable through the current `@use` chain counts as in
scope.

## How modes are expressed

**Caution:** SCSS variables resolve at compile time, so a runtime theme
switch cannot live in a `$variable` alone — it needs a mixin that emits both
sets of rules, or a class-scoped override applied at runtime. Find that
mechanism before you grade modes here; grading against the variables alone
will miss where the actual switch happens. If your repository has no mode
mechanism at all, `mode-completeness` is `not_applicable`, not `fail` —
note in the finding that no mode mechanism was found, so the grade reads as
absence of a mode story rather than a broken one.

## Idiomatic enforcement

stylelint with `scss/dollar-variable-pattern` catches naming drift in the
variables themselves. Add a disallowed-list rule alongside it to catch raw
values sitting in rules that had a variable available.
