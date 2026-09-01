# Tailwind CSS

The adapter for a token layer expressed through Tailwind's utility classes,
whichever major version generated them.

## Where tokens live

In Tailwind v4, tokens live in an `@theme` block. In v3, they live in
`theme.extend` inside `tailwind.config.*`. Both usually reference CSS custom
properties underneath, so run the checks in `references/adapters/css-vars.md`
against the same repository as well, and report the two adapters' findings
as one merged set — a value that leaks past a Tailwind utility and a value
that leaks past the underlying custom property are the same leak seen from
two layers.

## Detection

A `tailwind.config.*` file, or an `@import "tailwindcss"` / `@theme` block
inside a CSS file, tells you this is the adapter to run.

A category absent from the project's own theme can still come from
Tailwind's own default theme — for example `z-*` and `opacity-*` utilities
ship with a built-in scale even when a project never overrides one. Before
grading `coverage` as missing a category, check the installed version's
default theme and record the version you checked.

## What a leak looks like

A bracket-arbitrary value carrying a raw measurement or color:
`bg-[#0F8A83]`, `p-[15px]`, `duration-[240ms]`. A bracket value that
references a variable clears the bar — flag only the literals.

**Gotcha, and the most valuable line in this file:** a bracket-arbitrary
value holding a bare custom-property name compiles to invalid CSS and is
dropped with no error. `bg-[--brand]` renders transparent, because Tailwind
needs `bg-[var(--brand)]` or the v4 parenthesis shorthand to treat it as a
reference rather than a literal string. Report these as `redundant` leaks —
the value was meant to reference an existing token — and worth fixing
first: the element ships unstyled, and nothing in the build warns you.

## How modes are expressed

The `dark:` variant carries the mode split, layered on top of whatever the
underlying custom properties do. A token used with `dark:` that has no dark
definition behind it is a mode gap — the class compiles, but the value it
resolves to at runtime never changes.

## Idiomatic enforcement

`eslint-plugin-tailwindcss` catches malformed and redundant classes. Pair it
with a custom rule that flags bracket-arbitrary literals, since that plugin
does not itself distinguish a literal from a variable reference inside the
brackets.
