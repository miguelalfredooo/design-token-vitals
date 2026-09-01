# CSS custom properties

The adapter for a token layer built straight out of `--*` declarations, with
no build step standing between the token and the browser.

## Where tokens live

Look for `--*` declarations in any selector — `:root`, `[data-theme]`,
`@media (prefers-color-scheme:)`, a component class — plus `@property`
registrations. Some repositories collect these in `globals.css`,
`tokens.css` or `theme.css`; plenty spread them across several files, and a
system whose color, type and spacing live in three places is normal.

## Detection

This adapter applies once the repository declares custom properties at all.
**Which files are token sources is settled by discovery, never by a
filename or a declaration count** — see jobs two through four of
`references/discovery.md`. Collect every file holding `--*` declarations as
a candidate, then keep the ones reachable from an owned production entry
point.

A declaration count is a weak signal worth recording and acting on: a file
with 20 or more `--` declarations in one block is likely canonical, and a
file with three is likely a component-local override. Record which, and let
reachability and classification decide.

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
