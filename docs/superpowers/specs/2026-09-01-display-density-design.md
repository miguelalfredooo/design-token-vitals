# Display density — design

**Date:** 2026-09-01
**Status:** approved, not yet implemented
**Supersedes:** the 40-row rule in `references/report.md`

---

## The problem

A run against a 258-token codebase found plenty and showed almost none of it.

| Section | Found | Shown |
|---|---|---|
| Color inventory | 208 custom properties | 4 swatches |
| Redundant leaks | 24 groups, 317 occurrences | 6 rows |
| Orphans | 17 names | 0 |
| Type scale | 27 properties | a sentence describing them |
| Spacing scale | 23 properties | a sentence describing them |

The first fix replaced those fixed caps with a 40-row rule. That hides less, but
it hides by the same logic: when there is more data, show less of it. A designer
opening this report to understand their palette gets a summary of a summary.

## The principle

**Change the mark, don't cut the data.**

208 colors as table rows is unreadable. The same 208 as swatches in a grid is one
screen and completely readable. Too many rows was never a problem about quantity —
it was a problem about using a low-density mark for the data.

When a section outgrows its form, move to a denser form rather than a shorter
list. Disclosure is the last resort, not the first, and when it fires it holds
the tail rather than the majority.

| Data | Sparse form | Dense form | Denser still |
|---|---|---|---|
| Color | rows | swatch grid (~300) | ramps (~1000) |
| Typography | rows | specimens set at real size (~40) | — |
| Spacing and size | rows | bars drawn to width (~60) | — |
| Leaks | rows | grouped by token, count as a bar (~200 groups) | distribution plus outliers |
| Orphans | rows | inline chip list (~300) | grouped by family |
| Mode gaps | matrix | coverage bar plus exception list | — |
| Families | rows | rows with a health strip (~60) | grouped by namespace depth |

Capacities are guidance for choosing a form, never a cap on what the reader sees.

## Compress what is systematic, enumerate what is exceptional

This is what makes the compression lossless.

If 190 of your 208 colors form ordered ramps and 18 do not, the ramps compress to
a dozen strips without losing anything, because the ramp's structure is the
information. The 18 outliers get enumerated one by one, because each is a
separate fact that compresses into nothing.

The same split applies everywhere: a spacing scale that follows a ratio renders as
a sequence, and the one step that breaks the ratio gets called out. A leak found
in 84 files is one row with a count; 84 leaks each found once are 84 facts.

Systematic data has a compact visual form. Exceptions never do.

## Characterize whatever you do not show

`Showing 40 of 1,645` says nothing about the 1,605. Describe the hidden set
instead:

> The remaining 1,605 are single-file occurrences of these 12 values.

That tells the reader the shape of what they are missing and whether they need to
look. Counts stay prominent even when instances do not fit, and a distribution —
how many findings touch how many files — shows the shape when the instances
cannot.

## Inventory enumerates; the plan curates

These are different jobs and they take opposite rules.

**Inventory sections owe the reader everything.** Every color, every step, every
orphan, in whatever form fits.

**"Where to start" owes the reader the few that matter, in order.** Forty actions
is not a plan. Five is. This section is the one place a small fixed number is
correct, because its value comes from what it leaves out.

## Table width and long paths

Reports on a deeply nested codebase scroll horizontally on every table. Two causes
compound:

- `table { min-width: 620px }` and `.fam { min-width: 720px }` force a width
  regardless of content.
- `.path { white-space: nowrap }` stops the widest column from ever wrapping.

A Discourse plugin path runs to 88 characters where the shadcn example's longest
is 44, so the tables fit during development and scroll in the field.

**Let paths wrap.** Remove `white-space: nowrap` from `.path`, allow a break at
`/`, and drop the fixed `min-width` so a table sizes to its container.

**Elide the shared prefix.** Every row in a leak table tends to begin with the
same directory. Show that prefix once above the table and render each row as its
distinctive tail:

```
plugins/raptive-layout-and-styles/assets/stylesheets/
  common/share-community-feed-cta.scss:4
  common/fkb-c-topic.scss:270
```

That is the same compress-what-is-systematic rule applied to paths, and it makes
the table narrower and more readable at once rather than trading one for the
other.

## What to change

1. `references/report.md` — replace the 40-row rule with this principle, the
   form table, the systematic/exceptional split, and the remainder-characterization
   requirement. Keep "Where to start" curated at five.
2. `assets/report-template.html` — swatch grid and ramp forms for color, specimens
   for type, bars for spacing, grouped rows for leaks, chips for orphans. Remove
   the `min-width` declarations and `.path { white-space: nowrap }`. Add the
   shared-prefix treatment to the leak tables.
3. `assets/reference/small.html` and `large.html` — re-render under the new forms,
   since they are what the skill points at as worked examples.
4. `SKILL.md` — the fill stage picks a form per section from the data volume, and
   records which form it chose in the measurement section so two runs can be
   compared.
5. `examples/shadcn-ui/` — re-render. Change no grade, evidence array, or citation.

## Open question

Whether the chosen form belongs in `capability-map.yml` as a recorded decision
(`rendering.forms: {color: ramps, leaks: grouped}`) or stays implicit. Recording it
would let two runs be compared on presentation as well as findings, which is
consistent with the measurement contract. Not yet decided.
