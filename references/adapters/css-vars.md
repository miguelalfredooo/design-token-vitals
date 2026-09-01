# CSS custom properties

The adapter for a token layer built straight out of `--*` declarations, with
no build step standing between the token and the browser.

## Where tokens live

Look for `--*` declarations inside `:root`, `[data-theme]`, and
`@media (prefers-color-scheme:)` blocks. Most repositories keep these in one
file — `globals.css`, `tokens.css`, or `theme.css` — rather than spread
across components.

## Detection

A `.css` file counts as your token source once it holds 20 or more `--`
declarations inside a single `:root` block. Fewer than that, and you are
likely looking at a handful of one-off variables rather than a system.

## What a leak looks like

A hex, `rgb()`, `hsl()`, `oklch()`, `px`, `rem`, or `ms` value sitting in a
component file when a `var(--…)` covering that exact value was already
available. Skip the token source file itself when you scan — the
declarations there are definitions, not leaks, and flagging them tells you
nothing about the codebase's health.

## How modes are expressed

Your dark mode lives as a second `:root`-shaped block, scoped under
`[data-theme="dark"]` or `@media (prefers-color-scheme: dark)`. A mode gap
is a custom property present in one block and missing from the other — it
will not error at build time, so you will not see it until someone opens
the page in the mode you forgot.

## Idiomatic enforcement

Reach for stylelint's `declaration-property-value-disallowed-list`, or write
a rule that flags raw hex values outside the token file. Either one turns a
leak into a lint failure instead of a finding you catch after the fact.
